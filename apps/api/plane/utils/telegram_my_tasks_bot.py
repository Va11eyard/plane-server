# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from plane.db.models import Issue
from plane.utils.telegram_task_service import (
    build_issue_url,
    count_user_pending_issues,
    format_date_ru,
    get_user_pending_issues,
)

MY_TASKS_TRIGGERS = {
    "/mytasks",
    "/tasks",
    "📋 мои задачи",
    "мои задачи",
    "мои активные задачи",
}

PRIORITY_MARKERS = {
    "urgent": "🔴",
    "high": "🟠",
    "medium": "🟡",
    "low": "🔵",
    "none": "⚪",
}

MAX_ISSUES_PER_MESSAGE = 20
TELEGRAM_TEXT_LIMIT = 4096


def is_my_tasks_trigger(text: str) -> bool:
    normalized = text.strip().lower()
    return normalized in MY_TASKS_TRIGGERS or normalized.startswith(("/mytasks", "/tasks"))


def _format_issue_line(issue: Issue) -> str:
    project = issue.project
    ident = project.identifier or "TASK"
    marker = PRIORITY_MARKERS.get(issue.priority or "none", "⚪")
    state_name = issue.state.name if issue.state else "—"
    url = build_issue_url(project.workspace.slug, str(project.id), str(issue.id))
    title = (issue.name or "—")[:60]
    return (
        f"{marker} {ident}-{issue.sequence_id} {title}\n"
        f"   📁 {project.name} · {state_name} · 📅 {format_date_ru(issue.target_date)}\n"
        f"   {url}"
    )


def format_my_tasks_message(issues: list[Issue], *, total_count: int | None = None) -> str:
    if not issues:
        return "📋 У вас нет активных назначенных задач в iHealth."

    shown = len(issues)
    total = total_count if total_count is not None else shown
    header = f"📋 Ваши задачи ({shown}"
    if total > shown:
        header += f" из {total}"
    header += "):\n\n"

    lines = [_format_issue_line(issue) for issue in issues]
    body = "\n\n".join(lines)
    if total > shown:
        body += f"\n\n…и ещё {total - shown}. Откройте Plane для полного списка."

    text = header + body
    if len(text) <= TELEGRAM_TEXT_LIMIT:
        return text

    truncated: list[str] = []
    current = header
    for line in lines:
        chunk = ("\n\n" if truncated else "") + line
        if len(current) + len(chunk) > TELEGRAM_TEXT_LIMIT - 20:
            break
        truncated.append(line)
        current += chunk
    omitted = len(lines) - len(truncated)
    suffix = f"\n\n…и ещё {omitted} задач." if omitted else ""
    return header + "\n\n".join(truncated) + suffix


def show_my_tasks(
    chat_id: int,
    user,
    *,
    send_message,
    get_main_keyboard,
) -> None:
    total_count = count_user_pending_issues(user)
    issues = get_user_pending_issues(user, limit=MAX_ISSUES_PER_MESSAGE)
    text = format_my_tasks_message(issues, total_count=total_count)
    send_message(chat_id, text, reply_markup=get_main_keyboard(user))
