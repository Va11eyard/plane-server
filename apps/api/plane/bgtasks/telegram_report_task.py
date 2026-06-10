# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import logging
from datetime import datetime

from celery import shared_task
from django.contrib.auth import get_user_model

from plane.app.views.report import generate_activity_report
from plane.app.views.telegram import send_telegram_document
from plane.db.models import Workspace
from plane.utils.exception_logger import log_exception
from plane.utils.pdf_report import render_report_pdf
from plane.utils.telegram_bot import clear_session, send_message

logger = logging.getLogger("plane.telegram")


def run_telegram_report_generation(
    chat_id: int,
    user_id: str,
    workspace_id: str,
    period_from: str,
    period_to: str,
    project_ids: list[str] | None,
    use_whole_workspace: bool,
    title: str = "",
) -> None:
    User = get_user_model()
    try:
        user = User.objects.get(pk=user_id)
        workspace = Workspace.objects.get(pk=workspace_id)
        p_from = datetime.strptime(period_from, "%Y-%m-%d").date()
        p_to = datetime.strptime(period_to, "%Y-%m-%d").date()

        report, error = generate_activity_report(
            workspace=workspace,
            user=user,
            period_from=p_from,
            period_to=p_to,
            project_ids=None if use_whole_workspace else project_ids,
            title=title,
        )
        if error or not report:
            send_message(chat_id, f"❌ Не удалось сгенерировать отчёт: {error or 'неизвестная ошибка'}")
            return

        pdf_bytes = render_report_pdf(
            title=report.title or "Отчёт",
            content=report.content,
            period_from=report.period_from.isoformat() if report.period_from else "",
            period_to=report.period_to.isoformat() if report.period_to else "",
            author=report.created_by.display_name if report.created_by else "",
        )
        ok, err = send_telegram_document(
            chat_id=chat_id,
            file_bytes=pdf_bytes,
            filename=f"{report.title or 'report'}.pdf",
            caption=f"✅ {report.title or 'Отчёт'}",
        )
        if not ok:
            send_message(chat_id, f"❌ Отчёт создан, но не удалось отправить PDF: {err}")
        else:
            send_message(chat_id, "Готово! Нажмите «📊 Новый отчёт» для следующего.")
    except Exception as e:
        log_exception(e)
        logger.exception("Telegram report generation failed")
        send_message(chat_id, "❌ Произошла ошибка при генерации отчёта. Попробуйте позже.")
    finally:
        clear_session(chat_id)


@shared_task
def generate_telegram_report_task(
    chat_id: int,
    user_id: str,
    workspace_id: str,
    period_from: str,
    period_to: str,
    project_ids: list[str] | None,
    use_whole_workspace: bool,
    title: str = "",
):
    run_telegram_report_generation(
        chat_id,
        user_id,
        workspace_id,
        period_from,
        period_to,
        project_ids,
        use_whole_workspace,
        title,
    )
