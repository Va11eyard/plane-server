# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import logging
import os
from dataclasses import dataclass, field
from typing import Any

from django.utils import timezone

from plane.db.models import GitHubCommitImportLog, GitHubRepoSync, User
from plane.utils.github_api import (
    GitHubAPIError,
    build_commit_url,
    commit_summary,
    extract_commit_files,
    fetch_branch_commits,
    fetch_commit_detail,
    fetch_compare_commits,
    is_merge_commit,
)
from plane.utils.github_commit_import_service import (
    commit_already_imported,
    import_commit_plan,
    short_sha,
)
from plane.utils.github_commit_plan_ai import build_commit_plan

logger = logging.getLogger("plane.github")


@dataclass
class CommitPreview:
    repo_sync_id: str
    repo_label: str
    sha: str
    short_sha: str
    message: str
    url: str
    plan: dict[str, Any]
    section_count: int
    task_count: int
    log_id: str | None = None
    already_imported: bool = False


@dataclass
class ScanResult:
    repo_sync: GitHubRepoSync
    up_to_date: bool
    previews: list[CommitPreview] = field(default_factory=list)
    error: str | None = None


DEFAULT_GITHUB_SYNC_IMPORTER = "dimash@galamat.com"


def get_github_sync_importer_emails() -> set[str]:
    raw = os.environ.get("GITHUB_SYNC_IMPORTER_EMAILS", "").strip()
    if not raw:
        raw = DEFAULT_GITHUB_SYNC_IMPORTER
    return {email.strip().lower() for email in raw.split(",") if email.strip()}


def can_sync_github_tasks(user: User) -> bool:
    if not user.email:
        return False
    return user.email.lower() in get_github_sync_importer_emails()


def scan_repo_sync(repo_sync: GitHubRepoSync, actor: User, trigger_source: str) -> ScanResult:
    try:
        commits = fetch_branch_commits(
            repo_sync.repo_owner,
            repo_sync.repo_name,
            repo_sync.default_branch,
            per_page=30,
        )
        if not commits:
            commits = fetch_compare_commits(
                repo_sync.repo_owner,
                repo_sync.repo_name,
                repo_sync.last_imported_sha,
                repo_sync.default_branch,
            )
    except GitHubAPIError as e:
        return ScanResult(repo_sync=repo_sync, up_to_date=False, error=str(e))

    previews: list[CommitPreview] = []
    limit = repo_sync.max_commits_per_run or 5
    last_sha = (repo_sync.last_imported_sha or "").strip().lower()

    for commit in commits:
        if len(previews) >= limit:
            break
        if repo_sync.skip_merge_commits and is_merge_commit(commit):
            continue
        summary = commit_summary(commit, repo_sync.repo_owner, repo_sync.repo_name)
        sha = summary["sha"]
        if not sha:
            continue
        if last_sha and sha.lower() == last_sha:
            break
        if commit_already_imported(repo_sync.project, sha):
            continue

        try:
            detail = fetch_commit_detail(repo_sync.repo_owner, repo_sync.repo_name, sha)
            files = extract_commit_files(detail)
            message = summary.get("full_message") or summary.get("message") or ""
            plan, plan_error = build_commit_plan(
                commit_message=message,
                files=files,
                use_llm=repo_sync.use_llm,
            )
            if plan_error or not plan:
                logger.warning("Plan failed for %s: %s", sha[:8], plan_error)
                continue
        except GitHubAPIError as e:
            logger.warning("Commit detail failed %s: %s", sha[:8], e)
            continue

        section_count = len(plan.get("sections") or [])
        task_count = sum(len(s.get("tasks") or []) for s in plan.get("sections") or [])

        commit_url = summary.get("url") or build_commit_url(
            repo_sync.repo_owner, repo_sync.repo_name, sha
        )

        log = GitHubCommitImportLog.objects.create(
            repo_sync=repo_sync,
            commit_sha=sha,
            commit_message=summary.get("message") or "",
            commit_url=commit_url,
            status=GitHubCommitImportLog.Status.PREVIEW,
            plan_json=plan,
            triggered_by=actor,
            trigger_source=trigger_source,
            created_by=actor,
        )

        previews.append(
            CommitPreview(
                repo_sync_id=str(repo_sync.id),
                repo_label=repo_sync.full_name,
                sha=sha,
                short_sha=short_sha(sha),
                message=summary.get("message") or "",
                url=summary.get("url") or "",
                plan=plan,
                section_count=section_count,
                task_count=task_count,
                log_id=str(log.id),
            )
        )

    return ScanResult(repo_sync=repo_sync, up_to_date=len(previews) == 0, previews=previews)


def scan_all_repos(actor: User, trigger_source: str = GitHubCommitImportLog.TriggerSource.CLI) -> list[ScanResult]:
    results: list[ScanResult] = []
    for repo_sync in GitHubRepoSync.objects.filter(enabled=True).select_related("project", "workspace", "assignee"):
        results.append(scan_repo_sync(repo_sync, actor, trigger_source))
    return results


def execute_import_log(log_id: str, actor: User) -> tuple[bool, str]:
    if not can_sync_github_tasks(actor):
        return False, "Импорт GitHub-задач доступен только уполномоченным пользователям"

    log = GitHubCommitImportLog.objects.select_related("repo_sync", "repo_sync__project").filter(pk=log_id).first()
    if not log:
        return False, "Лог импорта не найден"
    if log.status == GitHubCommitImportLog.Status.IMPORTED:
        return False, "Уже импортировано"

    epic, task_count, error = import_commit_plan(
        repo_sync=log.repo_sync,
        sha=log.commit_sha,
        plan=log.plan_json,
        actor=actor,
        import_log=log,
    )
    if error or not epic:
        log.status = GitHubCommitImportLog.Status.FAILED
        log.error_message = error or "Ошибка импорта"
        log.save(update_fields=["status", "error_message", "updated_at"])
        return False, error or "Ошибка импорта"

    return True, f"Импортировано {task_count} задач, эпик {epic.name[:80]}"


def skip_import_log(log_id: str) -> None:
    GitHubCommitImportLog.objects.filter(pk=log_id).update(
        status=GitHubCommitImportLog.Status.SKIPPED,
        updated_at=timezone.now(),
    )


def set_last_imported_sha(repo_sync: GitHubRepoSync, sha: str) -> None:
    repo_sync.last_imported_sha = sha
    repo_sync.last_imported_at = timezone.now()
    repo_sync.save(update_fields=["last_imported_sha", "last_imported_at", "updated_at"])
