# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.core.management.base import BaseCommand

from plane.db.models import MonitorSite
from plane.utils.site_audit.galamat_endpoints import GALAMAT_HTTP_CHECKS
from plane.utils.site_audit.inlab_endpoints import INLAB_HTTP_CHECKS
from plane.utils.site_audit.odos_endpoints import ODOS_HTTP_CHECKS
from plane.utils.site_audit.senai_endpoints import SENAI_HTTP_CHECKS

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
        "checks_json": [{"type": "docker", "use_sudo": True}],
    },
    {
        "slug": "senai",
        "name": "SenAI",
        "sort_order": 4,
        "base_url": "https://sen-ai.kz/",
        "health_url": "",
        "ssh_host": "wellmen-senai",
        "ssh_project_path": "/opt/senai-src",
        "checks_json": [
            {"type": "docker", "use_sudo": True},
            *SENAI_HTTP_CHECKS,
        ],
    },
    {
        "slug": "pharma",
        "name": "Pharma",
        "sort_order": 5,
        "ssh_host": "pharma",
        "ssh_project_path": "/opt/pharma",
        "checks_json": [{"type": "docker", "compose_file": "docker-compose.ps-kz.yml", "use_sudo": True}],
    },
    {
        "slug": "odos",
        "name": "ODOS",
        "sort_order": 6,
        "base_url": "https://odos.kz/ru",
        "health_url": "https://api.odos.kz/healthz",
        "ssh_host": "odos",
        "ssh_project_path": "/opt/odos-src",
        "checks_json": [
            {"type": "docker", "compose_file": "docker-compose.prod.yml"},
            *ODOS_HTTP_CHECKS,
        ],
    },
    {
        "slug": "inlab",
        "name": "InLab",
        "sort_order": 7,
        "base_url": "https://inlab.kz/",
        "health_url": "https://inlab.kz/api/health",
        "ssh_host": "inlab",
        "ssh_project_path": "/opt/inlab-src",
        "checks_json": [
            {"type": "docker", "compose_file": "inlab.stack.ghcr.yml", "use_sudo": True},
            *INLAB_HTTP_CHECKS,
        ],
    },
    {
        "slug": "galamat",
        "name": "Galamat",
        "sort_order": 8,
        "base_url": "https://galamat.pro-ecta.kz/",
        "health_url": "",
        "ssh_host": "proecta",
        "ssh_project_path": "/var/www/galamat.pro-ecta.kz",
        "checks_json": [
            {"type": "systemd", "unit": "nginx"},
            *GALAMAT_HTTP_CHECKS,
        ],
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
