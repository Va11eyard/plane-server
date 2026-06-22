# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import json
import os
import re
import unicodedata
from datetime import date, datetime, timedelta
from typing import Any

from django.conf import settings
from django.utils import timezone

from plane.bgtasks.issue_activities_task import issue_activity
from plane.db.models import Issue, IssueAssignee, Project, ProjectMember, State, UserTelegramLink, Workspace, WorkspaceMember

IHEALTH_SLUG = "ihealth"
MEMBER_ROLE_MIN = 15
CONFIDENCE_THRESHOLD = 0.8


def can_create_task(user) -> bool:
    return WorkspaceMember.objects.filter(
        workspace__slug=IHEALTH_SLUG,
        member=user,
        is_active=True,
        role__gte=MEMBER_ROLE_MIN,
    ).exists()


def get_ihealth_workspace() -> Workspace | None:
    return Workspace.objects.filter(slug=IHEALTH_SLUG).first()


def get_task_projects(user) -> list[dict[str, str]]:
    workspace = get_ihealth_workspace()
    if not workspace:
        return []
    projects = (
        Project.objects.filter(
            workspace=workspace,
            project_projectmember__member=user,
            project_projectmember__is_active=True,
            project_projectmember__role__gte=MEMBER_ROLE_MIN,
        )
        .distinct()
        .order_by("name")
    )
    return [{"id": str(p.id), "name": p.name, "identifier": p.identifier or ""} for p in projects]


def get_assignable_members(project: Project) -> list[dict[str, str]]:
    members = (
        ProjectMember.objects.filter(
            project=project,
            is_active=True,
            role__gte=MEMBER_ROLE_MIN,
            member__isnull=False,
        )
        .select_related("member")
        .order_by("member__display_name", "member__email")
    )
    result: list[dict[str, str]] = []
    for pm in members:
        user = pm.member
        if not user:
            continue
        result.append(
            {
                "id": str(user.id),
                "display_name": user.display_name or "",
                "email": user.email or "",
            }
        )
    return result


def _normalize(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", text.lower().strip())


def match_project(hint: str | None, projects: list[dict[str, str]]) -> tuple[dict[str, str] | None, float]:
    if not hint or not projects:
        return None, 0.0
    norm_hint = _normalize(hint)
    if not norm_hint:
        return None, 0.0

    scored: list[tuple[float, dict[str, str]]] = []
    for project in projects:
        name = _normalize(project["name"])
        ident = _normalize(project.get("identifier") or "")
        score = 0.0
        if norm_hint == name or norm_hint == ident:
            score = 1.0
        elif norm_hint in name or name in norm_hint:
            score = 0.9
        elif ident and (norm_hint in ident or ident in norm_hint):
            score = 0.85
        else:
            hint_tokens = set(norm_hint.split())
            name_tokens = set(name.split())
            overlap = hint_tokens & name_tokens
            if overlap:
                score = 0.5 + 0.1 * len(overlap)
        if score > 0:
            scored.append((score, project))

    if not scored:
        return None, 0.0
    scored.sort(key=lambda x: x[0], reverse=True)
    best_score, best = scored[0]
    if len(scored) > 1 and scored[1][0] >= best_score - 0.05:
        return None, best_score * 0.5
    return best, best_score


def match_assignee(hint: str | None, members: list[dict[str, str]]) -> tuple[dict[str, str] | None, float]:
    if not hint or not members:
        return None, 0.0
    norm_hint = _normalize(hint)
    if not norm_hint:
        return None, 0.0

    scored: list[tuple[float, dict[str, str]]] = []
    for member in members:
        name = _normalize(member.get("display_name") or "")
        email = _normalize(member.get("email") or "")
        email_local = email.split("@")[0] if email else ""
        score = 0.0
        if norm_hint == name or norm_hint == email or norm_hint == email_local:
            score = 1.0
        elif name and (norm_hint in name or name in norm_hint):
            score = 0.9
        elif email_local and (norm_hint in email_local or email_local in norm_hint):
            score = 0.85
        elif email and norm_hint in email:
            score = 0.8
        if score > 0:
            scored.append((score, member))

    if not scored:
        return None, 0.0
    scored.sort(key=lambda x: x[0], reverse=True)
    best_score, best = scored[0]
    if len(scored) > 1 and scored[1][0] >= best_score - 0.05:
        return None, best_score * 0.5
    return best, best_score


def parse_target_date(hint: str | None, today: date | None = None) -> date | None:
    if not hint or not str(hint).strip():
        return None
    today = today or date.today()
    raw = str(hint).strip().lower()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        try:
            return datetime.strptime(raw, "%Y-%m-%d").date()
        except ValueError:
            return None
    if re.fullmatch(r"\d{1,2}\.\d{1,2}\.\d{4}", raw):
        try:
            return datetime.strptime(raw, "%d.%m.%Y").date()
        except ValueError:
            return None

    weekdays = {
        "понедельник": 0,
        "вторник": 1,
        "среда": 2,
        "четверг": 3,
        "пятница": 4,
        "суббота": 5,
        "воскресенье": 6,
        "пн": 0,
        "вт": 1,
        "ср": 2,
        "чт": 3,
        "пт": 4,
        "сб": 5,
        "вс": 6,
    }
    for label, wd in weekdays.items():
        if label in raw:
            days_ahead = (wd - today.weekday()) % 7
            if days_ahead == 0:
                days_ahead = 7
            return today + timedelta(days=days_ahead)

    if "завтра" in raw:
        return today + timedelta(days=1)
    if "послезавтра" in raw:
        return today + timedelta(days=2)
    if "недел" in raw:
        return today + timedelta(days=7)
    return None


def merge_draft(existing: dict[str, Any], parsed: dict[str, Any]) -> dict[str, Any]:
    draft = dict(existing or {})
    for key in ("title", "description", "project_id", "project_name", "assignee_id", "assignee_name", "target_date"):
        value = parsed.get(key)
        if value not in (None, "", []):
            draft[key] = value
    return draft


def get_default_state(project: Project) -> State | None:
    return (
        State.objects.filter(project=project, group="unstarted").order_by("sequence").first()
        or State.objects.filter(project=project, group="backlog").order_by("sequence").first()
        or State.objects.filter(project=project).order_by("sequence").first()
    )


def _html_desc(text: str) -> str:
    if not text:
        return "<p></p>"
    escaped = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return "<p>" + escaped.replace("\n", "<br/>") + "</p>"


def get_app_origin() -> str:
    base = (
        os.environ.get("WEB_URL")
        or os.environ.get("APP_BASE_URL")
        or getattr(settings, "WEB_URL", None)
        or getattr(settings, "APP_BASE_URL", None)
        or ""
    ).rstrip("/")
    return base or "https://task.pro-ecta.kz"


def notify_issue_created_from_telegram(
    *,
    issue: Issue,
    project: Project,
    creator,
    title: str,
    description: str = "",
    assignee_id: str | None = None,
) -> None:
    """Trigger Plane in-app/email notifications and optional Telegram DM to assignee."""
    assignee_ids = [str(assignee_id)] if assignee_id else []
    requested_data = {
        "name": title,
        "description_html": _html_desc(description),
        "assignee_ids": assignee_ids,
    }
    issue_activity.delay(  # pyright: ignore[reportFunctionMemberAccess]
        type="issue.activity.created",
        requested_data=json.dumps(requested_data),
        current_instance=None,
        actor_id=str(creator.id),
        issue_id=str(issue.id),
        project_id=str(project.id),
        epoch=int(timezone.now().timestamp()),
        notification=True,
        subscriber=True,
        origin=get_app_origin(),
    )

    if not assignee_id or str(creator.id) == str(assignee_id):
        return

    link = UserTelegramLink.objects.filter(user_id=assignee_id).first()
    if not link:
        return

    from plane.utils.telegram_bot import send_message

    url = build_issue_url(project.workspace.slug, str(project.id), str(issue.id))
    ident = project.identifier or "TASK"
    creator_name = creator.display_name or creator.email or "Менеджер"
    send_message(
        link.telegram_chat_id,
        f"📌 Вам назначена задача {ident}-{issue.sequence_id}\n"
        f"«{title}»\n"
        f"От: {creator_name}\n"
        f"{url}",
    )


def create_issue_from_telegram(
    *,
    project: Project,
    creator,
    title: str,
    description: str = "",
    assignee_id: str | None = None,
    target_date: date | None = None,
) -> tuple[Issue | None, str | None]:
    state = get_default_state(project)
    if not state:
        return None, "У проекта нет статусов для новой задачи"

    name = (title or "").strip()[:255]
    if not name:
        return None, "Название задачи не может быть пустым"

    desc = (description or "").strip()
    issue = Issue(
        project=project,
        workspace=project.workspace,
        name=name,
        description_html=_html_desc(desc) if desc else "<p></p>",
        description_stripped=desc,
        state=state,
        priority="medium",
        target_date=target_date,
        created_by=creator,
        updated_by=creator,
    )
    issue.save()

    if assignee_id:
        if ProjectMember.objects.filter(
            project=project,
            member_id=assignee_id,
            is_active=True,
            role__gte=MEMBER_ROLE_MIN,
        ).exists():
            IssueAssignee.objects.get_or_create(
                issue=issue,
                assignee_id=assignee_id,
                project=project,
                workspace=project.workspace,
                defaults={"created_by": creator, "updated_by": creator},
            )

    notify_issue_created_from_telegram(
        issue=issue,
        project=project,
        creator=creator,
        title=name,
        description=desc,
        assignee_id=assignee_id,
    )

    return issue, None


def build_issue_url(workspace_slug: str, project_id: str, issue_id: str) -> str:
    base = (
        os.environ.get("WEB_URL")
        or os.environ.get("APP_BASE_URL")
        or getattr(settings, "WEB_URL", None)
        or getattr(settings, "APP_BASE_URL", None)
        or ""
    ).rstrip("/")
    if not base:
        return f"/{workspace_slug}/projects/{project_id}/issues/{issue_id}"
    return f"{base}/{workspace_slug}/projects/{project_id}/issues/{issue_id}"


def format_date_ru(d: date | str | None) -> str:
    if not d:
        return "—"
    if isinstance(d, str):
        try:
            d = datetime.strptime(d, "%Y-%m-%d").date()
        except ValueError:
            return d
    return d.strftime("%d.%m.%Y")
