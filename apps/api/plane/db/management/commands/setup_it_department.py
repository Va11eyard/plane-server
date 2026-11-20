# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""
Idempotent setup of the IT department workflow in Plane (see the "ТЗ: настройка Plane
и ежедневный план/отчёт IT-отдела"):

* one project per product + service project "IT-отдел";
* the same seven statuses (with the correct Plane state groups) in every project;
* the same labels in every project;
* a module per site in project "Сайты" and per work area in "Galamat";
* manager views (workspace level) + per-person "Мои задачи" + boards in projects;
* a "Дейли, неделя N" page template in "IT-отдел".

Re-running is safe. The date-based "Просрочено" view is refreshed nightly by a Celery task.
"""

import html
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

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

GALAMAT_PROJECT = "Galamat"
# Work areas of the Galamat project; one module per area
GALAMAT_MODULES = ["Дизайн", "Фронтенд", "Бэкенд", "Контент", "SEO и аналитика"]

# name, identifier, aliases (old names that are renamed in place)
PROJECTS = [
    {"name": "ODOS Game Амблиопия", "identifier": "OGA", "aliases": []},
    {"name": "ODOS Game Миопия", "identifier": "OGM", "aliases": []},
    {"name": "Wellmen", "identifier": "WELLMEN", "aliases": ["Велмен"]},
    {"name": "Sen.AI", "identifier": "SEN", "aliases": ["Sen AI", "SenAI"]},
    {"name": "Сайты", "identifier": "SITES", "aliases": []},
    {"name": "MORI", "identifier": "MORI", "aliases": []},
    {"name": GALAMAT_PROJECT, "identifier": "GALAMAT", "aliases": []},
    {"name": "IT-отдел", "identifier": "ITD", "aliases": []},
]
SITES_PROJECT = "Сайты"
IT_PROJECT = "IT-отдел"
BEGARYS_PROJECTS = ["ODOS Game Амблиопия", "ODOS Game Миопия", "Wellmen", "Sen.AI"]

# name, group, color, sequence, legacy names that are renamed in place
STATUSES = [
    ("Бэклог", "backlog", "#60646C", 15000, ["Backlog"]),
    ("К работе", "unstarted", "#3A7BD5", 25000, ["Todo"]),
    ("Сегодня", "started", "#F59E0B", 35000, ["In Progress"]),
    ("Блокер", "started", "#E5484D", 36000, []),
    ("На проверке", "started", "#8E4EC6", 37000, []),
    ("Готово", "completed", "#46A758", 45000, ["Done"]),
    ("Отменено", "cancelled", "#9AA4BC", 55000, ["Cancelled"]),
]
DEFAULT_STATUS = "Бэклог"

LABELS = [
    ("дизайн", "#E93D82"),
    ("разработка", "#3E63DD"),
    ("баг", "#E5484D"),
    ("контент", "#30A46C"),
    ("запрос извне", "#F76B15"),
]

ACTIVE_GROUPS = "backlog,unstarted,started"
OVERDUE_FROM = "2000-01-01"
WEEKDAYS = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница"]


def _display(user: User) -> str:
    return user.first_name or user.display_name or user.email


def _in(*ids) -> str:
    return ",".join(str(i) for i in ids)


def ensure_project(workspace: Workspace, spec: dict, actor: User) -> Project:
    names = [spec["name"], *spec["aliases"]]
    project = None
    for name in names:
        project = Project.objects.filter(workspace=workspace, name=name).first()
        if project:
            break
    if project:
        if project.name != spec["name"]:
            project.name = spec["name"]
            project.save(update_fields=["name"])
    else:
        used = set(Project.objects.filter(workspace=workspace).values_list("identifier", flat=True))
        candidate = spec["identifier"].upper()[:12]
        n = 1
        while candidate in used:
            suffix = str(n)
            candidate = (candidate[: 12 - len(suffix)] + suffix)[:12]
            n += 1
        project = Project.objects.create(workspace=workspace, name=spec["name"], identifier=candidate, created_by=actor)

    for membership in WorkspaceMember.objects.filter(workspace=workspace, is_active=True):
        ProjectMember.objects.get_or_create(
            project=project,
            member_id=membership.member_id,
            defaults={
                "workspace": workspace,
                "role": membership.role,
                "created_by": actor,
                "is_active": True,
            },
        )
    return project


def ensure_states(workspace: Workspace, project: Project, actor: User) -> dict:
    """Make the project states match STATUSES; returns {name: State}."""
    result = {}
    for name, group, color, sequence, legacy in STATUSES:
        state = State.objects.filter(project=project, name=name).first()
        if not state:
            state = State.objects.filter(project=project, name__in=legacy, group=group).first()
        if state:
            state.name, state.group, state.sequence = name, group, sequence
            state.default = name == DEFAULT_STATUS
            state.save(update_fields=["name", "group", "sequence", "default"])
        else:
            state = State.objects.create(
                project=project,
                workspace=workspace,
                name=name,
                group=group,
                color=color,
                sequence=sequence,
                default=name == DEFAULT_STATUS,
                created_by=actor,
            )
        result[name] = state
    return result


def ensure_labels(workspace: Workspace, project: Project, actor: User) -> None:
    for name, color in LABELS:
        if not Label.objects.filter(project=project, name__iexact=name).exists():
            Label.objects.create(project=project, workspace=workspace, name=name, color=color, created_by=actor)


def ensure_modules(workspace: Workspace, project: Project, sites: list, actor: User) -> None:
    for site in sites:
        if not Module.objects.filter(project=project, name=site).exists():
            Module.objects.create(project=project, workspace=workspace, name=site, created_by=actor)


def _display_filters(group_by, layout="list", sub_group_by=None, order_by="target_date"):
    return {
        "group_by": group_by,
        "sub_group_by": sub_group_by,
        "order_by": order_by,
        "type": None,
        "sub_issue": True,
        "show_empty_groups": True,
        "layout": layout,
        "calendar_date_range": "",
    }


def upsert_view(workspace, owner, name, rich_filters, display_filters, description="", project=None) -> IssueView:
    view = IssueView.objects.filter(workspace=workspace, project=project, name=name).first()
    fields = {
        "description": description,
        "query": {},
        "filters": {},
        "rich_filters": rich_filters,
        "display_filters": display_filters,
        "access": 1,
    }
    if view:
        for key, value in fields.items():
            setattr(view, key, value)
        view.save()
        return view
    return IssueView.objects.create(
        workspace=workspace, project=project, name=name, owned_by=owner, created_by=owner, **fields
    )


def overdue_view_content(today) -> tuple:
    """Rich filters and description of «Просрочено»: open cards with a due date before `today`."""
    overdue_to = (today - timedelta(days=1)).isoformat()
    filters = {
        "and": [
            {"state_group__in": ACTIVE_GROUPS},
            {"target_date__range": f"{OVERDUE_FROM},{overdue_to}"},
        ]
    }
    description = (
        f"Срок раньше {today.isoformat()}, задача не закрыта. "
        "Диапазон обновляется ежедневно (задача Celery) или повторным запуском setup_it_department."
    )
    return filters, description


def refresh_overdue_view(workspace, today=None) -> bool:
    """Move the «Просрочено» date range to today. Returns False if the view does not exist."""
    view = IssueView.objects.filter(workspace=workspace, project__isnull=True, name="Просрочено").first()
    if not view:
        return False
    view.rich_filters, view.description = overdue_view_content(today or timezone.localdate())
    view.save(update_fields=["rich_filters", "description"])
    return True


def ensure_views(workspace, projects, states_by_project, team, actor) -> None:
    def ids(*names):
        return [s.id for st in states_by_project.values() for n, s in st.items() if n in names]

    today = timezone.localdate()

    upsert_view(
        workspace, actor, "Команда: сегодня",
        {"state_id__in": _in(*ids("Сегодня", "Блокер"))},
        _display_filters("assignees"),
        "Кто чем занят прямо сейчас (Сегодня + Блокер).",
    )
    upsert_view(
        workspace, actor, "Загрузка",
        {"state_id__in": _in(*ids("К работе", "Сегодня", "Блокер", "На проверке"))},
        _display_filters("assignees"),
        "У кого сколько задач в работе, кто перегружен.",
    )
    overdue_filters, overdue_description = overdue_view_content(today)
    upsert_view(workspace, actor, "Просрочено", overdue_filters, _display_filters("assignees"), overdue_description)
    upsert_view(
        workspace, actor, "Блокеры",
        {"state_id__in": _in(*ids("Блокер"))},
        _display_filters("project"),
        "Где нужна помощь руководителя.",
    )
    upsert_view(
        workspace, actor, "Без исполнителя или срока",
        {"state_id__in": _in(*ids("К работе", "Сегодня", "Блокер", "На проверке"))},
        _display_filters("assignees", order_by="target_date"),
        "Что почистить: группа «None» = задача без исполнителя; без срока задачи идут в конце списка по сроку.",
    )
    for user in team:
        upsert_view(
            workspace, user, f"Мои задачи: {_display(user)}",
            {"and": [{"assignee_id__in": str(user.id)}, {"state_group__in": ACTIVE_GROUPS}]},
            _display_filters("state"),
            "Рабочее место сотрудника утром и вечером.",
        )

    for name in BEGARYS_PROJECTS:
        upsert_view(
            workspace, actor, "Доска", {}, _display_filters("state", layout="kanban"),
            "Доска по статусам.", project=projects[name],
        )
    upsert_view(
        workspace, actor, "Доска по исполнителям", {},
        _display_filters("state", layout="kanban", sub_group_by="assignees"),
        "Доска по статусам с дорожками по исполнителям.", project=projects[SITES_PROJECT],
    )
    upsert_view(
        workspace, actor, "Доска по исполнителям", {},
        _display_filters("state", layout="kanban", sub_group_by="assignees"),
        "Доска по статусам с дорожками по исполнителям.", project=projects[GALAMAT_PROJECT],
    )


def daily_template_html(team) -> str:
    parts = [
        "<p>Шаблон: скопируйте страницу в «Дейли, неделя N» и замените N. "
        "Номера задач Plane (например OGA-12) становятся ссылками.</p>"
    ]
    for day in WEEKDAYS:
        parts.append(f"<h2>{day}</h2>")
        for user in team:
            parts.append(
                f"<h3>{html.escape(_display(user))}, __.__</h3>"
                "<p>Сделано: </p><p>Не успел: </p><p>Блокеры / нужна помощь: нет</p>"
            )
    return "".join(parts)


def ensure_daily_template(workspace, it_project, team, actor) -> Page:
    name = "Дейли, неделя N (шаблон)"
    body = daily_template_html(team)
    page = Page.objects.filter(workspace=workspace, name=name, project_pages__project=it_project).first()
    if page:
        page.description_html = body
        page.save(update_fields=["description_html"])
        return page
    page = Page.objects.create(
        workspace=workspace, name=name, description_html=body, owned_by=actor, created_by=actor, access=0
    )
    ProjectPage.objects.create(project=it_project, page=page, workspace=workspace, created_by=actor)
    return page


class Command(BaseCommand):
    help = "Set up IT department workflow: projects, statuses, labels, site modules, views, daily page template"

    def add_arguments(self, parser):
        parser.add_argument("--workspace", help="Workspace slug (optional when there is exactly one workspace)")
        parser.add_argument("--team", required=True, help="Comma-separated emails of the IT team (3 people)")
        parser.add_argument("--sites", default="InLab", help="Comma-separated site names for modules in «Сайты»")

    def handle(self, *args, **options):
        if options["workspace"]:
            workspace = Workspace.objects.filter(slug=options["workspace"]).first()
            if not workspace:
                raise CommandError(f"Workspace {options['workspace']} not found")
        else:
            workspaces = list(Workspace.objects.all()[:2])
            if len(workspaces) != 1:
                raise CommandError("Pass --workspace: expected exactly one workspace in the database")
            workspace = workspaces[0]

        team = []
        for email in [e.strip() for e in options["team"].split(",") if e.strip()]:
            user = User.objects.filter(email__iexact=email).first()
            if not user:
                raise CommandError(f"User {email} not found")
            team.append(user)
        if not team:
            raise CommandError("--team is empty")
        sites = [s.strip() for s in options["sites"].split(",") if s.strip()]

        actor = team[0]
        for user in team:
            WorkspaceMember.objects.get_or_create(
                workspace=workspace, member=user, defaults={"role": 15, "is_active": True}
            )

        projects, states_by_project = {}, {}
        for spec in PROJECTS:
            project = ensure_project(workspace, spec, actor)
            projects[spec["name"]] = project
            states_by_project[spec["name"]] = ensure_states(workspace, project, actor)
            ensure_labels(workspace, project, actor)
            self.stdout.write(self.style.SUCCESS(f"Project {project.name} ({project.identifier}) ready"))

        ensure_modules(workspace, projects[SITES_PROJECT], sites, actor)
        ensure_modules(workspace, projects[GALAMAT_PROJECT], GALAMAT_MODULES, actor)
        ensure_views(workspace, projects, states_by_project, team, actor)
        ensure_daily_template(workspace, projects[IT_PROJECT], team, actor)
        self.stdout.write(self.style.SUCCESS("IT department setup complete"))
