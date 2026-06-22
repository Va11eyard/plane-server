# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import logging
import threading
from datetime import date, datetime
from typing import Any

from plane.db.models import Project
from plane.utils.telegram_task_ai import parse_task_message
from plane.utils.telegram_task_service import (
    IHEALTH_SLUG,
    build_issue_url,
    can_create_task,
    create_issue_from_telegram,
    format_date_ru,
    get_assignable_members,
    get_task_projects,
    merge_draft,
    parse_target_date,
)

logger = logging.getLogger("plane.telegram")

TASK_PROMPT_TEXT = (
    "📝 Опишите задачу одним сообщением.\n\n"
    "Можно коротко — уточню детали. Примеры:\n"
    "• «В ODOS для Димаша: поправить колонку коррекции»\n"
    "• «Жулдыз — отчёт по iHealth к пятнице»\n"
    "• «сверстать PDF по неделе»"
)


def _members_by_project(user, projects: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    result: dict[str, list[dict[str, str]]] = {}
    for p in projects:
        project = Project.objects.filter(id=p["id"]).first()
        if project:
            result[p["id"]] = get_assignable_members(project)
    return result


def _build_clarify_keyboard(session: dict[str, Any]) -> dict | None:
    missing = session.get("missing_fields") or []
    rows: list[list[dict]] = []

    if "project" in missing:
        for idx, project in enumerate(session.get("projects") or []):
            rows.append([{"text": f"📁 {project['name'][:32]}", "callback_data": f"tk:p:{idx}"}])

    if "assignee" in missing and session.get("member_options"):
        row: list[dict] = []
        for idx, member in enumerate(session["member_options"][:6]):
            label = member.get("display_name") or member.get("email") or "?"
            row.append({"text": f"👤 {label[:20]}", "callback_data": f"tk:a:{idx}"})
            if len(row) == 2:
                rows.append(row)
                row = []
        if row:
            rows.append(row)

    if session.get("interpretations"):
        for idx, interp in enumerate(session["interpretations"][:3]):
            title = (interp.get("title") or f"Вариант {idx + 1}")[:28]
            rows.append([{"text": f"💡 {title}", "callback_data": f"tk:i:{idx}"}])

    rows.append([{"text": "✖️ Отмена", "callback_data": "tk:c:x"}])
    return {"inline_keyboard": rows} if rows else None


def _build_confirm_keyboard() -> dict:
    return {
        "inline_keyboard": [
            [{"text": "✅ Создать задачу", "callback_data": "tk:c:go"}],
            [
                {"text": "📁 Сменить проект", "callback_data": "tk:c:rp"},
                {"text": "👤 Сменить исполнителя", "callback_data": "tk:c:ra"},
            ],
            [{"text": "✖️ Отмена", "callback_data": "tk:c:x"}],
        ]
    }


def _confirm_text(draft: dict[str, Any]) -> str:
    return (
        "📋 Подтвердите задачу:\n\n"
        f"📌 {draft.get('title', '—')}\n"
        f"📁 {draft.get('project_name', '—')}\n"
        f"👤 {draft.get('assignee_name', '—')}\n"
        f"📅 {format_date_ru(draft.get('target_date'))}\n"
    )


def _is_task_ready(draft: dict[str, Any], missing_fields: list[str]) -> bool:
    required = {"title", "project_id", "assignee_id"}
    if not all(draft.get(k) for k in required):
        return False
    for field in ("title", "project", "assignee"):
        if field in missing_fields:
            return False
    return True


def _apply_parse_result(session: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    session["draft"] = result.get("draft") or {}
    session["missing_fields"] = result.get("missing_fields") or []
    session["interpretations"] = result.get("interpretations") or []
    session["member_options"] = result.get("member_options") or []
    session["last_question"] = result.get("question") or ""
    return session


def _handle_parse_result(
    chat_id: int,
    session: dict[str, Any],
    result: dict[str, Any],
    *,
    send_message,
    save_session,
    show_main_menu,
    MAIN_KEYBOARD,
) -> None:
    session = _apply_parse_result(session, result)
    draft = session.get("draft") or {}
    status = result.get("status")
    missing = session.get("missing_fields") or []

    if status == "ambiguous" and session.get("interpretations"):
        session["step"] = "clarify"
        save_session(chat_id, session)
        text = result.get("question") or "Не совсем понял. Выберите вариант или опишите подробнее:"
        send_message(chat_id, text, reply_markup=_build_clarify_keyboard(session))
        return

    if status == "clarify" or not _is_task_ready(draft, missing):
        if "target_date" in missing and not session.get("asked_target_date"):
            session["asked_target_date"] = True
        session["step"] = "clarify"
        save_session(chat_id, session)
        question = result.get("question") or session.get("last_question") or _default_clarify_question(missing)
        send_message(chat_id, question, reply_markup=_build_clarify_keyboard(session))
        return

    session["step"] = "confirm"
    save_session(chat_id, session)
    send_message(chat_id, _confirm_text(draft), reply_markup=_build_confirm_keyboard())


def _default_clarify_question(missing: list[str]) -> str:
    lines = ["Уточните, пожалуйста:"]
    if "title" in missing:
        lines.append("• Что именно нужно сделать?")
    if "project" in missing:
        lines.append("• В каком проекте?")
    if "assignee" in missing:
        lines.append("• Кто будет делать?")
    if "target_date" in missing:
        lines.append("• На какое число / к какому сроку?")
    return "\n".join(lines)


def _run_parse_and_respond(
    chat_id: int,
    user_message: str,
    session: dict[str, Any],
    user,
    *,
    send_message,
    save_session,
    get_session,
    show_main_menu,
    MAIN_KEYBOARD,
) -> None:
    try:
        cached = get_session(chat_id)
        if cached and cached.get("mode") == "task":
            session = cached
        projects = session.get("projects") or get_task_projects(user)
        members_map = session.get("members_by_project") or _members_by_project(user, projects)
        history = session.get("conversation_history") or []
        history = history + [{"role": "user", "content": user_message}]
        session["conversation_history"] = history

        result = parse_task_message(
            user_message=user_message,
            projects=projects,
            members_by_project=members_map,
            conversation_history=history,
            draft=session.get("draft") or {},
            asked_target_date=session.get("asked_target_date", False),
        )
        _handle_parse_result(
            chat_id,
            session,
            result,
            send_message=send_message,
            save_session=save_session,
            show_main_menu=show_main_menu,
            MAIN_KEYBOARD=MAIN_KEYBOARD,
        )
    except Exception:
        logger.exception("Task parse failed for chat %s", chat_id)
        send_message(chat_id, "❌ Не удалось обработать сообщение. Попробуйте ещё раз.", reply_markup=MAIN_KEYBOARD)


def start_task_wizard(chat_id: int, user, *, send_message, save_session, clear_session, MAIN_KEYBOARD) -> None:
    if not can_create_task(user):
        send_message(
            chat_id,
            "Создание задач доступно участникам воркспейса iHealth.",
            reply_markup=MAIN_KEYBOARD,
        )
        return

    projects = get_task_projects(user)
    if not projects:
        send_message(
            chat_id,
            "У вас нет проектов в iHealth.",
            reply_markup=MAIN_KEYBOARD,
        )
        return

    clear_session(chat_id)
    session: dict[str, Any] = {
        "mode": "task",
        "step": "input",
        "projects": projects,
        "members_by_project": _members_by_project(user, projects),
        "draft": {},
        "conversation_history": [],
        "missing_fields": [],
        "asked_target_date": False,
        "interpretations": [],
        "member_options": [],
    }
    save_session(chat_id, session)
    send_message(chat_id, TASK_PROMPT_TEXT, reply_markup=MAIN_KEYBOARD)


def handle_task_message(
    chat_id: int,
    text: str,
    link,
    session: dict[str, Any],
    *,
    send_message,
    save_session,
    get_session,
    show_main_menu,
    clear_session,
    MAIN_KEYBOARD,
) -> bool:
    """Returns True if message was handled."""
    if session.get("mode") != "task":
        return False

    step = session.get("step", "input")
    if step in ("input", "clarify"):
        send_message(chat_id, "⏳ Анализирую…", reply_markup=MAIN_KEYBOARD)
        save_session(chat_id, session)
        threading.Thread(
            target=_run_parse_and_respond,
            kwargs={
                "chat_id": chat_id,
                "user_message": text,
                "session": session,
                "user": link.user,
                "send_message": send_message,
                "save_session": save_session,
                "get_session": get_session,
                "show_main_menu": show_main_menu,
                "MAIN_KEYBOARD": MAIN_KEYBOARD,
            },
            daemon=True,
        ).start()
        return True

    return False


def handle_task_callback(
    data: str,
    chat_id: int,
    message_id: int,
    link,
    session: dict[str, Any],
    callback_id: str,
    *,
    answer_callback,
    edit_message,
    send_message,
    save_session,
    clear_session,
    show_main_menu,
    MAIN_KEYBOARD,
) -> bool:
    """Returns True if callback was handled."""
    if not data.startswith("tk:"):
        return False

    if session.get("mode") != "task":
        answer_callback(callback_id, "Сессия задачи истекла")
        return True

    action = data[3:]
    user = link.user

    if action == "c:x":
        clear_session(chat_id)
        answer_callback(callback_id)
        edit_message(chat_id, message_id, "Отменено.", {"inline_keyboard": []})
        show_main_menu(chat_id)
        return True

    if action == "c:go":
        draft = session.get("draft") or {}
        project_id = draft.get("project_id")
        if not project_id or not draft.get("title") or not draft.get("assignee_id"):
            answer_callback(callback_id, "Не все поля заполнены")
            return True
        project = Project.objects.filter(id=project_id).first()
        if not project:
            answer_callback(callback_id, "Проект не найден")
            return True
        target_date = None
        if draft.get("target_date"):
            target_date = parse_target_date(draft["target_date"])
            if not target_date and draft["target_date"]:
                try:
                    target_date = datetime.strptime(draft["target_date"], "%Y-%m-%d").date()
                except ValueError:
                    target_date = None

        issue, error = create_issue_from_telegram(
            project=project,
            creator=user,
            title=draft["title"],
            description=draft.get("description") or "",
            assignee_id=draft.get("assignee_id"),
            target_date=target_date,
        )
        clear_session(chat_id)
        answer_callback(callback_id)
        if error or not issue:
            edit_message(chat_id, message_id, f"❌ {error or 'Ошибка создания'}", {"inline_keyboard": []})
        else:
            url = build_issue_url(IHEALTH_SLUG, str(project.id), str(issue.id))
            ident = project.identifier or "TASK"
            edit_message(
                chat_id,
                message_id,
                f"✅ Задача {ident}-{issue.sequence_id} создана:\n{url}",
                {"inline_keyboard": []},
            )
        show_main_menu(chat_id)
        return True

    if action == "c:rp":
        session["step"] = "clarify"
        session["missing_fields"] = ["project"]
        draft = session.get("draft") or {}
        draft.pop("project_id", None)
        draft.pop("project_name", None)
        session["draft"] = draft
        save_session(chat_id, session)
        answer_callback(callback_id)
        edit_message(
            chat_id,
            message_id,
            "Выберите проект:",
            _build_clarify_keyboard(session) or {"inline_keyboard": [[{"text": "✖️ Отмена", "callback_data": "tk:c:x"}]]},
        )
        return True

    if action == "c:ra":
        project_id = (session.get("draft") or {}).get("project_id")
        if not project_id:
            answer_callback(callback_id, "Сначала выберите проект")
            return True
        project = Project.objects.filter(id=project_id).first()
        if not project:
            answer_callback(callback_id, "Проект не найден")
            return True
        session["step"] = "clarify"
        session["missing_fields"] = ["assignee"]
        session["member_options"] = get_assignable_members(project)
        draft = session.get("draft") or {}
        draft.pop("assignee_id", None)
        draft.pop("assignee_name", None)
        session["draft"] = draft
        save_session(chat_id, session)
        answer_callback(callback_id)
        edit_message(
            chat_id,
            message_id,
            "Выберите исполнителя:",
            _build_clarify_keyboard(session) or {"inline_keyboard": [[{"text": "✖️ Отмена", "callback_data": "tk:c:x"}]]},
        )
        return True

    if action.startswith("p:"):
        try:
            idx = int(action[2:])
        except ValueError:
            return True
        projects = session.get("projects") or []
        if idx < 0 or idx >= len(projects):
            return True
        project = projects[idx]
        draft = merge_draft(session.get("draft") or {}, {
            "project_id": project["id"],
            "project_name": project["name"],
        })
        session["draft"] = draft
        session["member_options"] = (session.get("members_by_project") or {}).get(project["id"], [])
        missing = [f for f in (session.get("missing_fields") or []) if f != "project"]
        session["missing_fields"] = missing
        answer_callback(callback_id)
        if _is_task_ready(draft, missing):
            session["step"] = "confirm"
            save_session(chat_id, session)
            edit_message(chat_id, message_id, _confirm_text(draft), _build_confirm_keyboard())
        else:
            session["step"] = "clarify"
            save_session(chat_id, session)
            edit_message(
                chat_id,
                message_id,
                _default_clarify_question(missing),
                _build_clarify_keyboard(session) or {"inline_keyboard": []},
            )
        return True

    if action.startswith("a:"):
        try:
            idx = int(action[2:])
        except ValueError:
            return True
        members = session.get("member_options") or []
        if idx < 0 or idx >= len(members):
            return True
        member = members[idx]
        draft = merge_draft(session.get("draft") or {}, {
            "assignee_id": member["id"],
            "assignee_name": member.get("display_name") or member.get("email"),
        })
        session["draft"] = draft
        missing = [f for f in (session.get("missing_fields") or []) if f != "assignee"]
        session["missing_fields"] = missing
        answer_callback(callback_id)
        if _is_task_ready(draft, missing):
            session["step"] = "confirm"
            save_session(chat_id, session)
            edit_message(chat_id, message_id, _confirm_text(draft), _build_confirm_keyboard())
        else:
            session["step"] = "clarify"
            save_session(chat_id, session)
            edit_message(
                chat_id,
                message_id,
                _default_clarify_question(missing),
                _build_clarify_keyboard(session) or {"inline_keyboard": []},
            )
        return True

    if action.startswith("i:"):
        try:
            idx = int(action[2:])
        except ValueError:
            return True
        interpretations = session.get("interpretations") or []
        if idx < 0 or idx >= len(interpretations):
            return True
        interp = interpretations[idx]
        answer_callback(callback_id)
        send_message(chat_id, "⏳ Применяю вариант…", reply_markup=MAIN_KEYBOARD)
        msg = (
            f"{interp.get('title', '')}. "
            f"{interp.get('description', '')} "
            f"Проект: {interp.get('project_hint') or ''}. "
            f"Исполнитель: {interp.get('assignee_hint') or ''}. "
            f"Срок: {interp.get('target_date_hint') or ''}."
        )
        threading.Thread(
            target=_run_parse_and_respond,
            kwargs={
                "chat_id": chat_id,
                "user_message": msg.strip(),
                "session": session,
                "user": user,
                "send_message": send_message,
                "save_session": save_session,
                "get_session": get_session,
                "show_main_menu": show_main_menu,
                "MAIN_KEYBOARD": MAIN_KEYBOARD,
            },
            daemon=True,
        ).start()
        return True

    return True
