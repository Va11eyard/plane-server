# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from unittest.mock import Mock

import pytest

from plane.utils.github_commit_import_service import (
    root_marker,
    short_sha,
    validate_plan,
)
from plane.utils.github_commit_plan_ai import MAX_PLAN_TASKS, _cap_plan_size, _fallback_plan_from_files
from plane.utils.github_sync_orchestrator import can_sync_github_tasks, get_github_sync_importer_emails
from plane.utils.telegram_github_sync_bot import is_sync_trigger


@pytest.mark.unit
class TestGitHubImportService:
    def test_short_sha(self):
        assert short_sha("616bfbc2cc1e6919c87f201bbdff63128ffe9bdf") == "616bfbc2"

    def test_root_marker(self):
        assert root_marker("616bfbc2cc1e6919c87f201bbdff63128ffe9bdf") == "[GitHub 616bfbc2]"

    def test_validate_plan_requires_epic_title(self):
        plan, error = validate_plan({"sections": []})
        assert plan is None
        assert error

    def test_validate_plan_normalizes_sections(self):
        plan, error = validate_plan(
            {
                "epic_title": "feat: test commit",
                "sections": [{"title": "API", "tasks": ["Add endpoint", ""]}],
            }
        )
        assert error is None
        assert plan is not None
        assert plan["epic_title"] == "feat: test commit"
        assert len(plan["sections"]) == 1
        assert plan["sections"][0]["tasks"] == ["Add endpoint"]

    def test_validate_plan_empty_sections_gets_default(self):
        plan, error = validate_plan({"epic_title": "Only title"})
        assert error is None
        assert plan is not None
        assert len(plan["sections"]) >= 1


@pytest.mark.unit
class TestGitHubPlanAI:
    def test_fallback_plan_from_files(self):
        files = [
            {"filename": "apps/api/views.py", "status": "modified"},
            {"filename": "README.md", "status": "added"},
        ]
        plan = _fallback_plan_from_files("feat: add views", files)
        assert plan["epic_title"] == "feat: add views"
        assert len(plan["sections"]) >= 1
        assert any(s["title"] == "apps" for s in plan["sections"])

    def test_cap_plan_size(self):
        plan = _cap_plan_size(
            {
                "epic_title": "test",
                "sections": [
                    {"title": "A", "tasks": [f"t{i}" for i in range(8)]},
                    {"title": "B", "tasks": [f"t{i}" for i in range(8)]},
                ],
            }
        )
        total_tasks = sum(len(s["tasks"]) for s in plan["sections"])
        assert len(plan["sections"]) <= 3
        assert total_tasks <= MAX_PLAN_TASKS


@pytest.mark.unit
class TestGitHubSyncPermissions:
    def test_default_importer_email(self):
        assert "dimash@galamat.com" in get_github_sync_importer_emails()

    def test_can_sync_only_importer(self, monkeypatch):
        monkeypatch.delenv("GITHUB_SYNC_IMPORTER_EMAILS", raising=False)
        assert can_sync_github_tasks(Mock(email="dimash@galamat.com")) is True
        assert can_sync_github_tasks(Mock(email="admin@galamat.com")) is False


@pytest.mark.unit
class TestTelegramGitHubSync:
    def test_is_sync_trigger(self):
        assert is_sync_trigger("🔄 Обновить задачи")
        assert is_sync_trigger("/sync")
        assert not is_sync_trigger("новый отчёт")
