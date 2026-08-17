# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from datetime import datetime
from typing import Any

from django.db import transaction
from django.utils import timezone

from plane.db.models import GitHubCommitImportLog, GitHubRepoSync, Issue, IssueAssignee, IssueLink, Project, State, User
from plane.utils.github_api import build_commit_url


def short_sha(sha: str) -> str:
    return (sha or "")[:8]


def root_marker(sha: str) -> str:
    return f"[GitHub {short_sha(sha)}]"


def html_desc(text: str) -> str:
    return f"<p>{text}</p>"


def commit_already_imported(project: Project, sha: str) -> bool:
    marker = root_marker(sha)
    return Issue.objects.filter(project=project, name__startswith=marker).exists()


def get_import_state(project: Project, state_group: str) -> State | None:
    state = State.objects.filter(project=project, group=state_group).order_by("sequence").first()
    if state:
        return state
    if state_group != "unstarted":
        return State.objects.filter(project=project, group="unstarted").order_by("sequence").first()
    return State.objects.filter(project=project).order_by("sequence").first()


def validate_plan(plan: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    if not plan:
        return None, "Пустой план"
    title = (plan.get("epic_title") or plan.get("title") or "").strip()
    if not title:
        return None, "epic_title обязателен"
    sections = plan.get("sections") or []
    if not isinstance(sections, list):
        return None, "sections должен быть списком"
    normalized_sections: list[dict[str, Any]] = []
    for section in sections:
        if not isinstance(section, dict):
            continue
        section_title = (section.get("title") or "Изменения").strip()
        tasks = section.get("tasks") or []
        if not isinstance(tasks, list):
            tasks = []
        task_lines = [str(t).strip() for t in tasks if str(t).strip()]
        if section_title or task_lines:
            normalized_sections.append({"title": section_title[:255], "tasks": task_lines})
    if not normalized_sections:
        normalized_sections = [{"title": "Изменения", "tasks": [title[:255]]}]
    return {
        "epic_title": title[:255],
        "epic_summary": (plan.get("epic_summary") or plan.get("summary") or title).strip(),
        "sections": normalized_sections,
    }, None


def _create_issue(
    *,
    project: Project,
    workspace,
    name: str,
    description: str,
    state: State,
    owner: User,
    assignee: User | None,
    parent: Issue | None,
    mark_completed: bool,
) -> Issue:
    issue = Issue(
        project=project,
        workspace=workspace,
        name=name[:255],
        description_html=html_desc(description),
        description_stripped=description,
        state=state,
        parent=parent,
        priority="medium",
        created_by=owner,
        updated_by=owner,
    )
    issue.save()
    if mark_completed and state.group == "completed":
        Issue.objects.filter(pk=issue.pk).update(completed_at=timezone.now())
    if assignee:
        IssueAssignee.objects.get_or_create(
            issue=issue,
            assignee=assignee,
            project=project,
            workspace=workspace,
            defaults={"created_by": owner, "updated_by": owner},
        )
    return issue


@transaction.atomic
def import_commit_plan(
    *,
    repo_sync: GitHubRepoSync,
    sha: str,
    plan: dict[str, Any],
    actor: User,
    import_log: GitHubCommitImportLog | None = None,
) -> tuple[Issue | None, int, str | None]:
    normalized, error = validate_plan(plan)
    if error or not normalized:
        return None, 0, error or "Невалидный план"

    project = repo_sync.project
    workspace = repo_sync.workspace
    assignee = repo_sync.assignee
    if not assignee:
        return None, 0, "Не задан assignee в конфиге репозитория"

    if commit_already_imported(project, sha):
        return None, 0, f"Коммит {short_sha(sha)} уже импортирован"

    state = get_import_state(project, repo_sync.issue_state_group)
    if not state:
        return None, 0, "Не найден статус для импорта"

    mark_completed = repo_sync.issue_state_group == "completed"
    marker = root_marker(sha)
    epic_name = f"{marker} {normalized['epic_title']}"[:255]
    commit_url = build_commit_url(repo_sync.repo_owner, repo_sync.repo_name, sha)

    root = _create_issue(
        project=project,
        workspace=workspace,
        name=epic_name,
        description=normalized["epic_summary"],
        state=state,
        owner=actor,
        assignee=assignee,
        parent=None,
        mark_completed=mark_completed,
    )
    IssueLink.objects.create(
        issue=root,
        project=project,
        workspace=workspace,
        title="GitHub commit",
        url=commit_url,
        created_by=actor,
    )

    task_count = 0
    for section in normalized["sections"]:
        section_issue = _create_issue(
            project=project,
            workspace=workspace,
            name=section["title"][:255],
            description=f"Section from {commit_url}",
            state=state,
            owner=actor,
            assignee=assignee,
            parent=root,
            mark_completed=mark_completed,
        )
        for task_title in section["tasks"]:
            _create_issue(
                project=project,
                workspace=workspace,
                name=task_title[:255],
                description=f"Imported from GitHub commit {short_sha(sha)}",
                state=state,
                owner=actor,
                assignee=assignee,
                parent=section_issue,
                mark_completed=mark_completed,
            )
            task_count += 1

    try:
        from plane.utils.github_api import fetch_branch_commits

        head_commits = fetch_branch_commits(
            repo_sync.repo_owner,
            repo_sync.repo_name,
            repo_sync.default_branch,
            per_page=1,
        )
        head_sha = (head_commits[0].get("sha") or "") if head_commits else ""
    except Exception:
        head_sha = ""

    if head_sha:
        repo_sync.last_imported_sha = head_sha
    elif not repo_sync.last_imported_sha:
        repo_sync.last_imported_sha = sha
    repo_sync.last_imported_at = timezone.now()
    repo_sync.save(update_fields=["last_imported_sha", "last_imported_at", "updated_at"])

    if import_log:
        import_log.status = GitHubCommitImportLog.Status.IMPORTED
        import_log.epic_issue = root
        import_log.tasks_created = task_count
        import_log.plan_json = normalized
        import_log.error_message = ""
        import_log.save(
            update_fields=["status", "epic_issue", "tasks_created", "plan_json", "error_message", "updated_at"]
        )

    return root, task_count, None


def delete_commit_import(project: Project, sha: str) -> int:
    marker = root_marker(sha)
    qs = Issue.objects.filter(project=project, name__startswith=marker)
    count = qs.count()
    qs.delete()
    return count
