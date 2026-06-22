# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import pytest

from plane.utils.github_commit_import_service import (
    root_marker,
    short_sha,
    validate_plan,
)
from plane.utils.github_commit_plan_ai import _fallback_plan_from_files
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


@pytest.mark.unit
class TestTelegramGitHubSync:
    def test_is_sync_trigger(self):
        assert is_sync_trigger("🔄 Обновить задачи")
        assert is_sync_trigger("/sync")
        assert not is_sync_trigger("новый отчёт")
