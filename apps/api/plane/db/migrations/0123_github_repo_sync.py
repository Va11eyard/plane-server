# Generated migration for GitHub commit sync

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("db", "0122_user_telegram_link"),
    ]

    operations = [
        migrations.CreateModel(
            name="GitHubRepoSync",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Created At")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Last Modified At")),
                ("deleted_at", models.DateTimeField(blank=True, null=True, verbose_name="Deleted At")),
                (
                    "id",
                    models.UUIDField(
                        db_index=True, default=uuid.uuid4, editable=False, primary_key=True, serialize=False, unique=True
                    ),
                ),
                ("repo_owner", models.CharField(max_length=255)),
                ("repo_name", models.CharField(max_length=255)),
                ("default_branch", models.CharField(default="main", max_length=255)),
                ("last_imported_sha", models.CharField(blank=True, default="", max_length=64)),
                ("last_imported_at", models.DateTimeField(blank=True, null=True)),
                ("issue_state_group", models.CharField(default="completed", max_length=32)),
                ("enabled", models.BooleanField(default=True)),
                ("use_llm", models.BooleanField(default=True)),
                ("max_commits_per_run", models.PositiveSmallIntegerField(default=5)),
                ("skip_merge_commits", models.BooleanField(default=True)),
                (
                    "assignee",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="github_repo_sync_assignments",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "created_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_created_by",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Created By",
                    ),
                ),
                (
                    "project",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="github_repo_syncs",
                        to="db.project",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_updated_by",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Last Modified By",
                    ),
                ),
                (
                    "workspace",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="github_repo_syncs",
                        to="db.workspace",
                    ),
                ),
            ],
            options={
                "verbose_name": "GitHub Repo Sync",
                "verbose_name_plural": "GitHub Repo Syncs",
                "db_table": "github_repo_syncs",
            },
        ),
        migrations.CreateModel(
            name="GitHubCommitImportLog",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Created At")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Last Modified At")),
                ("deleted_at", models.DateTimeField(blank=True, null=True, verbose_name="Deleted At")),
                (
                    "id",
                    models.UUIDField(
                        db_index=True, default=uuid.uuid4, editable=False, primary_key=True, serialize=False, unique=True
                    ),
                ),
                ("commit_sha", models.CharField(db_index=True, max_length=64)),
                ("commit_message", models.TextField(blank=True, default="")),
                ("commit_url", models.URLField(max_length=500)),
                ("status", models.CharField(default="pending", max_length=16)),
                ("tasks_created", models.PositiveIntegerField(default=0)),
                ("plan_json", models.JSONField(blank=True, default=dict)),
                ("trigger_source", models.CharField(default="cli", max_length=16)),
                ("error_message", models.TextField(blank=True, default="")),
                (
                    "created_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_created_by",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Created By",
                    ),
                ),
                (
                    "epic_issue",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="github_import_logs",
                        to="db.issue",
                    ),
                ),
                (
                    "repo_sync",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="import_logs",
                        to="db.githubreposync",
                    ),
                ),
                (
                    "triggered_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="github_import_logs",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_updated_by",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Last Modified By",
                    ),
                ),
            ],
            options={
                "db_table": "github_commit_import_logs",
                "ordering": ("-created_at",),
            },
        ),
        migrations.AddConstraint(
            model_name="githubreposync",
            constraint=models.UniqueConstraint(
                condition=models.Q(("deleted_at__isnull", True)),
                fields=("repo_owner", "repo_name", "project"),
                name="unique_github_repo_sync_per_project",
            ),
        ),
    ]
