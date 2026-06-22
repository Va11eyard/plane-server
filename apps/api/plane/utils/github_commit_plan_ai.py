# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import json
import logging
import re
from collections import defaultdict
from typing import Any

from plane.app.views.external.base import get_llm_config, get_llm_response
from plane.utils.github_commit_import_service import validate_plan

logger = logging.getLogger("plane.github")

PLAN_INSTRUCTION = (
    "Ты помощник менеджера. По коммиту GitHub сформируй структуру задач для Plane. "
    "Ответь ТОЛЬКО валидным JSON без markdown."
)

PLAN_SCHEMA = """{
  "epic_title": "краткое название эпика из commit message",
  "epic_summary": "1-3 предложения что сделано",
  "sections": [
    {
      "title": "Логическая секция (модуль/область)",
      "tasks": ["конкретная подзадача", "..."]
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


def _fallback_plan_from_files(commit_message: str, files: list[dict[str, str]]) -> dict[str, Any]:
    title = (commit_message or "GitHub commit").split("\n", 1)[0].strip()[:255]
    by_area: dict[str, list[str]] = defaultdict(list)
    for f in files:
        path = f.get("filename") or ""
        if not path:
            continue
        parts = path.split("/")
        area = parts[0] if len(parts) > 1 else "root"
        status = f.get("status") or "modified"
        by_area[area].append(f"{status}: {path}")

    sections = []
    for area, items in sorted(by_area.items()):
        sections.append(
            {
                "title": area,
                "tasks": items[:15],
            }
        )
    if not sections:
        sections = [{"title": "Изменения", "tasks": [title]}]
    return {
        "epic_title": title,
        "epic_summary": commit_message[:2000] if commit_message else title,
        "sections": sections,
    }


def build_commit_plan(
    *,
    commit_message: str,
    files: list[dict[str, str]],
    use_llm: bool = True,
) -> tuple[dict[str, Any] | None, str | None]:
    api_key, model, provider = get_llm_config()
    parsed: dict[str, Any] | None = None

    if use_llm and api_key and model and provider:
        files_text = "\n".join(
            f"- {f.get('status', '?')}: {f.get('filename', '')} ({f.get('changes', '?')} changes)" for f in files[:80]
        )
        prompt = f"""Commit message:
{commit_message}

Изменённые файлы:
{files_text or '—'}

Сгруппируй изменения в 3-8 секций и 5-40 конкретных подзадач на русском.
Схема ответа:
{PLAN_SCHEMA}
"""
        text, error = get_llm_response(PLAN_INSTRUCTION, prompt, api_key, model, provider)
        if error:
            logger.warning("Commit plan LLM error: %s", error)
        else:
            parsed = _extract_json(text or "")

    if not parsed:
        parsed = _fallback_plan_from_files(commit_message, files)

    return validate_plan(parsed)
