# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from plane.db.models import (
    IssueView,
    Label,
    Module,
    Page,
    Project,
    ProjectMember,
    ProjectPage,
    State,
    User,
    Workspace,
    WorkspaceMember,
)

PROJECT_NAMES = [
    "ODOS Game Амблиопия",
    "ODOS Game Миопия",
    "Wellmen",
    "Sen.AI",
    "Сайты",
    "MORI",
    "Galamat",
    "IT-отдел",
]
STATUSES = {
    "Бэклог": "backlog",
    "К работе": "unstarted",
    "Сегодня": "started",
    "Блокер": "started",
    "На проверке": "started",
    "Готово": "completed",
    "Отменено": "cancelled",
}
LABELS = {"дизайн", "разработка", "баг", "контент", "запрос извне"}


@pytest.fixture
def team(db):
    users = []
    for first in ("Begarys", "Dimash", "Aiganym"):
        users.append(User.objects.create(email=f"{first.lower()}@test.kz", first_name=first, username=first.lower()))
    return users


@pytest.fixture
def ws(workspace, team):
    for u in team:
        WorkspaceMember.objects.create(workspace=workspace, member=u, role=15)
    return workspace


def run(ws, team, *extra):
    emails = ",".join(u.email for u in team)
    call_command("setup_it_department", "--workspace", ws.slug, "--team", emails, *extra)


@pytest.mark.unit
@pytest.mark.django_db
class TestSetupItDepartment:
    def test_creates_all_projects(self, ws, team):
        run(ws, team)
        names = set(Project.objects.filter(workspace=ws).values_list("name", flat=True))
        assert set(PROJECT_NAMES) <= names

    def test_renames_existing_project_by_alias(self, ws, team):
        actor = team[0]
        old = Project.objects.create(workspace=ws, name="Sen AI", identifier="SEN", created_by=actor)
        run(ws, team)
        old.refresh_from_db()
        assert old.name == "Sen.AI"
        assert Project.objects.filter(workspace=ws, name="Sen.AI").count() == 1

    def test_states_follow_table_in_every_project(self, ws, team):
        run(ws, team)
        for project in Project.objects.filter(workspace=ws, name__in=PROJECT_NAMES):
            got = {s.name: s.group for s in State.objects.filter(project=project)}
            for name, group in STATUSES.items():
                assert got.get(name) == group, (project.name, name)

    def test_default_states_renamed_not_duplicated_and_issues_keep_state(self, ws, team):
        run(ws, team)
        project = Project.objects.get(workspace=ws, name="Сайты")
        # default Plane names must not linger next to the new ones
        names = list(State.objects.filter(project=project).values_list("name", flat=True))
        for legacy in ("Todo", "In Progress", "Done", "Backlog", "Cancelled"):
            assert legacy not in names
        assert State.objects.get(project=project, name="Бэклог").default is True

    def test_existing_default_states_are_renamed_in_place(self, ws, team):
        actor = team[0]
        project = Project.objects.create(workspace=ws, name="MORI", identifier="MORI", created_by=actor)
        todo = State.objects.create(project=project, workspace=ws, name="Todo", group="unstarted", color="#000")
        run(ws, team)
        todo.refresh_from_db()
        assert todo.name == "К работе"

    def test_labels_in_every_project(self, ws, team):
        run(ws, team)
        for project in Project.objects.filter(workspace=ws, name__in=PROJECT_NAMES):
            got = set(Label.objects.filter(project=project).values_list("name", flat=True))
            assert LABELS <= got, project.name

    def test_site_modules_in_sites_project(self, ws, team):
        run(ws, team, "--sites", "InLab,Galamat")
        sites = Project.objects.get(workspace=ws, name="Сайты")
        assert set(Module.objects.filter(project=sites).values_list("name", flat=True)) == {"InLab", "Galamat"}

    def test_workspace_views_created(self, ws, team):
        run(ws, team)
        names = set(IssueView.objects.filter(workspace=ws, project__isnull=True).values_list("name", flat=True))
        assert {
            "Команда: сегодня",
            "Загрузка",
            "Просрочено",
            "Блокеры",
            "Без исполнителя или срока",
        } <= names

    def test_my_tasks_view_per_team_member(self, ws, team):
        run(ws, team)
        for user in team:
            view = IssueView.objects.get(workspace=ws, project__isnull=True, name=f"Мои задачи: {user.first_name}")
            assert view.owned_by == user
            assert str(user.id) in str(view.rich_filters)

    def test_team_today_view_filters_by_state_ids_and_groups_by_assignee(self, ws, team):
        run(ws, team)
        view = IssueView.objects.get(workspace=ws, project__isnull=True, name="Команда: сегодня")
        wanted = set(
            str(i)
            for i in State.objects.filter(workspace=ws, name__in=["Сегодня", "Блокер"]).values_list("id", flat=True)
        )
        ids = set(view.rich_filters["state_id__in"].split(","))
        assert ids == wanted
        assert view.display_filters["group_by"] == "assignees"

    def test_blockers_view_groups_by_project(self, ws, team):
        run(ws, team)
        view = IssueView.objects.get(workspace=ws, project__isnull=True, name="Блокеры")
        assert view.display_filters["group_by"] == "project"

    def test_board_views_in_projects(self, ws, team):
        run(ws, team)
        wellmen = Project.objects.get(workspace=ws, name="Wellmen")
        board = IssueView.objects.get(project=wellmen, name="Доска")
        assert board.display_filters["layout"] == "kanban"
        assert board.display_filters["group_by"] == "state"
        sites = Project.objects.get(workspace=ws, name="Сайты")
        swim = IssueView.objects.get(project=sites, name="Доска по исполнителям")
        assert swim.display_filters["sub_group_by"] == "assignees"

    def test_daily_template_page_in_it_project(self, ws, team):
        run(ws, team)
        it = Project.objects.get(workspace=ws, name="IT-отдел")
        page = Page.objects.get(workspace=ws, name="Дейли, неделя N (шаблон)")
        assert ProjectPage.objects.filter(project=it, page=page).exists()
        for u in team:
            assert u.first_name in page.description_html
        assert "Сделано:" in page.description_html
        assert "Не успел:" in page.description_html
        assert "Блокеры / нужна помощь:" in page.description_html

    def test_idempotent(self, ws, team):
        run(ws, team)
        counts = lambda: (  # noqa: E731
            Project.objects.count(),
            State.objects.count(),
            Label.objects.count(),
            Module.objects.count(),
            IssueView.objects.count(),
            Page.objects.count(),
            ProjectMember.objects.count(),
        )
        first = counts()
        run(ws, team)
        assert counts() == first

    def test_overdue_view_is_refreshed_on_rerun(self, ws, team):
        run(ws, team)
        IssueView.objects.filter(name="Просрочено").update(rich_filters={})
        run(ws, team)
        assert IssueView.objects.get(name="Просрочено").rich_filters

    def test_unknown_team_email_fails(self, ws, team):
        with pytest.raises(CommandError):
            call_command("setup_it_department", "--workspace", ws.slug, "--team", "nobody@test.kz")

    def test_single_workspace_is_autodetected(self, ws, team):
        call_command("setup_it_department", "--team", ",".join(u.email for u in team))
        assert Project.objects.filter(workspace=ws, name="Сайты").exists()

    def test_requires_workspace_when_several(self, ws, team):
        Workspace.objects.create(name="Other", slug="other", owner=team[0])
        with pytest.raises(CommandError):
            call_command("setup_it_department", "--team", ",".join(u.email for u in team))

    def test_galamat_existing_project_is_reused_and_configured(self, ws, team):
        actor = team[0]
        galamat = Project.objects.create(workspace=ws, name="Galamat", identifier="GAL", created_by=actor)
        todo = State.objects.create(project=galamat, workspace=ws, name="Todo", group="unstarted", color="#000")
        run(ws, team)
        assert Project.objects.filter(workspace=ws, name="Galamat").count() == 1
        galamat.refresh_from_db()
        assert galamat.identifier == "GAL"
        todo.refresh_from_db()
        assert todo.name == "К работе"

    def test_galamat_has_area_modules(self, ws, team):
        run(ws, team)
        galamat = Project.objects.get(workspace=ws, name="Galamat")
        names = set(Module.objects.filter(project=galamat).values_list("name", flat=True))
        assert {"Дизайн", "Фронтенд", "Бэкенд", "Контент", "SEO и аналитика"} <= names

    def test_galamat_has_swimlane_board(self, ws, team):
        run(ws, team)
        galamat = Project.objects.get(workspace=ws, name="Galamat")
        board = IssueView.objects.get(project=galamat, name="Доска по исполнителям")
        assert board.display_filters["sub_group_by"] == "assignees"
        assert board.display_filters["layout"] == "kanban"
