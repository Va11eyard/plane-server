# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.core.management.base import BaseCommand, CommandError

from plane.db.models import (
    DEFAULT_STATES,
    GitHubRepoSync,
    Project,
    ProjectMember,
    State,
    User,
    Workspace,
    WorkspaceMember,
)

DEFAULT_OWNER = "Va11eyard"
DEFAULT_ASSIGNEE = "dimash@galamat.com"
WORKSPACE_SLUG = "ihealth"

REPOS = [
    {"repo": "ODOS", "project": "ODOS Check UP", "branch": "main"},
    {"repo": "galamat", "project": "Galamat", "branch": "master"},
    {"repo": "SenAI", "project": "Sen AI", "branch": "main"},
    {"repo": "inlab", "project": "InLab", "branch": "main"},
    {"repo": "Wellmen", "project": "Wellmen", "branch": "main"},
    {"repo": "ECG", "project": "ECG", "branch": "main", "identifier": "ECG"},
    {"repo": "ai-sport", "project": "ai-sport", "branch": "main", "identifier": "AISPORT"},
]


def ensure_project(workspace: Workspace, name: str, identifier: str, actor: User) -> Project:
    project = Project.objects.filter(workspace=workspace, name=name).first()
    if project:
        return project

    used = set(Project.objects.filter(workspace=workspace).values_list("identifier", flat=True))
    candidate = (identifier or "PRJ").upper()[:12]
    n = 1
    while candidate in used:
        suffix = str(n)
        candidate = (candidate[: 12 - len(suffix)] + suffix)[:12]
        n += 1

    project = Project.objects.create(
        workspace=workspace,
        name=name,
        identifier=candidate,
        created_by=actor,
    )
    State.objects.bulk_create(
        [
            State(
                name=state["name"],
                color=state["color"],
                project=project,
                sequence=state["sequence"],
                workspace=workspace,
                group=state["group"],
                default=state.get("default", False),
                created_by=actor,
            )
            for state in DEFAULT_STATES
        ]
    )
    for membership in WorkspaceMember.objects.filter(workspace=workspace, is_active=True).select_related("member"):
        ProjectMember.objects.get_or_create(
            project=project,
            member=membership.member,
            defaults={
                "workspace": workspace,
                "role": membership.role,
                "created_by": actor,
                "is_active": True,
            },
        )
    return project


class Command(BaseCommand):
    help = "Seed default GitHub repo syncs (ODOS, Galamat, SenAI, InLab, Wellmen, ECG, ai-sport)"

    def handle(self, *args, **options):
        workspace = Workspace.objects.filter(slug=WORKSPACE_SLUG).first()
        if not workspace:
            raise CommandError(f"Workspace {WORKSPACE_SLUG} not found")

        assignee = User.objects.filter(email=DEFAULT_ASSIGNEE).first()
        if not assignee:
            raise CommandError(f"User {DEFAULT_ASSIGNEE} not found")

        actor = User.objects.filter(is_active=True).order_by("date_joined").first()

        for spec in REPOS:
            project = ensure_project(
                workspace,
                spec["project"],
                spec.get("identifier") or spec["repo"],
                actor,
            )

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
