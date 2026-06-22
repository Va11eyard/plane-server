# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.conf import settings
from django.db import models

from .base import BaseModel
from .project import Project
from .workspace import Workspace


class GitHubRepoSync(BaseModel):
    repo_owner = models.CharField(max_length=255)
    repo_name = models.CharField(max_length=255)
    default_branch = models.CharField(max_length=255, default="main")
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name="github_repo_syncs")
    project = models.ForeignKey(Project, on_delete=models.CASCADE, related_name="github_repo_syncs")
    assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="github_repo_sync_assignments",
    )
    last_imported_sha = models.CharField(max_length=64, blank=True, default="")
    last_imported_at = models.DateTimeField(null=True, blank=True)
    issue_state_group = models.CharField(max_length=32, default="completed")
    enabled = models.BooleanField(default=True)
    use_llm = models.BooleanField(default=True)
    max_commits_per_run = models.PositiveSmallIntegerField(default=5)
    skip_merge_commits = models.BooleanField(default=True)

    class Meta:
        db_table = "github_repo_syncs"
        verbose_name = "GitHub Repo Sync"
        verbose_name_plural = "GitHub Repo Syncs"
        constraints = [
            models.UniqueConstraint(
                fields=["repo_owner", "repo_name", "project"],
                condition=models.Q(deleted_at__isnull=True),
                name="unique_github_repo_sync_per_project",
            )
        ]

    def __str__(self):
        return f"{self.repo_owner}/{self.repo_name} → {self.project.name}"

    @property
    def full_name(self) -> str:
        return f"{self.repo_owner}/{self.repo_name}"


class GitHubCommitImportLog(BaseModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PREVIEW = "preview", "Preview"
        IMPORTED = "imported", "Imported"
        SKIPPED = "skipped", "Skipped"
        FAILED = "failed", "Failed"

    class TriggerSource(models.TextChoices):
        TELEGRAM = "telegram", "Telegram"
        CLI = "cli", "CLI"
        API = "api", "API"

    repo_sync = models.ForeignKey(GitHubRepoSync, on_delete=models.CASCADE, related_name="import_logs")
    commit_sha = models.CharField(max_length=64, db_index=True)
    commit_message = models.TextField(blank=True, default="")
    commit_url = models.URLField(max_length=500)
    epic_issue = models.ForeignKey(
        "db.Issue",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="github_import_logs",
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    tasks_created = models.PositiveIntegerField(default=0)
    plan_json = models.JSONField(default=dict, blank=True)
    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="github_import_logs",
    )
    trigger_source = models.CharField(max_length=16, choices=TriggerSource.choices, default=TriggerSource.CLI)
    error_message = models.TextField(blank=True, default="")

    class Meta:
        db_table = "github_commit_import_logs"
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.commit_sha[:8]} ({self.status})"
