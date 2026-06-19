# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import json
import logging
import re
from datetime import date
from typing import Any

from plane.app.views.external.base import get_llm_config, get_llm_response
from plane.utils.telegram_task_service import (
    CONFIDENCE_THRESHOLD,
    match_assignee,
    match_project,
    merge_draft,
    parse_target_date,
)

logger = logging.getLogger("plane.telegram")

TASK_PARSE_INSTRUCTION = (
    "Ты ассистент менеджера в Plane (Project Office). "
    "Проанализируй сообщение пользователя и помоги создать задачу. "
    "Ответь ТОЛЬКО валидным JSON без markdown."
)

TASK_PARSE_SCHEMA = """{
  "status": "ready | clarify | ambiguous",
  "title": "краткое название задачи или пустая строка",
  "description": "подробности или пустая строка",
  "project_hint": "подсказка проекта или null",
  "assignee_hint": "имя или email исполнителя или null",
  "target_date_hint": "дата/срок или null",
  "missing_fields": ["title", "project", "assignee", "target_date"],
  "confidence": 0.0,
  "question": "вопрос пользователю на русском если нужно уточнение",
  "interpretations": [
    {
      "title": "...",
      "description": "...",
      "project_hint": "...",
      "assignee_hint": "...",
      "target_date_hint": "..."
    }
  ]
}"""


def _extract_json(text: str) -> dict[str, Any] | None:
    if not text:
        return None
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{[\s\S]*\}", text)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return None


def _build_prompt(
    *,
    user_message: str,
    projects: list[dict[str, str]],
    members_by_project: dict[str, list[dict[str, str]]],
    conversation_history: list[dict[str, str]],
    draft: dict[str, Any],
    asked_target_date: bool,
) -> str:
    projects_text = "\n".join(f"- {p['name']} (id: {p['id']})" for p in projects) or "—"
    members_lines: list[str] = []
    for project in projects:
        members = members_by_project.get(project["id"], [])
        if members:
            names = ", ".join(m["display_name"] or m["email"] for m in members)
            members_lines.append(f"  {project['name']}: {names}")
    members_text = "\n".join(members_lines) or "—"

    history_text = ""
    for item in conversation_history[-8:]:
        role = item.get("role", "user")
        content = item.get("content", "")
        history_text += f"{role}: {content}\n"

    draft_text = json.dumps(draft, ensure_ascii=False) if draft else "{}"
    today = date.today().isoformat()

    return f"""Сегодня: {today}
Уже известно о задаче (draft): {draft_text}
Уже спрашивали про срок: {asked_target_date}

Доступные проекты:
{projects_text}

Участники по проектам:
{members_text}

История диалога:
{history_text or "—"}

Новое сообщение пользователя:
{user_message}

Правила:
1. Обязательные поля: title (суть), project, assignee.
2. target_date желателен; если не указан — добавь в missing_fields только если срок важен из контекста.
3. status=clarify если не хватает обязательных полей — задай один понятный вопрос в question.
4. status=ambiguous если смысл задачи неясен — предложи 2-3 interpretations.
5. status=ready если title, project_hint и assignee_hint можно однозначно понять.
6. Не выдумывай проекты и людей вне списков.

Схема ответа:
{TASK_PARSE_SCHEMA}
"""


def _fallback_parse(user_message: str, projects: list[dict[str, str]]) -> dict[str, Any]:
    text = user_message.strip()
    project_hint = None
    assignee_hint = None
    title = text

    m = re.search(r"(?:в|для проекта)\s+([^,:]+?)(?:\s+для|\s*[,:]|$)", text, re.IGNORECASE)
    if m:
        project_hint = m.group(1).strip()

    m = re.search(r"для\s+([А-Яа-яA-Za-zЁё]+)", text, re.IGNORECASE)
    if m:
        assignee_hint = m.group(1).strip()

    missing: list[str] = []
    if not title or len(title) < 3:
        missing.append("title")
    if not project_hint and not match_project(text, projects)[0]:
        missing.append("project")
    if not assignee_hint:
        missing.append("assignee")

    status = "clarify" if missing else "ready"
    question = ""
    if missing:
        parts = []
        if "title" in missing:
            parts.append("что именно нужно сделать")
        if "project" in missing:
            parts.append("в каком проекте")
        if "assignee" in missing:
            parts.append("кто будет делать")
        question = "Уточните, пожалуйста: " + ", ".join(parts) + "?"

    return {
        "status": status,
        "title": title[:255],
        "description": "",
        "project_hint": project_hint,
        "assignee_hint": assignee_hint,
        "target_date_hint": None,
        "missing_fields": missing,
        "confidence": 0.5,
        "question": question,
        "interpretations": [],
    }


def resolve_parsed_task(
    *,
    parsed: dict[str, Any],
    projects: list[dict[str, str]],
    members_by_project: dict[str, list[dict[str, str]]],
    draft: dict[str, Any],
    asked_target_date: bool,
) -> dict[str, Any]:
    merged_hints = merge_draft(
        {},
        {
            "title": parsed.get("title"),
            "description": parsed.get("description"),
        },
    )
    merged_hints.update({k: v for k, v in (draft or {}).items() if v})

    project_data = None
    project_confidence = 0.0
    if draft.get("project_id"):
        project_data = next((p for p in projects if p["id"] == draft["project_id"]), None)
        project_confidence = 1.0 if project_data else 0.0
    if not project_data and parsed.get("project_hint"):
        project_data, project_confidence = match_project(parsed["project_hint"], projects)

    members: list[dict[str, str]] = []
    if project_data:
        members = members_by_project.get(project_data["id"], [])

    assignee_data = None
    assignee_confidence = 0.0
    if draft.get("assignee_id"):
        assignee_data = next((m for m in members if m["id"] == draft["assignee_id"]), None)
        if not assignee_data:
            for ms in members_by_project.values():
                assignee_data = next((m for m in ms if m["id"] == draft["assignee_id"]), None)
                if assignee_data:
                    break
        assignee_confidence = 1.0 if assignee_data else 0.0
    if not assignee_data and parsed.get("assignee_hint") and members:
        assignee_data, assignee_confidence = match_assignee(parsed["assignee_hint"], members)

    target_date = None
    if draft.get("target_date"):
        target_date = parse_target_date(draft["target_date"])
    if not target_date and parsed.get("target_date_hint"):
        target_date = parse_target_date(parsed["target_date_hint"])

    title = (parsed.get("title") or merged_hints.get("title") or "").strip()
    description = (parsed.get("description") or merged_hints.get("description") or "").strip()

    missing_fields: list[str] = list(parsed.get("missing_fields") or [])
    if not title:
        if "title" not in missing_fields:
            missing_fields.append("title")
    if not project_data or project_confidence < CONFIDENCE_THRESHOLD:
        if "project" not in missing_fields:
            missing_fields.append("project")
    if not assignee_data or assignee_confidence < CONFIDENCE_THRESHOLD:
        if "assignee" not in missing_fields:
            missing_fields.append("assignee")
    if not target_date and not asked_target_date:
        if "target_date" not in missing_fields:
            missing_fields.append("target_date")

    status = parsed.get("status") or "clarify"
    if status == "ready" and missing_fields:
        required_missing = [f for f in missing_fields if f in ("title", "project", "assignee")]
        if required_missing:
            status = "clarify"
        elif "target_date" in missing_fields and not asked_target_date:
            status = "clarify"
        else:
            status = "ready"
            missing_fields = [f for f in missing_fields if f != "target_date"]
    if status == "ambiguous" and not parsed.get("interpretations"):
        status = "clarify"

    new_draft: dict[str, Any] = {}
    if title:
        new_draft["title"] = title[:255]
    if description:
        new_draft["description"] = description
    if project_data and project_confidence >= CONFIDENCE_THRESHOLD:
        new_draft["project_id"] = project_data["id"]
        new_draft["project_name"] = project_data["name"]
    if assignee_data and assignee_confidence >= CONFIDENCE_THRESHOLD:
        new_draft["assignee_id"] = assignee_data["id"]
        new_draft["assignee_name"] = assignee_data.get("display_name") or assignee_data.get("email")
    if target_date:
        new_draft["target_date"] = target_date.isoformat()

    member_options = members
    if not member_options and new_draft.get("project_id"):
        member_options = members_by_project.get(new_draft["project_id"], [])

    return {
        "status": status,
        "question": parsed.get("question") or "",
        "interpretations": parsed.get("interpretations") or [],
        "missing_fields": missing_fields,
        "draft": merge_draft(draft, new_draft),
        "project_options": projects,
        "member_options": member_options,
        "confidence": float(parsed.get("confidence") or 0),
    }


def parse_task_message(
    *,
    user_message: str,
    projects: list[dict[str, str]],
    members_by_project: dict[str, list[dict[str, str]]],
    conversation_history: list[dict[str, str]],
    draft: dict[str, Any] | None = None,
    asked_target_date: bool = False,
) -> dict[str, Any]:
    draft = draft or {}
    api_key, model, provider = get_llm_config()
    parsed: dict[str, Any] | None = None

    if api_key and model and provider:
        prompt = _build_prompt(
            user_message=user_message,
            projects=projects,
            members_by_project=members_by_project,
            conversation_history=conversation_history,
            draft=draft,
            asked_target_date=asked_target_date,
        )
        text, error = get_llm_response(TASK_PARSE_INSTRUCTION, prompt, api_key, model, provider)
        if error:
            logger.warning("Task LLM error: %s", error)
        else:
            parsed = _extract_json(text or "")

    if not parsed:
        parsed = _fallback_parse(user_message, projects)

    return resolve_parsed_task(
        parsed=parsed,
        projects=projects,
        members_by_project=members_by_project,
        draft=draft,
        asked_target_date=asked_target_date,
    )
