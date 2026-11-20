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
        # Plane cannot group workspace-level views: they are flat spreadsheets (grouping lives in project views)
        assert view.display_filters["layout"] == "spreadsheet"
        assert view.display_filters["group_by"] is None

    def test_blockers_workspace_view_is_spreadsheet(self, ws, team):
        run(ws, team)
        view = IssueView.objects.get(workspace=ws, project__isnull=True, name="Блокеры")
        assert view.display_filters["layout"] == "spreadsheet"

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
        IssueView.objects.filter(name="Просрочено", project__isnull=True).update(rich_filters={})
        run(ws, team)
        assert IssueView.objects.get(name="Просрочено", project__isnull=True).rich_filters

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


@pytest.mark.unit
@pytest.mark.django_db
class TestRefreshOverdueView:
    def test_moves_range_end_to_yesterday(self, ws, team):
        from datetime import date

        from plane.db.management.commands.setup_it_department import refresh_overdue_view

        run(ws, team)
        assert refresh_overdue_view(ws, today=date(2030, 1, 2)) is True
        view = IssueView.objects.get(workspace=ws, name="Просрочено", project__isnull=True)
        assert {"target_date__range": "2000-01-01,2030-01-01"} in view.rich_filters["and"]
        assert "2030-01-02" in view.description

    def test_returns_false_when_view_missing(self, ws, team):
        from plane.db.management.commands.setup_it_department import refresh_overdue_view

        assert refresh_overdue_view(ws) is False


GROUPED = ["Команда: сегодня", "Загрузка", "Просрочено", "Блокеры", "Без исполнителя или срока"]


@pytest.mark.unit
@pytest.mark.django_db
class TestProjectGroupedViews:
    def test_every_it_project_has_views_grouped_by_assignee(self, ws, team):
        run(ws, team)
        for project in Project.objects.filter(workspace=ws, name__in=PROJECT_NAMES):
            for name in GROUPED:
                view = IssueView.objects.get(project=project, name=name)
                assert view.display_filters["group_by"] == "assignees", (project.name, name)
                assert view.display_filters["layout"] == "list", (project.name, name)

    def test_project_view_uses_only_its_own_state_ids(self, ws, team):
        run(ws, team)
        project = Project.objects.get(workspace=ws, name="Сайты")
        view = IssueView.objects.get(project=project, name="Команда: сегодня")
        qs = State.objects.filter(project=project, name__in=["Сегодня", "Блокер"])
        own = {str(i) for i in qs.values_list("id", flat=True)}
        assert set(view.rich_filters["state_id__in"].split(",")) == own

    def test_refresh_updates_project_overdue_views_too(self, ws, team):
        from datetime import date

        from plane.db.management.commands.setup_it_department import refresh_overdue_view

        run(ws, team)
        refresh_overdue_view(ws, today=date(2030, 1, 2))
        project = Project.objects.get(workspace=ws, name="Сайты")
        view = IssueView.objects.get(project=project, name="Просрочено")
        assert {"target_date__range": "2000-01-01,2030-01-01"} in view.rich_filters["and"]


@pytest.mark.unit
@pytest.mark.django_db
class TestSidebarFavorites:
    def _run(self, ws, team, follower):
        call_command(
            "setup_it_department",
            "--workspace", ws.slug,
            "--team", ",".join(u.email for u in team),
            "--followers", follower.email,
        )

    def test_follower_gets_folder_with_entry_per_person(self, ws, team):
        from plane.db.models import UserFavorite

        boss = User.objects.create(email="boss@test.kz", first_name="Boss", username="boss")
        WorkspaceMember.objects.create(workspace=ws, member=boss, role=20)
        self._run(ws, team, boss)
        folder = UserFavorite.objects.get(user=boss, workspace=ws, is_folder=True, name="IT-отдел")
        items = UserFavorite.objects.filter(user=boss, parent=folder, entity_type="view")
        views = IssueView.objects.filter(workspace=ws, project__isnull=True, name__startswith="Мои задачи:")
        assert {i.entity_identifier for i in items} == {v.id for v in views}
        assert items.count() == 3
        assert all(i.project_id is None for i in items)

    def test_each_team_member_sees_only_own_entry(self, ws, team):
        from plane.db.models import UserFavorite

        boss = User.objects.create(email="boss@test.kz", first_name="Boss", username="boss")
        WorkspaceMember.objects.create(workspace=ws, member=boss, role=20)
        self._run(ws, team, boss)
        items = UserFavorite.objects.filter(user=team[1], entity_type="view")
        assert items.count() == 1
        assert IssueView.objects.get(id=items[0].entity_identifier).owned_by == team[1]

    def test_favorites_are_idempotent(self, ws, team):
        from plane.db.models import UserFavorite

        boss = User.objects.create(email="boss@test.kz", first_name="Boss", username="boss")
        WorkspaceMember.objects.create(workspace=ws, member=boss, role=20)
        self._run(ws, team, boss)
        first = UserFavorite.objects.count()
        self._run(ws, team, boss)
        assert UserFavorite.objects.count() == first

    def test_unknown_follower_fails(self, ws, team):
        with pytest.raises(CommandError):
            call_command(
                "setup_it_department", "--workspace", ws.slug,
                "--team", ",".join(u.email for u in team), "--followers", "ghost@test.kz",
            )
