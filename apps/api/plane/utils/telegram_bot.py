# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import logging
import os
import threading
from datetime import date, timedelta
from typing import Any

import requests
from django.core.cache import cache
from plane.db.models import Project, UserTelegramLink, Workspace
from plane.utils.telegram_task_bot import handle_task_callback, handle_task_message, start_task_wizard

logger = logging.getLogger("plane.telegram")


def get_bot_token() -> str | None:
    return os.environ.get("TELEGRAM_BOT_TOKEN")


SESSION_TTL = 60 * 30
PROJECTS_PER_PAGE = 8
SESSION_KEY = "telegram_report_session:{chat_id}"

MAIN_KEYBOARD = {
    "keyboard": [
        [{"text": "📊 Новый отчёт"}, {"text": "📝 Новая задача"}],
        [{"text": "ℹ️ Помощь"}],
    ],
    "resize_keyboard": True,
    "is_persistent": True,
}

TASK_TRIGGERS = {
    "/task",
    "📝 новая задача",
    "новая задача",
    "создать задачу",
    "новая задача в plane",
}

REPORT_TRIGGERS = {
    "/report",
    "📊 новый отчёт",
    "новый отчёт",
    "новый отчет",
    "отчет",
    "отчёт",
    "отправь отчет",
    "отправь отчёт",
    "сгенерировать отчёт",
    "сгенерировать отчет",
}


def _session_key(chat_id: int) -> str:
    return SESSION_KEY.format(chat_id=chat_id)


def get_session(chat_id: int) -> dict[str, Any] | None:
    return cache.get(_session_key(chat_id))


def save_session(chat_id: int, session: dict[str, Any]) -> None:
    cache.set(_session_key(chat_id), session, SESSION_TTL)


def clear_session(chat_id: int) -> None:
    cache.delete(_session_key(chat_id))


def _api(method: str, payload: dict) -> dict | None:
    token = get_bot_token()
    if not token:
        return None
    try:
        resp = requests.post(f"https://api.telegram.org/bot{token}/{method}", json=payload, timeout=30)
        data = resp.json()
        if data.get("ok"):
            return data.get("result")
        logger.warning("Telegram API %s failed: %s", method, data.get("description"))
    except Exception:
        logger.exception("Telegram API %s error", method)
    return None


def send_message(chat_id: int, text: str, reply_markup: dict | None = None) -> int | None:
    payload: dict[str, Any] = {"chat_id": chat_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    result = _api("sendMessage", payload)
    return result.get("message_id") if result else None


def edit_message(chat_id: int, message_id: int, text: str, reply_markup: dict | None = None) -> None:
    payload: dict[str, Any] = {"chat_id": chat_id, "message_id": message_id, "text": text}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    _api("editMessageText", payload)


def answer_callback(callback_query_id: str, text: str = "") -> None:
    payload: dict[str, Any] = {"callback_query_id": callback_query_id}
    if text:
        payload["text"] = text[:200]
    _api("answerCallbackQuery", payload)


def get_link(chat_id: int) -> UserTelegramLink | None:
    return UserTelegramLink.objects.filter(telegram_chat_id=chat_id).select_related("user").first()


def get_user_workspaces(user) -> list[Workspace]:
    return list(
        Workspace.objects.filter(workspace_member__member=user, workspace_member__is_active=True)
        .distinct()
        .order_by("name")
    )


def get_workspace_projects(user, workspace: Workspace) -> list[Project]:
    return list(
        Project.objects.filter(
            workspace=workspace,
            project_projectmember__member=user,
            project_projectmember__is_active=True,
        )
        .distinct()
        .order_by("name")
    )


def _is_report_trigger(text: str) -> bool:
    normalized = text.strip().lower()
    return normalized in REPORT_TRIGGERS or normalized.startswith("/report")


def _is_task_trigger(text: str) -> bool:
    normalized = text.strip().lower()
    return normalized in TASK_TRIGGERS or normalized.startswith("/task")


def _projects_summary(session: dict[str, Any]) -> str:
    if session.get("use_whole_workspace"):
        return "Весь воркспейс"
    selected = session.get("selected_ids") or []
    projects = session.get("projects") or []
    if not selected:
        return "не выбрано"
    names = [p["name"] for p in projects if p["id"] in selected]
    if len(names) <= 3:
        return ", ".join(names)
    return f"{len(names)} проектов"


def _build_projects_keyboard(session: dict[str, Any]) -> dict:
    projects = session.get("projects") or []
    page = session.get("page", 0)
    selected = set(session.get("selected_ids") or [])
    use_whole = session.get("use_whole_workspace", False)
    start = page * PROJECTS_PER_PAGE
    page_projects = projects[start : start + PROJECTS_PER_PAGE]

    rows: list[list[dict]] = []
    for idx, project in enumerate(page_projects):
        global_idx = start + idx
        mark = "✅" if (not use_whole and project["id"] in selected) else "⬜"
        label = f"{mark} {project['name'][:28]}"
        rows.append([{"text": label, "callback_data": f"p:t:{global_idx}"}])

    nav_row: list[dict] = []
    if page > 0:
        nav_row.append({"text": "◀️", "callback_data": "p:pg:-1"})
    if start + PROJECTS_PER_PAGE < len(projects):
        nav_row.append({"text": "▶️", "callback_data": "p:pg:1"})
    if nav_row:
        rows.append(nav_row)

    rows.append(
        [
            {"text": "✅ Выбрать все", "callback_data": "p:a"},
            {"text": "🌐 Весь воркспейс", "callback_data": "p:w"},
        ]
    )
    rows.append([{"text": "Далее →", "callback_data": "p:n"}])
    rows.append([{"text": "✖️ Отмена", "callback_data": "p:x"}])
    return {"inline_keyboard": rows}


def _build_period_keyboard() -> dict:
    return {
        "inline_keyboard": [
            [
                {"text": "День", "callback_data": "d:1"},
                {"text": "Неделя", "callback_data": "d:7"},
                {"text": "Месяц", "callback_data": "d:30"},
            ],
            [{"text": "◀️ Назад", "callback_data": "d:b"}],
        ]
    }


def _build_confirm_keyboard() -> dict:
    return {
        "inline_keyboard": [
            [{"text": "✅ Сгенерировать отчёт", "callback_data": "g:go"}],
            [{"text": "◀️ Изменить период", "callback_data": "g:b"}],
            [{"text": "✖️ Отмена", "callback_data": "g:x"}],
        ]
    }


def show_main_menu(chat_id: int, text: str | None = None) -> None:
    send_message(
        chat_id,
        text or "Выберите действие:",
        reply_markup=MAIN_KEYBOARD,
    )


def show_help(chat_id: int) -> None:
    send_message(
        chat_id,
        "📊 Новый отчёт — пошаговый мастер:\n"
        "1) выбор проектов\n"
        "2) период (день / неделя / месяц)\n"
        "3) генерация PDF и отправка в чат\n\n"
        "📝 Новая задача — создание задачи в Project Office:\n"
        "опишите задачу текстом (проект, исполнитель, срок).\n"
        "Бот уточнит детали и создаст задачу в Plane.\n\n"
        "Команды: /report, /task, /menu",
        reply_markup=MAIN_KEYBOARD,
    )


def start_report_wizard(chat_id: int, user) -> None:
    workspaces = get_user_workspaces(user)
    if not workspaces:
        send_message(chat_id, "У вас нет доступных воркспейсов в Plane.", reply_markup=MAIN_KEYBOARD)
        return

    if len(workspaces) == 1:
        _start_projects_step(chat_id, user, workspaces[0])
        return

    rows = [[{"text": ws.name[:40], "callback_data": f"w:{idx}"}] for idx, ws in enumerate(workspaces)]
    rows.append([{"text": "✖️ Отмена", "callback_data": "w:x"}])
    save_session(
        chat_id,
        {
            "mode": "report",
            "step": "workspace",
            "workspaces": [{"id": str(ws.id), "slug": ws.slug, "name": ws.name} for ws in workspaces],
        },
    )
    send_message(chat_id, "Выберите воркспейс:", reply_markup={"inline_keyboard": rows})


def _start_projects_step(chat_id: int, user, workspace: Workspace) -> None:
    projects = get_workspace_projects(user, workspace)
    session = {
        "mode": "report",
        "step": "projects",
        "workspace_id": str(workspace.id),
        "workspace_slug": workspace.slug,
        "workspace_name": workspace.name,
        "projects": [{"id": str(p.id), "name": p.name} for p in projects],
        "selected_ids": [],
        "use_whole_workspace": True,
        "page": 0,
    }
    save_session(chat_id, session)
    text = (
        f"📁 Проекты — {workspace.name}\n\n"
        "Выберите проекты или «Весь воркспейс».\n"
        f"Сейчас: {_projects_summary(session)}"
    )
    send_message(chat_id, text, reply_markup=_build_projects_keyboard(session))


def _show_projects(chat_id: int, message_id: int | None = None) -> None:
    session = get_session(chat_id)
    if not session:
        show_main_menu(chat_id)
        return
    text = (
        f"📁 Проекты — {session.get('workspace_name', '')}\n\n"
        "Выберите проекты или «Весь воркспейс».\n"
        f"Сейчас: {_projects_summary(session)}"
    )
    keyboard = _build_projects_keyboard(session)
    if message_id:
        edit_message(chat_id, message_id, text, keyboard)
    else:
        send_message(chat_id, text, keyboard)


def _show_period(chat_id: int, message_id: int) -> None:
    session = get_session(chat_id) or {}
    text = (
        f"📅 Период\n\n"
        f"Проекты: {_projects_summary(session)}\n"
        "Выберите период отчёта:"
    )
    edit_message(chat_id, message_id, text, _build_period_keyboard())


def _show_confirm(chat_id: int, message_id: int, days: int) -> None:
    period_to = date.today()
    period_from = period_to - timedelta(days=days - 1)
    session = get_session(chat_id) or {}
    session["period_days"] = days
    session["period_from"] = period_from.isoformat()
    session["period_to"] = period_to.isoformat()
    session["step"] = "confirm"
    save_session(chat_id, session)

    label = {1: "День", 7: "Неделя", 30: "Месяц"}.get(days, f"{days} дн.")
    text = (
        "📋 Подтверждение\n\n"
        f"Воркспейс: {session.get('workspace_name')}\n"
        f"Проекты: {_projects_summary(session)}\n"
        f"Период: {period_from} — {period_to} ({label})\n\n"
        "Нажмите «Сгенерировать отчёт». Генерация займёт 1–3 минуты."
    )
    edit_message(chat_id, message_id, text, _build_confirm_keyboard())


def _launch_generation(chat_id: int, link: UserTelegramLink) -> None:
    session = get_session(chat_id)
    if not session:
        send_message(chat_id, "Сессия истекла. Нажмите «📊 Новый отчёт».", reply_markup=MAIN_KEYBOARD)
        return

    use_whole = session.get("use_whole_workspace", True)
    selected = session.get("selected_ids") or []
    if not use_whole and not selected:
        send_message(chat_id, "Выберите хотя бы один проект или «Весь воркспейс».", reply_markup=MAIN_KEYBOARD)
        return

    send_message(
        chat_id,
        "⏳ Генерирую отчёт… Это может занять несколько минут.",
        reply_markup=MAIN_KEYBOARD,
    )
    from plane.bgtasks.telegram_report_task import run_telegram_report_generation

    kwargs = {
        "chat_id": chat_id,
        "user_id": str(link.user_id),
        "workspace_id": session["workspace_id"],
        "period_from": session["period_from"],
        "period_to": session["period_to"],
        "project_ids": selected if not use_whole else None,
        "use_whole_workspace": use_whole,
        "title": "",
    }
    threading.Thread(target=run_telegram_report_generation, kwargs=kwargs, daemon=True).start()


def handle_callback(callback: dict) -> None:
    data = callback.get("data") or ""
    callback_id = callback.get("id")
    message = callback.get("message") or {}
    chat_id = (message.get("chat") or {}).get("id")
    message_id = message.get("message_id")
    if chat_id is None or message_id is None:
        return

    link = get_link(chat_id)
    if not link:
        answer_callback(callback_id, "Сначала привяжите аккаунт через Plane")
        return

    session = get_session(chat_id) or {}

    if handle_task_callback(
        data,
        chat_id,
        message_id,
        link,
        session,
        callback_id,
        answer_callback=answer_callback,
        edit_message=edit_message,
        send_message=send_message,
        save_session=save_session,
        clear_session=clear_session,
        show_main_menu=show_main_menu,
        MAIN_KEYBOARD=MAIN_KEYBOARD,
    ):
        return

    if data.startswith("w:"):
        answer_callback(callback_id)
        code = data[2:]
        if code == "x":
            clear_session(chat_id)
            edit_message(chat_id, message_id, "Отменено.", {"inline_keyboard": []})
            show_main_menu(chat_id)
            return
        session = get_session(chat_id) or {}
        workspaces = session.get("workspaces") or []
        try:
            idx = int(code)
            ws_data = workspaces[idx]
        except (ValueError, IndexError):
            return
        workspace = Workspace.objects.filter(id=ws_data["id"]).first()
        if not workspace:
            return
        _start_projects_step(chat_id, link.user, workspace)
        edit_message(chat_id, message_id, f"Воркспейс: {workspace.name}", {"inline_keyboard": []})
        return

    if data.startswith("p:"):
        session = get_session(chat_id)
        if not session:
            answer_callback(callback_id, "Сессия истекла")
            show_main_menu(chat_id)
            return

        action = data[2:]
        if action == "x":
            clear_session(chat_id)
            answer_callback(callback_id)
            edit_message(chat_id, message_id, "Отменено.", {"inline_keyboard": []})
            show_main_menu(chat_id)
            return
        if action == "n":
            if not session.get("use_whole_workspace") and not session.get("selected_ids"):
                answer_callback(callback_id, "Выберите проекты")
                return
            session["step"] = "period"
            save_session(chat_id, session)
            answer_callback(callback_id)
            _show_period(chat_id, message_id)
            return
        if action == "a":
            session["use_whole_workspace"] = False
            session["selected_ids"] = [p["id"] for p in session.get("projects") or []]
            save_session(chat_id, session)
            answer_callback(callback_id, "Все проекты выбраны")
            _show_projects(chat_id, message_id)
            return
        if action == "w":
            session["use_whole_workspace"] = True
            session["selected_ids"] = []
            save_session(chat_id, session)
            answer_callback(callback_id, "Весь воркспейс")
            _show_projects(chat_id, message_id)
            return
        if action.startswith("t:"):
            try:
                idx = int(action[2:])
            except ValueError:
                return
            projects = session.get("projects") or []
            if idx < 0 or idx >= len(projects):
                return
            session["use_whole_workspace"] = False
            pid = projects[idx]["id"]
            selected = set(session.get("selected_ids") or [])
            if pid in selected:
                selected.remove(pid)
            else:
                selected.add(pid)
            session["selected_ids"] = list(selected)
            save_session(chat_id, session)
            answer_callback(callback_id)
            _show_projects(chat_id, message_id)
            return
        if action.startswith("pg:"):
            try:
                delta = int(action[3:])
            except ValueError:
                return
            session["page"] = max(0, session.get("page", 0) + delta)
            save_session(chat_id, session)
            answer_callback(callback_id)
            _show_projects(chat_id, message_id)
            return

    if data.startswith("d:"):
        session = get_session(chat_id)
        if not session:
            answer_callback(callback_id, "Сессия истекла")
            return
        code = data[2:]
        if code == "b":
            session["step"] = "projects"
            save_session(chat_id, session)
            answer_callback(callback_id)
            _show_projects(chat_id, message_id)
            return
        try:
            days = int(code)
        except ValueError:
            return
        answer_callback(callback_id)
        _show_confirm(chat_id, message_id, days)
        return

    if data.startswith("g:"):
        code = data[2:]
        if code == "x":
            clear_session(chat_id)
            answer_callback(callback_id)
            edit_message(chat_id, message_id, "Отменено.", {"inline_keyboard": []})
            show_main_menu(chat_id)
            return
        if code == "b":
            session = get_session(chat_id) or {}
            session["step"] = "period"
            save_session(chat_id, session)
            answer_callback(callback_id)
            _show_period(chat_id, message_id)
            return
        if code == "go":
            answer_callback(callback_id, "Запускаю генерацию…")
            edit_message(chat_id, message_id, "⏳ Генерация отчёта запущена…", {"inline_keyboard": []})
            _launch_generation(chat_id, link)
            return


def handle_message(message: dict) -> None:
    text = (message.get("text") or "").strip()
    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    if chat_id is None or not text:
        return

    if text.startswith("/start"):
        parts = text.split(maxsplit=1)
        if len(parts) < 2:
            link = get_link(chat_id)
            if link:
                show_main_menu(
                    chat_id,
                    f"Аккаунт привязан: {link.user.email}\n\n"
                    "📊 Новый отчёт или 📝 Новая задача в Project Office.",
                )
            else:
                send_message(chat_id, "Отправьте команду с токеном: /start <ваш_код>\nТокен создаётся в Plane.")
        return

    if text in ("/menu", "/help") or text.lower() == "ℹ️ помощь":
        show_help(chat_id)
        return

    link = get_link(chat_id)
    if not link:
        send_message(chat_id, "Аккаунт не привязан. Создайте токен в Plane и отправьте /start <код>.")
        return

    if _is_report_trigger(text):
        start_report_wizard(chat_id, link.user)
        return

    if _is_task_trigger(text):
        start_task_wizard(
            chat_id,
            link.user,
            send_message=send_message,
            save_session=save_session,
            clear_session=clear_session,
            MAIN_KEYBOARD=MAIN_KEYBOARD,
        )
        return

    session = get_session(chat_id)
    if session and handle_task_message(
        chat_id,
        text,
        link,
        session,
        send_message=send_message,
        save_session=save_session,
        get_session=get_session,
        show_main_menu=show_main_menu,
        clear_session=clear_session,
        MAIN_KEYBOARD=MAIN_KEYBOARD,
    ):
        return

    show_main_menu(chat_id, "Используйте «📊 Новый отчёт», «📝 Новая задача» или /help.")


def handle_telegram_update(update: dict) -> None:
    callback = update.get("callback_query")
    if callback:
        handle_callback(callback)
        return
    message = update.get("message") or update.get("edited_message")
    if message:
        handle_message(message)
