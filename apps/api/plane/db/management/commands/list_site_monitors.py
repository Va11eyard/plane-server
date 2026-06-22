# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.core.management.base import BaseCommand

from plane.db.models import MonitorRun, MonitorSite


class Command(BaseCommand):
    help = "List site monitor configurations and last run status"

    def handle(self, *args, **options):
        sites = MonitorSite.objects.order_by("sort_order", "name")
        if not sites.exists():
            self.stdout.write("No monitors. Run setup_site_monitors.")
            return

        last_run = MonitorRun.objects.order_by("-created_at").first()
        if last_run:
            self.stdout.write(
                f"Last run: {last_run.created_at} ({last_run.trigger}) "
                f"ok={last_run.ok_count} warn={last_run.warn_count} "
                f"critical={last_run.critical_count} error={last_run.error_count}\n"
            )

        for site in sites:
            status = "ON" if site.enabled else "OFF"
            base = site.base_url or "—"
            health = site.health_url or "—"
            self.stdout.write(
                f"[{status}] {site.name} ({site.slug})\n"
                f"  url: {base} | health: {health}\n"
                f"  ssh: {site.ssh_host or '—'} → {site.ssh_project_path or '—'}"
            )
