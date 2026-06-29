# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from datetime import date
from uuid import uuid4

import pytest

from plane.db.models import Workspace, WorkspaceMember
from plane.utils.telegram_task_ai import resolve_parsed_task
from plane.utils.telegram_my_tasks_bot import format_my_tasks_message, is_my_tasks_trigger
from plane.utils.telegram_task_service import (
    IHEALTH_SLUG,
    can_create_task,
    match_assignee,
    match_project,
    merge_draft,
    parse_target_date,
)


PROJECTS = [
    {"id": "1", "name": "ODOS Check UP", "identifier": "ODOS"},
    {"id": "2", "name": "iHealth Reports", "identifier": "IHL"},
]

MEMBERS = [
    {"id": "u1", "display_name": "Димаш", "email": "dimash@galamat.com"},
    {"id": "u2", "display_name": "Жулдыз", "email": "zhuldyz@galamat.com"},
]


@pytest.mark.unit
class TestTelegramTaskMatching:
    def test_match_project_odos(self):
        project, score = match_project("ODOS", PROJECTS)
        assert project is not None
        assert project["name"] == "ODOS Check UP"
        assert score >= 0.8

    def test_match_project_partial(self):
        project, score = match_project("iHealth", PROJECTS)
        assert project is not None
        assert "iHealth" in project["name"]
        assert score >= 0.8

    def test_match_assignee_display_name(self):
        member, score = match_assignee("Димаш", MEMBERS)
        assert member is not None
        assert member["email"] == "dimash@galamat.com"
        assert score >= 0.8

    def test_match_assignee_email_local(self):
        member, score = match_assignee("zhuldyz", MEMBERS)
        assert member is not None
        assert member["id"] == "u2"

    def test_parse_target_date_friday(self):
        today = date(2026, 6, 10)  # Wednesday
        result = parse_target_date("к пятнице", today=today)
        assert result == date(2026, 6, 12)

    def test_parse_target_date_iso(self):
        result = parse_target_date("2026-06-15")
        assert result == date(2026, 6, 15)

    def test_merge_draft_preserves_existing(self):
        existing = {"project_id": "1", "project_name": "ODOS Check UP", "title": "Old title"}
        merged = merge_draft(existing, {"title": "New title", "assignee_id": "u1"})
        assert merged["project_id"] == "1"
        assert merged["title"] == "New title"
        assert merged["assignee_id"] == "u1"


@pytest.mark.unit
class TestResolveParsedTask:
    def test_ready_when_all_slots_present(self):
        parsed = {
            "status": "ready",
            "title": "Тест на выход из сессии",
            "description": "Добавить автотест",
            "project_hint": "ODOS",
            "assignee_hint": "Димаш",
            "target_date_hint": "2026-06-13",
            "missing_fields": [],
            "confidence": 0.95,
            "question": "",
            "interpretations": [],
        }
        members_map = {"1": MEMBERS, "2": MEMBERS}
        result = resolve_parsed_task(
            parsed=parsed,
            projects=PROJECTS,
            members_by_project=members_map,
            draft={},
            asked_target_date=False,
        )
        assert result["status"] == "ready"
        draft = result["draft"]
        assert draft["title"] == "Тест на выход из сессии"
        assert draft["project_name"] == "ODOS Check UP"
        assert draft["assignee_id"] == "u1"
        assert draft["target_date"] == "2026-06-13"

    def test_clarify_when_project_missing(self):
        parsed = {
            "status": "clarify",
            "title": "Сверстать PDF",
            "description": "",
            "project_hint": None,
            "assignee_hint": "Жулдыз",
            "target_date_hint": None,
            "missing_fields": ["project"],
            "confidence": 0.5,
            "question": "В каком проекте?",
            "interpretations": [],
        }
        result = resolve_parsed_task(
            parsed=parsed,
            projects=PROJECTS,
            members_by_project={"2": MEMBERS},
            draft={},
            asked_target_date=False,
        )
        assert result["status"] == "clarify"
        assert "project" in result["missing_fields"]


@pytest.mark.unit
class TestTelegramMyTasks:
    def test_is_my_tasks_trigger(self):
        assert is_my_tasks_trigger("📋 Мои задачи") is True
        assert is_my_tasks_trigger("/mytasks") is True
        assert is_my_tasks_trigger("новая задача") is False

    def test_format_my_tasks_message_empty(self):
        assert "нет активных" in format_my_tasks_message([])

    def test_format_my_tasks_message_with_total(self):
        class FakeProject:
            identifier = "ODOS"
            name = "ODOS Check UP"
            id = "p1"
            workspace = type("W", (), {"slug": "ihealth"})()

        class FakeState:
            name = "В работе"

        class FakeIssue:
            project = FakeProject()
            state = FakeState()
            sequence_id = 42
            name = "Поправить колонку"
            priority = "high"
            target_date = date(2026, 6, 15)
            id = "i1"

        text = format_my_tasks_message([FakeIssue()], total_count=3)
        assert "ODOS-42" in text
        assert "из 3" in text
        assert "Поправить колонку" in text


@pytest.mark.unit
@pytest.mark.django_db
class TestTelegramTaskPermissions:
    def test_can_create_task_member(self, create_user):
        workspace = Workspace.objects.create(
            name="iHealth",
            slug=IHEALTH_SLUG,
            id=uuid4(),
            owner=create_user,
        )
        WorkspaceMember.objects.create(workspace=workspace, member=create_user, role=15, is_active=True)
        assert can_create_task(create_user) is True

    def test_can_create_task_no_access(self, create_user):
        assert can_create_task(create_user) is False
