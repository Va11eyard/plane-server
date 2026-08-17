# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.core.management.base import BaseCommand, CommandError

from plane.db.models import GitHubRepoSync, Project, User, Workspace

DEFAULT_OWNER = "Va11eyard"
DEFAULT_ASSIGNEE = "dimash@galamat.com"
WORKSPACE_SLUG = "ihealth"

REPOS = [
    {"repo": "ODOS", "project": "ODOS Check UP", "branch": "main"},
    {"repo": "galamat", "project": "Galamat", "branch": "master"},
    {"repo": "SenAI", "project": "Sen AI", "branch": "main"},
    {"repo": "inlab", "project": "InLab", "branch": "main"},
]


class Command(BaseCommand):
    help = "Seed default GitHub repo syncs (ODOS, Galamat, SenAI, InLab)"

    def handle(self, *args, **options):
        workspace = Workspace.objects.filter(slug=WORKSPACE_SLUG).first()
        if not workspace:
            raise CommandError(f"Workspace {WORKSPACE_SLUG} not found")

        assignee = User.objects.filter(email=DEFAULT_ASSIGNEE).first()
        if not assignee:
            raise CommandError(f"User {DEFAULT_ASSIGNEE} not found")

        actor = User.objects.filter(is_active=True).order_by("date_joined").first()

        for spec in REPOS:
            project = Project.objects.filter(workspace=workspace, name=spec["project"]).first()
            if not project:
                self.stdout.write(self.style.ERROR(f"Project '{spec['project']}' not found, skipped {spec['repo']}"))
                continue

            sync, created = GitHubRepoSync.objects.update_or_create(
                repo_owner=DEFAULT_OWNER,
                repo_name=spec["repo"],
                project=project,
                defaults={
                    "workspace": workspace,
                    "assignee": assignee,
                    "default_branch": spec.get("branch") or "main",
                    "enabled": True,
                    "use_llm": True,
                    "created_by": actor,
                },
            )
            verb = "Created" if created else "Updated"
            self.stdout.write(
                self.style.SUCCESS(
                    f"{verb} {sync.full_name} → {project.name} (last_sha={sync.last_imported_sha[:12] or '—'})"
                )
            )

        disabled = GitHubRepoSync.objects.filter(
            repo_owner="Va11eyard",
            repo_name="senai",
            enabled=True,
        ).update(enabled=False)
        if disabled:
            self.stdout.write(self.style.WARNING("Disabled stale sync Va11eyard/senai"))
