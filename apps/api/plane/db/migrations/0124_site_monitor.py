# Generated migration for site monitoring

import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("db", "0123_github_repo_sync"),
    ]

    operations = [
        migrations.CreateModel(
            name="MonitorSite",
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
                ("slug", models.SlugField(max_length=64, unique=True)),
                ("name", models.CharField(max_length=255)),
                ("enabled", models.BooleanField(default=True)),
                ("base_url", models.URLField(blank=True, default="", max_length=500)),
                ("health_url", models.URLField(blank=True, default="", max_length=500)),
                ("ssh_host", models.CharField(blank=True, default="", max_length=255)),
                ("ssh_project_path", models.CharField(blank=True, default="", max_length=500)),
                ("domain_renewal_at", models.DateField(blank=True, null=True)),
                ("vps_renewal_at", models.DateField(blank=True, null=True)),
                ("checks_json", models.JSONField(blank=True, default=list)),
                ("sort_order", models.PositiveSmallIntegerField(default=0)),
                (
                    "created_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_created_by",
                        to="db.user",
                        verbose_name="Created By",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_updated_by",
                        to="db.user",
                        verbose_name="Last Modified By",
                    ),
                ),
            ],
            options={
                "verbose_name": "Monitor Site",
                "verbose_name_plural": "Monitor Sites",
                "db_table": "monitor_sites",
                "ordering": ("sort_order", "name"),
            },
        ),
        migrations.CreateModel(
            name="MonitorRun",
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
                (
                    "trigger",
                    models.CharField(
                        choices=[
                            ("scheduled", "Scheduled"),
                            ("alert", "Alert"),
                            ("manual", "Manual"),
                            ("telegram", "Telegram"),
                        ],
                        default="scheduled",
                        max_length=16,
                    ),
                ),
                ("fast_only", models.BooleanField(default=False)),
                ("sites_checked", models.PositiveSmallIntegerField(default=0)),
                ("ok_count", models.PositiveSmallIntegerField(default=0)),
                ("warn_count", models.PositiveSmallIntegerField(default=0)),
                ("critical_count", models.PositiveSmallIntegerField(default=0)),
                ("error_count", models.PositiveSmallIntegerField(default=0)),
                ("duration_ms", models.PositiveIntegerField(default=0)),
                ("summary", models.TextField(blank=True, default="")),
                (
                    "created_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_created_by",
                        to="db.user",
                        verbose_name="Created By",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_updated_by",
                        to="db.user",
                        verbose_name="Last Modified By",
                    ),
                ),
            ],
            options={
                "db_table": "monitor_runs",
                "ordering": ("-created_at",),
            },
        ),
        migrations.CreateModel(
            name="MonitorCheckResult",
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
                ("check_type", models.CharField(max_length=64)),
                ("check_key", models.CharField(blank=True, default="", max_length=255)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("ok", "OK"),
                            ("warn", "Warn"),
                            ("critical", "Critical"),
                            ("error", "Error"),
                            ("skipped", "Skipped"),
                        ],
                        default="ok",
                        max_length=16,
                    ),
                ),
                ("message", models.TextField(blank=True, default="")),
                ("details_json", models.JSONField(blank=True, default=dict)),
                ("duration_ms", models.PositiveIntegerField(default=0)),
                (
                    "created_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_created_by",
                        to="db.user",
                        verbose_name="Created By",
                    ),
                ),
                (
                    "run",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, related_name="results", to="db.monitorrun"
                    ),
                ),
                (
                    "site",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE, related_name="check_results", to="db.monitorsite"
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_updated_by",
                        to="db.user",
                        verbose_name="Last Modified By",
                    ),
                ),
            ],
            options={
                "db_table": "monitor_check_results",
                "ordering": ("site__sort_order", "check_type"),
            },
        ),
    ]
