# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import os
from datetime import date

from plane.db.models import User
from plane.utils.site_audit.types import (
    RENEWAL_WARN_DAYS,
    ProbeResult,
    STATUS_CRITICAL,
    STATUS_OK,
    STATUS_SKIPPED,
    STATUS_WARN,
)


def get_site_audit_recipient_emails() -> set[str]:
    raw = os.environ.get("SITE_AUDIT_RECIPIENT_EMAILS", "").strip()
    if not raw:
        raw = "dimash@galamat.com"
    return {email.strip().lower() for email in raw.split(",") if email.strip()}


def can_run_site_audit(user: User) -> bool:
    if not user.email:
        return False
    return user.email.lower() in get_site_audit_recipient_emails()


def get_audit_recipient_chat_ids() -> list[int]:
    from plane.db.models import UserTelegramLink

    emails = get_site_audit_recipient_emails()
    return list(
        UserTelegramLink.objects.filter(user__email__in=emails)
        .values_list("telegram_chat_id", flat=True)
        .distinct()
    )


def probe_renewal_reminder(
    *,
    site_name: str,
    domain_renewal_at: date | None,
    vps_renewal_at: date | None,
) -> list[ProbeResult]:
    results: list[ProbeResult] = []
    today = date.today()

    if domain_renewal_at:
        days = (domain_renewal_at - today).days
        if days < 0:
            status, msg = STATUS_CRITICAL, f"Домен просрочен ({domain_renewal_at})"
        elif days <= RENEWAL_WARN_DAYS:
            status, msg = STATUS_WARN, f"Оплата домена через {days} дн. ({domain_renewal_at})"
        else:
            status, msg = STATUS_OK, f"Домен до {domain_renewal_at} ({days} дн.)"
        results.append(
            ProbeResult(
                check_type="renewal_reminder",
                check_key="domain",
                status=status,
                message=msg,
                details={"renewal_at": domain_renewal_at.isoformat(), "days_left": days},
            )
        )

    if vps_renewal_at:
        days = (vps_renewal_at - today).days
        if days < 0:
            status, msg = STATUS_CRITICAL, f"VPS просрочен ({vps_renewal_at})"
        elif days <= RENEWAL_WARN_DAYS:
            status, msg = STATUS_WARN, f"Оплата VPS через {days} дн. ({vps_renewal_at})"
        else:
            status, msg = STATUS_OK, f"VPS до {vps_renewal_at} ({days} дн.)"
        results.append(
            ProbeResult(
                check_type="renewal_reminder",
                check_key="vps",
                status=status,
                message=msg,
                details={"renewal_at": vps_renewal_at.isoformat(), "days_left": days},
            )
        )

    if not results:
        results.append(
            ProbeResult(
                check_type="renewal_reminder",
                status=STATUS_SKIPPED,
                message="Даты оплаты не заданы",
            )
        )
    return results
