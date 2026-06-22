# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from plane.utils.site_audit.types import (
    STATUS_CRITICAL,
    STATUS_ERROR,
    STATUS_OK,
    STATUS_SKIPPED,
    STATUS_WARN,
)

STATUS_EMOJI = {
    STATUS_OK: "✅",
    STATUS_WARN: "⚠️",
    STATUS_CRITICAL: "🔴",
    STATUS_ERROR: "❌",
    STATUS_SKIPPED: "⏭",
}


def format_audit_report(
    *,
    results_by_site: dict[str, list],
    trigger_label: str,
    ok_count: int,
    warn_count: int,
    critical_count: int,
    error_count: int,
    duration_ms: int,
) -> list[str]:
    """Return one or more Telegram messages (max ~4000 chars each)."""
    header = (
        f"🔍 Аудит сайтов ({trigger_label})\n"
        f"✅ {ok_count}  ⚠️ {warn_count}  🔴 {critical_count}  ❌ {error_count}\n"
        f"Время: {duration_ms // 1000} с\n"
    )

    if critical_count == 0 and error_count == 0 and warn_count == 0:
        header += "\nВсе системы в норме.\n"

    lines = [header]
    for site_name, site_results in results_by_site.items():
        site_worst = STATUS_OK
        for r in site_results:
            if r.status in (STATUS_CRITICAL, STATUS_ERROR):
                site_worst = r.status
                break
            if r.status == STATUS_WARN and site_worst == STATUS_OK:
                site_worst = STATUS_WARN
        emoji = STATUS_EMOJI.get(site_worst, "•")
        lines.append(f"\n{emoji} {site_name}")
        for r in site_results:
            if r.status == STATUS_SKIPPED and r.check_type in ("renewal_reminder",):
                continue
            if r.status == STATUS_SKIPPED and not r.message:
                continue
            check_emoji = STATUS_EMOJI.get(r.status, "•")
            lines.append(f"  {check_emoji} {r.message}")

    text = "\n".join(lines)
    return _split_messages(text, 4000)


def format_alert_message(site_name: str, results: list) -> str:
    bad = [r for r in results if r.status in (STATUS_CRITICAL, STATUS_ERROR)]
    if not bad:
        return ""
    lines = [f"🚨 Алерт: {site_name}"]
    for r in bad:
        lines.append(f"  {STATUS_EMOJI.get(r.status, '•')} {r.message}")
    return "\n".join(lines)


def _split_messages(text: str, limit: int) -> list[str]:
    if len(text) <= limit:
        return [text]
    parts: list[str] = []
    current = ""
    for line in text.split("\n"):
        if len(current) + len(line) + 1 > limit:
            if current:
                parts.append(current.rstrip())
            current = line + "\n"
        else:
            current += line + "\n"
    if current.strip():
        parts.append(current.rstrip())
    return parts or [text[:limit]]
