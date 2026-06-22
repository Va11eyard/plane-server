# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.db import models

from .base import BaseModel


class MonitorSite(BaseModel):
    slug = models.SlugField(max_length=64, unique=True)
    name = models.CharField(max_length=255)
    enabled = models.BooleanField(default=True)
    base_url = models.URLField(max_length=500, blank=True, default="")
    health_url = models.URLField(max_length=500, blank=True, default="")
    ssh_host = models.CharField(max_length=255, blank=True, default="")
    ssh_project_path = models.CharField(max_length=500, blank=True, default="")
    domain_renewal_at = models.DateField(null=True, blank=True)
    vps_renewal_at = models.DateField(null=True, blank=True)
    checks_json = models.JSONField(default=list, blank=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = "monitor_sites"
        ordering = ("sort_order", "name")
        verbose_name = "Monitor Site"
        verbose_name_plural = "Monitor Sites"

    def __str__(self):
        return self.name


class MonitorRun(BaseModel):
    class Trigger(models.TextChoices):
        SCHEDULED = "scheduled", "Scheduled"
        ALERT = "alert", "Alert"
        MANUAL = "manual", "Manual"
        TELEGRAM = "telegram", "Telegram"

    trigger = models.CharField(max_length=16, choices=Trigger.choices, default=Trigger.SCHEDULED)
    fast_only = models.BooleanField(default=False)
    sites_checked = models.PositiveSmallIntegerField(default=0)
    ok_count = models.PositiveSmallIntegerField(default=0)
    warn_count = models.PositiveSmallIntegerField(default=0)
    critical_count = models.PositiveSmallIntegerField(default=0)
    error_count = models.PositiveSmallIntegerField(default=0)
    duration_ms = models.PositiveIntegerField(default=0)
    summary = models.TextField(blank=True, default="")

    class Meta:
        db_table = "monitor_runs"
        ordering = ("-created_at",)

    def __str__(self):
        return f"{self.trigger} ({self.created_at})"


class MonitorCheckResult(BaseModel):
    class Status(models.TextChoices):
        OK = "ok", "OK"
        WARN = "warn", "Warn"
        CRITICAL = "critical", "Critical"
        ERROR = "error", "Error"
        SKIPPED = "skipped", "Skipped"

    run = models.ForeignKey(MonitorRun, on_delete=models.CASCADE, related_name="results")
    site = models.ForeignKey(MonitorSite, on_delete=models.CASCADE, related_name="check_results")
    check_type = models.CharField(max_length=64)
    check_key = models.CharField(max_length=255, blank=True, default="")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OK)
    message = models.TextField(blank=True, default="")
    details_json = models.JSONField(default=dict, blank=True)
    duration_ms = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "monitor_check_results"
        ordering = ("site__sort_order", "check_type")

    def __str__(self):
        return f"{self.site.slug}/{self.check_type}: {self.status}"
