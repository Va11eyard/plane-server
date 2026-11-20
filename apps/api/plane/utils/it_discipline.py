# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""
Daily-routine checks for the IT department (see setup_it_department) and Telegram reminders.

Team = IT_TEAM_EMAILS if set, else workspace members with role "member" (15);
managers = workspace admins (role 20) who are not in the team.
Rules checked: at most 5 cards in «Сегодня», no card in «Сегодня» longer than 3 days,
every card from «К работе» onward has an assignee and a due date, nothing overdue.
"""

import logging
import os
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Callable

from django.db.models import DateTimeField, OuterRef, Q, Subquery
from django.db.models.functions import Coalesce
from django.utils import timezone

from plane.db.models import Issue, IssueActivity, UserTelegramLink, WorkspaceMember

logger = logging.getLogger("plane.it_discipline")

STATE_TODAY = "Сегодня"
STATE_BLOCKER = "Блокер"
WORKING_STATES = ["К работе", "Сегодня", "Блокер", "На проверке"]
OPEN_GROUPS = ["backlog", "unstarted", "started"]
WIP_LIMIT = 5
STALE_DAYS = 3
TEAM_ROLE = 15
MANAGER_ROLE = 20
MAX_LINES = 10


@dataclass
class UserStats:
    today: list = field(default_factory=list)
    stale: list = field(default_factory=list)
    overdue: list = field(default_factory=list)

    @property
    def today_count(self) -> int:
        return len(self.today)

    @property
    def over_limit(self) -> bool:
        return self.today_count > WIP_LIMIT


@dataclass
class Report:
    users: dict
    blockers: list
    incomplete: list


def _issues(workspace):
    return Issue.issue_objects.filter(workspace=workspace).select_related("project", "state")


def analyze(workspace, team) -> Report:
    now = timezone.now()
    last_state_change = Subquery(
        IssueActivity.objects.filter(issue=OuterRef("pk"), field="state")
        .order_by("-created_at")
        .values("created_at")[:1],
        output_field=DateTimeField(),
    )
    base = _issues(workspace)
    users = {}
    for user in team:
        mine = base.filter(assignees=user, issue_assignee__deleted_at__isnull=True).distinct()
        today = list(mine.filter(state__name=STATE_TODAY).annotate(
            since=Coalesce(last_state_change, "created_at")
        ).order_by("since"))
        stale = [i for i in today if i.since < now - timedelta(days=STALE_DAYS)]
        overdue = list(
            mine.filter(state__group__in=OPEN_GROUPS, target_date__lt=timezone.localdate()).order_by("target_date")
        )
        users[user.id] = UserStats(today=today, stale=stale, overdue=overdue)

    blockers = list(base.filter(state__name=STATE_BLOCKER).order_by("created_at"))
    incomplete = list(
        base.filter(state__name__in=WORKING_STATES)
        .filter(Q(target_date__isnull=True) | Q(assignees__isnull=True))
        .distinct()
        .order_by("created_at")
    )
    return Report(users=users, blockers=blockers, incomplete=incomplete)


def _line(issue) -> str:
    return f"• {issue.project.identifier}-{issue.sequence_id} {(issue.name or '—')[:60]}"


def _lines(issues) -> str:
    shown = "\n".join(_line(i) for i in issues[:MAX_LINES])
    if len(issues) > MAX_LINES:
        shown += f"\n… и ещё {len(issues) - MAX_LINES}"
    return shown


def format_user_message(user, stats: UserStats, kind: str) -> str | None:
    name = user.first_name or user.email
    parts = []
    if kind == "morning":
        if stats.today_count == 0:
            parts.append("В «Сегодня» пусто. Перетащите туда 3-5 карточек до 10:00 - это ваш план на день.")
        if stats.over_limit:
            parts.append(f"В «Сегодня» {stats.today_count} карточек, лимит {WIP_LIMIT}. Верните лишние в «К работе».")
    elif kind == "evening":
        if stats.today:
            parts.append(
                "Передвиньте карточки из «Сегодня» (На проверке / Готово / Блокер / К работе):\n" + _lines(stats.today)
            )
        parts.append("Запишите 3 строки в странице «Дейли, неделя N» (Pages → «IT-отдел») до 18:30.")
    else:
        return None
    if stats.stale:
        parts.append(f"Висят в «Сегодня» больше {STALE_DAYS} дней, задачу нужно разбить:\n" + _lines(stats.stale))
    if stats.overdue:
        parts.append("Просрочено:\n" + _lines(stats.overdue))
    if not parts:
        return None
    return f"👋 {name}\n\n" + "\n\n".join(parts)


def format_manager_digest(report: Report) -> str | None:
    parts = []
    if report.blockers:
        parts.append("🚧 Блокеры:\n" + _lines(report.blockers))
    if report.incomplete:
        parts.append("🧹 Без исполнителя или срока:\n" + _lines(report.incomplete))
    overdue = [i for s in report.users.values() for i in s.overdue]
    if overdue:
        parts.append("⏰ Просрочено:\n" + _lines(overdue))
    stale = [i for s in report.users.values() for i in s.stale]
    if stale:
        parts.append(f"🐢 В «Сегодня» дольше {STALE_DAYS} дней:\n" + _lines(stale))
    over = [uid for uid, s in report.users.items() if s.over_limit]
    if over:
        parts.append(f"⚠️ Больше {WIP_LIMIT} карточек в «Сегодня»: {len(over)} чел.")
    if not parts:
        return None
    return "📊 IT-отдел: сводка\n\n" + "\n\n".join(parts)


def _members(workspace, role):
    return [
        m.member
        for m in WorkspaceMember.objects.filter(workspace=workspace, role=role, is_active=True).select_related("member")
        if not m.member.is_bot
    ]


def get_team(workspace) -> list:
    """IT_TEAM_EMAILS (comma separated) if set, otherwise active workspace members with role "member"."""
    raw = os.environ.get("IT_TEAM_EMAILS", "")
    emails = [e.strip().lower() for e in raw.split(",") if e.strip()]
    if not emails:
        return _members(workspace, TEAM_ROLE)
    members = WorkspaceMember.objects.filter(workspace=workspace, is_active=True).select_related("member")
    return [m.member for m in members if m.member.email.lower() in emails]


def get_managers(workspace, team) -> list:
    team_ids = {u.id for u in team}
    return [u for u in _members(workspace, MANAGER_ROLE) if u.id not in team_ids]


def run_reminders(kind: str, workspace_slug: str, send: Callable[[int, str], object] | None = None) -> int:
    """kind: morning | evening (to the team) or digest (to managers). Returns messages sent."""
    from plane.db.models import Workspace

    if send is None:
        from plane.utils.telegram_bot import send_message as send

    workspace = Workspace.objects.get(slug=workspace_slug)
    team = get_team(workspace)
    report = analyze(workspace, team)

    if kind == "digest":
        recipients = get_managers(workspace, team)
        text = format_manager_digest(report)
        messages = {u.id: text for u in recipients} if text else {}
    else:
        recipients = team
        messages = {u.id: format_user_message(u, report.users[u.id], kind) for u in team}

    sent = 0
    for user in recipients:
        text = messages.get(user.id)
        if not text:
            continue
        link = UserTelegramLink.objects.filter(user=user).first()
        if not link:
            continue
        try:
            send(link.telegram_chat_id, text)
            sent += 1
        except Exception:
            logger.exception("Failed to send %s reminder to %s", kind, user.email)
    return sent
