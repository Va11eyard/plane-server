# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import logging
import threading

from plane.utils.site_audit.permissions import can_run_site_audit

logger = logging.getLogger("plane.telegram")

AUDIT_TRIGGERS = {
    "/audit",
    "🔍 аудит сайтов",
    "аудит сайтов",
}


def is_audit_trigger(text: str) -> bool:
    normalized = text.strip().lower()
    return normalized in AUDIT_TRIGGERS or normalized.startswith("/audit")


def start_site_audit(
    chat_id: int,
    user,
    *,
    send_message,
    get_main_keyboard,
) -> None:
    if not can_run_site_audit(user):
        send_message(
            chat_id,
            "Аудит сайтов доступен только уполномоченным пользователям.",
            reply_markup=get_main_keyboard(user),
        )
        return

    send_message(chat_id, "⏳ Запускаю аудит сайтов…", reply_markup=get_main_keyboard(user))
    threading.Thread(
        target=_run_audit_and_respond,
        kwargs={"chat_id": chat_id, "user": user, "send_message": send_message, "get_main_keyboard": get_main_keyboard},
        daemon=True,
    ).start()


def _run_audit_and_respond(
    chat_id: int,
    user,
    *,
    send_message,
    get_main_keyboard,
) -> None:
    try:
        from plane.bgtasks.site_audit_task import run_manual_site_audit

        run_manual_site_audit(telegram=True)
        send_message(chat_id, "✅ Аудит завершён. Отчёт отправлен.", reply_markup=get_main_keyboard(user))
    except Exception:
        logger.exception("Site audit from Telegram failed")
        send_message(chat_id, "❌ Ошибка аудита сайтов.", reply_markup=get_main_keyboard(user))
