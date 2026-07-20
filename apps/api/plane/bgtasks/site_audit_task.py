# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import logging

from celery import shared_task

from plane.db.models import MonitorRun
from plane.utils.exception_logger import log_exception
from plane.utils.site_audit.orchestrator import (
    build_telegram_messages,
    run_site_audit,
    send_audit_to_telegram,
)

logger = logging.getLogger("plane.site_audit")


def _execute_audit(
    *,
    trigger: str,
    fast_only: bool,
    trigger_label: str,
    send_report: bool,
    site_slug: str | None = None,
) -> None:
    try:
        audit = run_site_audit(
            trigger=trigger,
            fast_only=fast_only,
            site_slug=site_slug,
            persist=True,
            send_alerts=True,
        )
        if send_report:
            messages = build_telegram_messages(audit, trigger_label)
            send_audit_to_telegram(messages, alerts=audit.alerts if fast_only else None)
        elif audit.alerts:
            send_audit_to_telegram([], alerts=audit.alerts)
    except Exception as e:
        log_exception(e)
        logger.exception("Site audit failed: %s", trigger)


@shared_task
def run_daily_site_audit() -> None:
    _execute_audit(
        trigger=MonitorRun.Trigger.SCHEDULED,
        fast_only=False,
        trigger_label="ежедневный",
        send_report=True,
    )


@shared_task
def run_fast_site_probes() -> None:
    _execute_audit(
        trigger=MonitorRun.Trigger.ALERT,
        fast_only=True,
        trigger_label="быстрая проверка",
        send_report=False,
    )


def run_manual_site_audit(*, telegram: bool = False, site_slug: str | None = None) -> None:
    trigger = MonitorRun.Trigger.TELEGRAM if telegram else MonitorRun.Trigger.MANUAL
    if telegram and not site_slug:
        site_slug = "odos"
        label = "ODOS endpoints"
    else:
        label = "Telegram" if telegram else "ручной"
    _execute_audit(
        trigger=trigger,
        fast_only=False,
        trigger_label=label,
        send_report=True,
        site_slug=site_slug,
    )
