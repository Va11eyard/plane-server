# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.core.management.base import BaseCommand, CommandError

from plane.db.models import GitHubRepoSync, Project, User, Workspace


class Command(BaseCommand):
    help = "Configure GitHub repository sync to a Plane project"

    def add_arguments(self, parser):
        parser.add_argument("--owner", required=True)
        parser.add_argument("--repo", required=True)
        parser.add_argument("--workspace", required=True, help="Workspace slug")
        parser.add_argument("--project", required=True, help="Project name")
        parser.add_argument("--assignee", required=True, help="Assignee email")
        parser.add_argument("--branch", default="main")
        parser.add_argument("--last-sha", default="", help="Last imported commit SHA")
        parser.add_argument("--state-group", default="completed", choices=["completed", "unstarted", "backlog"])
        parser.add_argument("--no-llm", action="store_true")
        parser.add_argument("--disabled", action="store_true")

    def handle(self, *args, **options):
        workspace = Workspace.objects.filter(slug=options["workspace"]).first()
        if not workspace:
            raise CommandError(f"Workspace {options['workspace']} not found")

        project = Project.objects.filter(workspace=workspace, name=options["project"]).first()
        if not project:
            raise CommandError(f"Project '{options['project']}' not found")

        assignee = User.objects.filter(email=options["assignee"]).first()
        if not assignee:
            raise CommandError(f"User {options['assignee']} not found")

        actor = User.objects.filter(is_active=True).order_by("date_joined").first()

        defaults = {
            "workspace": workspace,
            "assignee": assignee,
            "default_branch": options["branch"],
            "issue_state_group": options["state_group"],
            "use_llm": not options["no_llm"],
            "enabled": not options["disabled"],
            "created_by": actor,
        }
        if options["last_sha"]:
            defaults["last_imported_sha"] = options["last_sha"]

        sync, created = GitHubRepoSync.objects.update_or_create(
            repo_owner=options["owner"],
            repo_name=options["repo"],
            project=project,
            defaults=defaults,
        )

        verb = "Created" if created else "Updated"
        self.stdout.write(
            self.style.SUCCESS(
                f"{verb} sync {sync.full_name} → {workspace.slug}/{project.name} "
                f"(last_sha={sync.last_imported_sha[:12] or '—'})"
            )
        )
