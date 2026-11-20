# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone

from plane.db.models import (
    Issue,
    IssueActivity,
    IssueAssignee,
    Project,
    State,
    User,
    UserTelegramLink,
    WorkspaceMember,
)
from plane.utils.it_discipline import analyze, format_manager_digest, format_user_message, run_reminders


@pytest.fixture
def team(db):
    return [User.objects.create(email=f"{n}@test.kz", first_name=n, username=n) for n in ("beg", "dim", "aig")]


@pytest.fixture
def setup(workspace, team):
    for u in team:
        WorkspaceMember.objects.create(workspace=workspace, member=u, role=15)
    call_command("setup_it_department", "--workspace", workspace.slug, "--team", ",".join(u.email for u in team))
    return workspace


def state(ws, project, name):
    return State.objects.get(workspace=ws, project=project, name=name)


def make_issue(ws, project, st_name, assignee=None, due=None, name="Сделать вещь"):
    issue = Issue.objects.create(
        workspace=ws, project=project, name=name, state=state(ws, project, st_name), target_date=due
    )
    if assignee:
        IssueAssignee.objects.create(issue=issue, assignee=assignee, project=project, workspace=ws)
    return issue


def age_state_change(ws, project, issue, days):
    act = IssueActivity.objects.create(issue=issue, project=project, workspace=ws, field="state", verb="updated")
    IssueActivity.objects.filter(pk=act.pk).update(created_at=timezone.now() - timedelta(days=days))


@pytest.mark.unit
@pytest.mark.django_db
class TestAnalyze:
    def test_counts_today_cards_per_person(self, setup, team):
        proj = Project.objects.get(workspace=setup, name="Сайты")
        for _ in range(3):
            make_issue(setup, proj, "Сегодня", team[1], timezone.localdate())
        report = analyze(setup, team)
        assert report.users[team[1].id].today_count == 3
        assert report.users[team[0].id].today_count == 0

    def test_flags_over_limit(self, setup, team):
        proj = Project.objects.get(workspace=setup, name="Сайты")
        for _ in range(6):
            make_issue(setup, proj, "Сегодня", team[1], timezone.localdate())
        assert analyze(setup, team).users[team[1].id].over_limit is True

    def test_five_cards_is_not_over_limit(self, setup, team):
        proj = Project.objects.get(workspace=setup, name="Сайты")
        for _ in range(5):
            make_issue(setup, proj, "Сегодня", team[1], timezone.localdate())
        assert analyze(setup, team).users[team[1].id].over_limit is False

    def test_stale_today_card_older_than_three_days(self, setup, team):
        proj = Project.objects.get(workspace=setup, name="Сайты")
        old = make_issue(setup, proj, "Сегодня", team[1], timezone.localdate())
        age_state_change(setup, proj, old, 4)
        fresh = make_issue(setup, proj, "Сегодня", team[1], timezone.localdate())
        age_state_change(setup, proj, fresh, 1)
        stale = analyze(setup, team).users[team[1].id].stale
        assert [i.id for i in stale] == [old.id]

    def test_overdue_excludes_done(self, setup, team):
        proj = Project.objects.get(workspace=setup, name="Сайты")
        yesterday = timezone.localdate() - timedelta(days=1)
        late = make_issue(setup, proj, "К работе", team[2], yesterday)
        make_issue(setup, proj, "Готово", team[2], yesterday)
        overdue = analyze(setup, team).users[team[2].id].overdue
        assert [i.id for i in overdue] == [late.id]

    def test_blockers_listed(self, setup, team):
        proj = Project.objects.get(workspace=setup, name="Сайты")
        blocked = make_issue(setup, proj, "Блокер", team[0], timezone.localdate())
        assert [i.id for i in analyze(setup, team).blockers] == [blocked.id]

    def test_missing_assignee_or_due_excludes_backlog(self, setup, team):
        proj = Project.objects.get(workspace=setup, name="Сайты")
        no_owner = make_issue(setup, proj, "К работе", None, timezone.localdate())
        no_due = make_issue(setup, proj, "Сегодня", team[0], None)
        make_issue(setup, proj, "Бэклог", None, None)
        ok = make_issue(setup, proj, "Сегодня", team[0], timezone.localdate())
        ids = {i.id for i in analyze(setup, team).incomplete}
        assert ids == {no_owner.id, no_due.id}
        assert ok.id not in ids


@pytest.mark.unit
@pytest.mark.django_db
class TestMessages:
    def test_morning_asks_for_plan_when_today_empty(self, setup, team):
        report = analyze(setup, team)
        msg = format_user_message(team[0], report.users[team[0].id], "morning")
        assert "Сегодня" in msg and "10:00" in msg

    def test_morning_silent_when_plan_ok(self, setup, team):
        proj = Project.objects.get(workspace=setup, name="Сайты")
        for _ in range(3):
            make_issue(setup, proj, "Сегодня", team[0], timezone.localdate())
        report = analyze(setup, team)
        assert format_user_message(team[0], report.users[team[0].id], "morning") is None

    def test_morning_warns_over_limit(self, setup, team):
        proj = Project.objects.get(workspace=setup, name="Сайты")
        for _ in range(6):
            make_issue(setup, proj, "Сегодня", team[0], timezone.localdate())
        report = analyze(setup, team)
        assert "5" in format_user_message(team[0], report.users[team[0].id], "morning")

    def test_evening_lists_open_today_cards_and_daily_page(self, setup, team):
        proj = Project.objects.get(workspace=setup, name="Сайты")
        make_issue(setup, proj, "Сегодня", team[0], timezone.localdate(), name="Сверстать тарифы")
        report = analyze(setup, team)
        msg = format_user_message(team[0], report.users[team[0].id], "evening")
        assert "Сверстать тарифы" in msg
        assert "Дейли" in msg

    def test_stale_card_is_mentioned(self, setup, team):
        proj = Project.objects.get(workspace=setup, name="Сайты")
        old = make_issue(setup, proj, "Сегодня", team[0], timezone.localdate(), name="Огромная задача")
        age_state_change(setup, proj, old, 5)
        report = analyze(setup, team)
        msg = format_user_message(team[0], report.users[team[0].id], "evening")
        assert "Огромная задача" in msg and "разбить" in msg

    def test_manager_digest_sections(self, setup, team):
        proj = Project.objects.get(workspace=setup, name="Сайты")
        make_issue(setup, proj, "Блокер", team[0], timezone.localdate(), name="Ждём ассеты")
        make_issue(setup, proj, "К работе", None, timezone.localdate(), name="Без хозяина")
        text = format_manager_digest(analyze(setup, team))
        assert "Ждём ассеты" in text
        assert "Без хозяина" in text

    def test_manager_digest_none_when_all_clean(self, setup, team):
        assert format_manager_digest(analyze(setup, team)) is None


@pytest.mark.unit
@pytest.mark.django_db
class TestRunReminders:
    def test_sends_only_to_linked_team_members_with_something_to_say(self, setup, team):
        UserTelegramLink.objects.create(user=team[0], telegram_chat_id=111)
        sent = []
        run_reminders("morning", setup.slug, send=lambda chat, text: sent.append((chat, text)))
        assert [c for c, _ in sent] == [111]

    def test_manager_digest_goes_to_workspace_admins(self, setup, team, create_user):
        proj = Project.objects.get(workspace=setup, name="Сайты")
        make_issue(setup, proj, "Блокер", team[0], timezone.localdate(), name="Ждём ассеты")
        UserTelegramLink.objects.create(user=create_user, telegram_chat_id=999)  # workspace owner, role 20
        sent = []
        run_reminders("digest", setup.slug, send=lambda chat, text: sent.append((chat, text)))
        assert [c for c, _ in sent] == [999]
        assert "Ждём ассеты" in sent[0][1]

    def test_send_failure_does_not_stop_other_recipients(self, setup, team):
        UserTelegramLink.objects.create(user=team[0], telegram_chat_id=111)
        UserTelegramLink.objects.create(user=team[1], telegram_chat_id=222)
        sent = []

        def flaky(chat, text):
            if chat == 111:
                raise RuntimeError("boom")
            sent.append(chat)

        run_reminders("morning", setup.slug, send=flaky)
        assert sent == [222]


@pytest.mark.unit
class TestSchedule:
    def test_beat_schedule_has_weekday_reminders(self):
        from plane.celery import app

        schedule = app.conf.beat_schedule
        for key, task in {
            "it-morning-reminder": "plane.bgtasks.it_discipline_task.send_morning_reminders",
            "it-manager-digest": "plane.bgtasks.it_discipline_task.send_manager_digest",
            "it-evening-reminder": "plane.bgtasks.it_discipline_task.send_evening_reminders",
        }.items():
            assert schedule[key]["task"] == task
            assert "1-5" in repr(schedule[key]["schedule"]) or "mon-fri" in repr(schedule[key]["schedule"])

    def test_task_failure_is_logged_not_raised(self, monkeypatch):
        from plane.bgtasks import it_discipline_task

        def boom(*a, **k):
            raise RuntimeError("x")

        monkeypatch.setattr(it_discipline_task, "run_reminders", boom)
        it_discipline_task.send_morning_reminders()  # must not raise

    def test_task_uses_configured_workspace(self, monkeypatch):
        from plane.bgtasks import it_discipline_task

        calls = []
        monkeypatch.setattr(it_discipline_task, "run_reminders", lambda kind, slug: calls.append((kind, slug)))
        monkeypatch.setenv("IT_WORKSPACE_SLUG", "my-ws")
        it_discipline_task.send_evening_reminders()
        assert calls == [("evening", "my-ws")]


@pytest.mark.unit
class TestOverdueRefreshTask:
    def test_scheduled_nightly(self):
        from plane.celery import app

        entry = app.conf.beat_schedule["it-refresh-overdue-view"]
        assert entry["task"] == "plane.bgtasks.it_discipline_task.refresh_overdue_view_task"

    def test_task_refreshes_configured_workspace(self, monkeypatch):
        from plane.bgtasks import it_discipline_task

        calls = []
        monkeypatch.setattr(it_discipline_task, "refresh_overdue_for_slug", lambda slug: calls.append(slug))
        monkeypatch.setenv("IT_WORKSPACE_SLUG", "my-ws")
        it_discipline_task.refresh_overdue_view_task()
        assert calls == ["my-ws"]

    def test_task_failure_is_logged_not_raised(self, monkeypatch):
        from plane.bgtasks import it_discipline_task

        def boom(slug):
            raise RuntimeError("x")

        monkeypatch.setattr(it_discipline_task, "refresh_overdue_for_slug", boom)
        it_discipline_task.refresh_overdue_view_task()
