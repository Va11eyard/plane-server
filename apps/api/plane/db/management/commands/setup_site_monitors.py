# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.core.management.base import BaseCommand

from plane.db.models import MonitorSite

DEFAULT_SITES = [
    {
        "slug": "proecta",
        "name": "ProEcta",
        "sort_order": 1,
        "ssh_host": "proecta",
        "ssh_project_path": "/opt/proecta-src",
        "checks_json": [
            {"type": "systemd", "unit": "nginx"},
            {"type": "systemd", "unit": "proecta-backend"},
        ],
    },
    {
        "slug": "cornea",
        "name": "Cornea",
        "sort_order": 2,
        "ssh_host": "proecta",
        "ssh_project_path": "/opt/cornea",
        "checks_json": [{"type": "systemd", "unit": "cornea"}],
    },
    {
        "slug": "wellmen",
        "name": "Wellmen",
        "sort_order": 3,
        "ssh_host": "wellmen-senai",
        "ssh_project_path": "/opt/wellmen-src",
        "checks_json": [{"type": "docker"}],
    },
    {
        "slug": "senai",
        "name": "SenAI",
        "sort_order": 4,
        "ssh_host": "wellmen-senai",
        "ssh_project_path": "/opt/senai-src",
        "checks_json": [{"type": "docker"}],
    },
    {
        "slug": "pharma",
        "name": "Pharma",
        "sort_order": 5,
        "ssh_host": "pharma",
        "ssh_project_path": "/opt/pharma",
        "checks_json": [{"type": "docker"}],
    },
    {
        "slug": "odos",
        "name": "ODOS",
        "sort_order": 6,
        "ssh_host": "odos",
        "ssh_project_path": "/opt/odos-src",
        "checks_json": [{"type": "docker"}],
    },
    {
        "slug": "inlab",
        "name": "InLab",
        "sort_order": 7,
        "ssh_host": "",
        "ssh_project_path": "/opt/inlab-src",
        "checks_json": [{"type": "docker"}],
    },
]


class Command(BaseCommand):
    help = "Seed or update default site monitor configurations"

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Update existing sites with defaults")

    def handle(self, *args, **options):
        for data in DEFAULT_SITES:
            defaults = {k: v for k, v in data.items() if k != "slug"}
            site, created = MonitorSite.objects.update_or_create(
                slug=data["slug"],
                defaults=defaults,
            )
            verb = "Created" if created else "Updated"
            self.stdout.write(f"{verb} {site.name} ({site.slug}) ssh={site.ssh_host or '—'}")
        self.stdout.write(self.style.SUCCESS("Done. Set URLs: update_site_monitor --slug odos --base-url https://..."))
