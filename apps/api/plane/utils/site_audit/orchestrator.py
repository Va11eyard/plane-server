# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import logging
import time
from dataclasses import dataclass, field

from django.core.cache import cache

from plane.db.models import MonitorCheckResult, MonitorRun, MonitorSite
from plane.utils.site_audit.permissions import probe_renewal_reminder
from plane.utils.site_audit.probe_http import probe_health_url, probe_https_reachable
from plane.utils.site_audit.probe_ssh import probe_ssh_docker, probe_ssh_systemd
from plane.utils.site_audit.probe_ssl import probe_ssl_expiry
from plane.utils.site_audit.report_formatter import format_alert_message, format_audit_report
from plane.utils.site_audit.types import (
    STATUS_CRITICAL,
    STATUS_ERROR,
    STATUS_OK,
    STATUS_SKIPPED,
    STATUS_WARN,
    ProbeResult,
)

logger = logging.getLogger("plane.site_audit")

ALERT_COOLDOWN_SECONDS = 30 * 60
FAIL_STREAK_KEY = "site_audit:fail_streak:{site_slug}:{check_key}"
ALERT_SENT_KEY = "site_audit:alert_sent:{site_slug}:{check_key}"
FAIL_STREAK_THRESHOLD = 2


@dataclass
class AuditRunResult:
    run: MonitorRun | None = None
    results_by_site: dict[str, list[ProbeResult]] = field(default_factory=dict)
    all_results: list[ProbeResult] = field(default_factory=list)
    ok_count: int = 0
    warn_count: int = 0
    critical_count: int = 0
    error_count: int = 0
    duration_ms: int = 0
    alerts: list[str] = field(default_factory=list)


def _count_status(results: list[ProbeResult]) -> dict[str, int]:
    counts = {STATUS_OK: 0, STATUS_WARN: 0, STATUS_CRITICAL: 0, STATUS_ERROR: 0}
    for r in results:
        if r.status in counts:
            counts[r.status] += 1
    return counts


def _probe_site(site: MonitorSite, *, fast_only: bool) -> list[ProbeResult]:
    results: list[ProbeResult] = []

    ssl_url = site.base_url or site.health_url
    if ssl_url:
        results.append(probe_ssl_expiry(ssl_url))

    if site.base_url:
        results.append(probe_https_reachable(site.base_url))

    if site.health_url:
        results.append(probe_health_url(site.health_url))

    if not fast_only:
        results.extend(
            probe_renewal_reminder(
                site_name=site.name,
                domain_renewal_at=site.domain_renewal_at,
                vps_renewal_at=site.vps_renewal_at,
            )
        )
        for check in site.checks_json or []:
            if not isinstance(check, dict):
                continue
            ctype = check.get("type", "")
            if ctype == "systemd":
                unit = check.get("unit", "")
                if unit:
                    results.append(probe_ssh_systemd(site.ssh_host, unit))
            elif ctype == "docker":
                results.append(
                    probe_ssh_docker(
                        site.ssh_host,
                        site.ssh_project_path,
                        compose_file=str(check.get("compose_file") or ""),
                        use_sudo=bool(check.get("use_sudo")),
                    )
                )

    return results


def _save_run(
    *,
    trigger: str,
    fast_only: bool,
    results_by_site: dict[str, list[ProbeResult]],
    site_map: dict[str, MonitorSite],
    duration_ms: int,
) -> MonitorRun:
    all_flat = [r for rs in results_by_site.values() for r in rs]
    counts = _count_status(all_flat)

    summary_parts = []
    if counts[STATUS_CRITICAL]:
        summary_parts.append(f"critical={counts[STATUS_CRITICAL]}")
    if counts[STATUS_ERROR]:
        summary_parts.append(f"error={counts[STATUS_ERROR]}")
    if counts[STATUS_WARN]:
        summary_parts.append(f"warn={counts[STATUS_WARN]}")

    run = MonitorRun.objects.create(
        trigger=trigger,
        fast_only=fast_only,
        sites_checked=len(results_by_site),
        ok_count=counts[STATUS_OK],
        warn_count=counts[STATUS_WARN],
        critical_count=counts[STATUS_CRITICAL],
        error_count=counts[STATUS_ERROR],
        duration_ms=duration_ms,
        summary=", ".join(summary_parts) or "ok",
    )

    for site_slug, site_results in results_by_site.items():
        site = site_map.get(site_slug)
        if not site:
            continue
        for pr in site_results:
            MonitorCheckResult.objects.create(
                run=run,
                site=site,
                check_type=pr.check_type,
                check_key=pr.check_key,
                status=pr.status,
                message=pr.message[:2000],
                details_json=pr.details,
                duration_ms=pr.duration_ms,
            )
    return run


def _check_key_for_probe(site_slug: str, pr: ProbeResult) -> str:
    return f"{site_slug}:{pr.check_type}:{pr.check_key or 'default'}"


def _should_alert(site_slug: str, pr: ProbeResult) -> bool:
    if pr.status not in (STATUS_CRITICAL, STATUS_ERROR):
        key = _check_key_for_probe(site_slug, pr)
        cache.delete(FAIL_STREAK_KEY.format(site_slug=site_slug, check_key=key))
        return False

    key = _check_key_for_probe(site_slug, pr)
    streak_key = FAIL_STREAK_KEY.format(site_slug=site_slug, check_key=key)
    streak = cache.get(streak_key, 0) + 1
    cache.set(streak_key, streak, timeout=3600)

    if streak < FAIL_STREAK_THRESHOLD:
        return False

    alert_key = ALERT_SENT_KEY.format(site_slug=site_slug, check_key=key)
    if cache.get(alert_key):
        return False
    cache.set(alert_key, True, timeout=ALERT_COOLDOWN_SECONDS)
    return True


def run_site_audit(
    *,
    trigger: str = MonitorRun.Trigger.SCHEDULED,
    fast_only: bool = False,
    site_slug: str | None = None,
    persist: bool = True,
    send_alerts: bool = True,
) -> AuditRunResult:
    start = time.monotonic()
    qs = MonitorSite.objects.filter(enabled=True)
    if site_slug:
        qs = qs.filter(slug=site_slug)

    sites = list(qs.order_by("sort_order", "name"))
    results_by_site: dict[str, list[ProbeResult]] = {}
    site_map: dict[str, MonitorSite] = {}
    alerts: list[str] = []

    for site in sites:
        site_map[site.slug] = site
        site_results = _probe_site(site, fast_only=fast_only)
        results_by_site[site.name] = site_results

        if send_alerts:
            alert_results = [pr for pr in site_results if _should_alert(site.slug, pr)]
            if alert_results:
                msg = format_alert_message(site.name, alert_results)
                if msg:
                    alerts.append(msg)

    all_flat = [r for rs in results_by_site.values() for r in rs]
    counts = _count_status(all_flat)
    duration_ms = int((time.monotonic() - start) * 1000)

    result = AuditRunResult(
        results_by_site=results_by_site,
        all_results=all_flat,
        ok_count=counts[STATUS_OK],
        warn_count=counts[STATUS_WARN],
        critical_count=counts[STATUS_CRITICAL],
        error_count=counts[STATUS_ERROR],
        duration_ms=duration_ms,
        alerts=alerts,
    )

    if persist and sites:
        slug_results = {site.slug: results_by_site.get(site.name, []) for site in sites}
        result.run = _save_run(
            trigger=trigger,
            fast_only=fast_only,
            results_by_site=slug_results,
            site_map=site_map,
            duration_ms=duration_ms,
        )

    return result


def build_telegram_messages(audit: AuditRunResult, trigger_label: str) -> list[str]:
    return format_audit_report(
        results_by_site=audit.results_by_site,
        trigger_label=trigger_label,
        ok_count=audit.ok_count,
        warn_count=audit.warn_count,
        critical_count=audit.critical_count,
        error_count=audit.error_count,
        duration_ms=audit.duration_ms,
    )


def send_audit_to_telegram(messages: list[str], *, alerts: list[str] | None = None) -> None:
    from plane.utils.telegram_bot import send_message

    from plane.utils.site_audit.permissions import get_audit_recipient_chat_ids

    chat_ids = get_audit_recipient_chat_ids()
    if not chat_ids:
        logger.warning("No Telegram chat IDs for site audit recipients")
        return

    for chat_id in chat_ids:
        for alert in alerts or []:
            send_message(chat_id, alert)
        for msg in messages:
            send_message(chat_id, msg)
