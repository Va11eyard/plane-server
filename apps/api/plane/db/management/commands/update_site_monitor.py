# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from datetime import datetime

from django.core.management.base import BaseCommand, CommandError

from plane.db.models import MonitorSite


class Command(BaseCommand):
    help = "Update a site monitor configuration"

    def add_arguments(self, parser):
        parser.add_argument("--slug", required=True)
        parser.add_argument("--base-url", default="")
        parser.add_argument("--health-url", default="")
        parser.add_argument("--ssh-host", default="")
        parser.add_argument("--ssh-path", default="")
        parser.add_argument("--domain-renewal", help="YYYY-MM-DD")
        parser.add_argument("--vps-renewal", help="YYYY-MM-DD")
        parser.add_argument("--enabled", choices=["true", "false"])
        parser.add_argument("--name", default="")

    def handle(self, *args, **options):
        site = MonitorSite.objects.filter(slug=options["slug"]).first()
        if not site:
            raise CommandError(f"Site {options['slug']} not found. Run setup_site_monitors.")

        if options["base_url"]:
            site.base_url = options["base_url"]
        if options["health_url"]:
            site.health_url = options["health_url"]
        if options["ssh_host"]:
            site.ssh_host = options["ssh_host"]
        if options["ssh_path"]:
            site.ssh_project_path = options["ssh_path"]
        if options["name"]:
            site.name = options["name"]
        if options["domain_renewal"]:
            site.domain_renewal_at = datetime.strptime(options["domain_renewal"], "%Y-%m-%d").date()
        if options["vps_renewal"]:
            site.vps_renewal_at = datetime.strptime(options["vps_renewal"], "%Y-%m-%d").date()
        if options["enabled"] == "true":
            site.enabled = True
        elif options["enabled"] == "false":
            site.enabled = False

        site.save()
        self.stdout.write(self.style.SUCCESS(f"Updated {site.name}: base={site.base_url or '—'} health={site.health_url or '—'}"))
