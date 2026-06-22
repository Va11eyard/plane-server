# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import logging
import threading
from typing import Any

from plane.db.models import GitHubCommitImportLog
from plane.utils.github_sync_orchestrator import (
    CommitPreview,
    ScanResult,
    can_sync_github_tasks,
    execute_import_log,
    scan_all_repos,
    skip_import_log,
)

logger = logging.getLogger("plane.telegram")

SYNC_TRIGGERS = {
    "/sync",
    "🔄 обновить задачи",
    "обновить задачи",
}


def is_sync_trigger(text: str) -> bool:
    normalized = text.strip().lower()
    return normalized in SYNC_TRIGGERS or normalized.startswith("/sync")


def _preview_summary(previews: list[CommitPreview]) -> str:
    if not previews:
        return "Нет новых коммитов для импорта."
    lines = [f"Найдено {len(previews)} новых коммитов:\n"]
    for p in previews:
        lines.append(
            f"📦 {p.repo_label}\n"
            f"• {p.short_sha} — {p.message[:80]}\n"
            f"  {p.section_count} секций, {p.task_count} задач"
        )
    return "\n\n".join(lines)


def _build_preview_keyboard(previews: list[CommitPreview]) -> dict:
    rows: list[list[dict]] = []
    if len(previews) == 1:
        rows.append([{"text": "✅ Импортировать", "callback_data": "gh:go:0"}])
        rows.append([{"text": "⏭ Пропустить", "callback_data": "gh:skip:0"}])
    else:
        rows.append([{"text": "✅ Импортировать все", "callback_data": "gh:all"}])
        rows.append([{"text": "📋 По одному", "callback_data": "gh:one"}])
    rows.append([{"text": "✖️ Отмена", "callback_data": "gh:x"}])
    return {"inline_keyboard": rows}


def _build_single_keyboard(index: int, total: int) -> dict:
    rows = [
        [{"text": "✅ Импорт", "callback_data": f"gh:go:{index}"}],
        [{"text": "⏭ Пропустить", "callback_data": f"gh:skip:{index}"}],
    ]
    if index + 1 < total:
        rows.append([{"text": "Следующий →", "callback_data": f"gh:next:{index + 1}"}])
    rows.append([{"text": "✖️ Отмена", "callback_data": "gh:x"}])
    return {"inline_keyboard": rows}


def _single_preview_text(preview: CommitPreview, index: int, total: int) -> str:
    return (
        f"Коммит {index + 1}/{total}\n\n"
        f"📦 {preview.repo_label}\n"
        f"🔖 {preview.short_sha}: {preview.message}\n"
        f"📁 {preview.section_count} секций, {preview.task_count} задач\n\n"
        f"Эпик: {preview.plan.get('epic_title', '—')}"
    )


def _run_scan_and_respond(
    chat_id: int,
    user,
    *,
    send_message,
    save_session,
    show_main_menu,
    get_main_keyboard,
) -> None:
    try:
        results = scan_all_repos(user, GitHubCommitImportLog.TriggerSource.TELEGRAM)
        previews: list[CommitPreview] = []
        errors: list[str] = []
        for result in results:
            if result.error:
                errors.append(f"{result.repo_sync.full_name}: {result.error}")
            previews.extend(result.previews)

        if errors and not previews:
            send_message(chat_id, "❌ " + "\n".join(errors), reply_markup=get_main_keyboard(user))
            return

        if not previews:
            msg = "✅ Все репозитории актуальны."
            if errors:
                msg += "\n\n⚠️ " + "\n".join(errors)
            send_message(chat_id, msg, reply_markup=get_main_keyboard(user))
            return

        session: dict[str, Any] = {
            "mode": "github_sync",
            "step": "preview",
            "previews": [
                {
                    "log_id": p.log_id,
                    "short_sha": p.short_sha,
                    "message": p.message,
                    "repo_label": p.repo_label,
                    "section_count": p.section_count,
                    "task_count": p.task_count,
                    "plan": p.plan,
                }
                for p in previews
            ],
            "preview_index": 0,
        }
        save_session(chat_id, session)
        text = _preview_summary(previews)
        if errors:
            text += "\n\n⚠️ " + "\n".join(errors)
        send_message(chat_id, text, reply_markup=_build_preview_keyboard(previews))
    except Exception:
        logger.exception("GitHub sync scan failed")
        send_message(chat_id, "❌ Ошибка сканирования GitHub.", reply_markup=get_main_keyboard(user))


def start_github_sync(
    chat_id: int,
    user,
    *,
    send_message,
    save_session,
    show_main_menu,
    get_main_keyboard,
) -> None:
    if not can_sync_github_tasks(user):
        send_message(chat_id, "Синхронизация GitHub доступна только администраторам.", reply_markup=get_main_keyboard(user))
        return

    send_message(chat_id, "⏳ Сканирую репозитории GitHub…", reply_markup=get_main_keyboard(user))
    threading.Thread(
        target=_run_scan_and_respond,
        kwargs={
            "chat_id": chat_id,
            "user": user,
            "send_message": send_message,
            "save_session": save_session,
            "show_main_menu": show_main_menu,
            "get_main_keyboard": get_main_keyboard,
        },
        daemon=True,
    ).start()


def _rebuild_previews_from_session(session: dict[str, Any]) -> list[CommitPreview]:
    items = session.get("previews") or []
    return [
        CommitPreview(
            repo_sync_id="",
            repo_label=item.get("repo_label", ""),
            sha="",
            short_sha=item.get("short_sha", ""),
            message=item.get("message", ""),
            url="",
            plan=item.get("plan") or {},
            section_count=item.get("section_count", 0),
            task_count=item.get("task_count", 0),
            log_id=item.get("log_id"),
        )
        for item in items
    ]


def handle_github_sync_callback(
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
    get_main_keyboard,
) -> bool:
    if not data.startswith("gh:"):
        return False

    if session.get("mode") != "github_sync":
        answer_callback(callback_id, "Сессия истекла")
        return True

    user = link.user
    action = data[3:]
    previews = _rebuild_previews_from_session(session)

    if action == "x":
        clear_session(chat_id)
        answer_callback(callback_id)
        edit_message(chat_id, message_id, "Отменено.", {"inline_keyboard": []})
        show_main_menu(chat_id, user=user)
        return True

    if action == "all":
        answer_callback(callback_id, "Импортирую…")
        lines = []
        for item in session.get("previews") or []:
            log_id = item.get("log_id")
            if not log_id:
                continue
            ok, msg = execute_import_log(log_id, user)
            prefix = "✅" if ok else "❌"
            lines.append(f"{prefix} {item.get('short_sha')}: {msg}")
        clear_session(chat_id)
        edit_message(chat_id, message_id, "\n".join(lines) or "Готово.", {"inline_keyboard": []})
        show_main_menu(chat_id, user=user)
        return True

    if action == "one":
        session["step"] = "single"
        session["preview_index"] = 0
        save_session(chat_id, session)
        answer_callback(callback_id)
        if previews:
            edit_message(
                chat_id,
                message_id,
                _single_preview_text(previews[0], 0, len(previews)),
                _build_single_keyboard(0, len(previews)),
            )
        return True

    if action.startswith("next:"):
        try:
            idx = int(action[5:])
        except ValueError:
            return True
        session["preview_index"] = idx
        save_session(chat_id, session)
        answer_callback(callback_id)
        if 0 <= idx < len(previews):
            edit_message(
                chat_id,
                message_id,
                _single_preview_text(previews[idx], idx, len(previews)),
                _build_single_keyboard(idx, len(previews)),
            )
        return True

    if action.startswith("go:"):
        try:
            idx = int(action[3:])
        except ValueError:
            return True
        items = session.get("previews") or []
        if idx < 0 or idx >= len(items):
            answer_callback(callback_id, "Не найдено")
            return True
        log_id = items[idx].get("log_id")
        ok, msg = execute_import_log(log_id, user) if log_id else (False, "Нет log_id")
        answer_callback(callback_id)
        if len(items) == 1 or session.get("step") != "single":
            clear_session(chat_id)
            edit_message(
                chat_id,
                message_id,
                f"{'✅' if ok else '❌'} {items[idx].get('short_sha')}: {msg}",
                {"inline_keyboard": []},
            )
            show_main_menu(chat_id, user=user)
        else:
            items.pop(idx)
            session["previews"] = items
            if not items:
                clear_session(chat_id)
                edit_message(chat_id, message_id, "Все коммиты обработаны.", {"inline_keyboard": []})
                show_main_menu(chat_id, user=user)
            else:
                new_idx = min(idx, len(items) - 1)
                session["preview_index"] = new_idx
                save_session(chat_id, session)
                previews = _rebuild_previews_from_session(session)
                edit_message(
                    chat_id,
                    message_id,
                    _single_preview_text(previews[new_idx], new_idx, len(previews)),
                    _build_single_keyboard(new_idx, len(previews)),
                )
        return True

    if action.startswith("skip:"):
        try:
            idx = int(action[5:])
        except ValueError:
            return True
        items = session.get("previews") or []
        if 0 <= idx < len(items) and items[idx].get("log_id"):
            skip_import_log(items[idx]["log_id"])
        answer_callback(callback_id)
        if session.get("step") == "single" and len(items) > 1:
            items.pop(idx)
            session["previews"] = items
            if not items:
                clear_session(chat_id)
                edit_message(chat_id, message_id, "Все коммиты пропущены.", {"inline_keyboard": []})
                show_main_menu(chat_id, user=user)
            else:
                new_idx = min(idx, len(items) - 1)
                session["preview_index"] = new_idx
                save_session(chat_id, session)
                previews = _rebuild_previews_from_session(session)
                edit_message(
                    chat_id,
                    message_id,
                    _single_preview_text(previews[new_idx], new_idx, len(previews)),
                    _build_single_keyboard(new_idx, len(previews)),
                )
        else:
            clear_session(chat_id)
            edit_message(chat_id, message_id, "Пропущено.", {"inline_keyboard": []})
            show_main_menu(chat_id, user=user)
        return True

    return True
