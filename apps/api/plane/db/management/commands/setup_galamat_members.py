# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import uuid

from django.core.management.base import BaseCommand, CommandError

from plane.db.models import Profile, Project, ProjectMember, User, Workspace, WorkspaceMember

IHEALTH_SLUG = "ihealth"
ADMIN_EMAIL = "admin@galamat.com"

ODOS_PROJECT_NAMES = ["ODOS Check UP", "ODOS Game"]

LAURA = {
    "email": "laura@galamat.com",
    "password": "Laura123!",
    "display_name": "Laura",
}

AIGANYM = {
    "email": "aiganym@galamat.com",
    "password": "Aiganym123!",
    "display_name": "Aiganym",
}


def ensure_user(email: str, password: str, display_name: str) -> tuple[User, bool]:
    user = User.objects.filter(email=email).first()
    created = False
    if user is None:
        user = User(
            email=email,
            username=uuid.uuid4().hex,
            display_name=display_name,
            is_active=True,
            is_email_verified=True,
        )
        user.set_password(password)
        user.save()
        created = True
    else:
        user.is_active = True
        user.is_email_verified = True
        user.set_password(password)
        user.save(update_fields=["password", "is_active", "is_email_verified"])
    return user, created


def ensure_profile(user: User, workspace: Workspace) -> None:
    profile, _ = Profile.objects.get_or_create(user=user)
    profile.last_workspace_id = workspace.id
    profile.is_onboarded = True
    profile.onboarding_step = {
        "profile_complete": True,
        "workspace_create": True,
        "workspace_invite": True,
        "workspace_join": True,
    }
    profile.save()


def ensure_workspace_member(
    workspace: Workspace,
    user: User,
    role: int,
    admin: User,
) -> tuple[WorkspaceMember, bool]:
    member, created = WorkspaceMember.objects.get_or_create(
        workspace=workspace,
        member=user,
        defaults={"role": role, "created_by": admin, "is_active": True},
    )
    if not created and (member.role != role or not member.is_active):
        member.role = role
        member.is_active = True
        member.save(update_fields=["role", "is_active"])
    return member, created


def ensure_project_member(
    project: Project,
    user: User,
    role: int,
    admin: User,
) -> tuple[ProjectMember, bool]:
    member, created = ProjectMember.objects.get_or_create(
        project=project,
        member=user,
        defaults={
            "workspace": project.workspace,
            "role": role,
            "created_by": admin,
            "is_active": True,
        },
    )
    if not created and (member.role != role or not member.is_active):
        member.role = role
        member.is_active = True
        member.save(update_fields=["role", "is_active"])
    return member, created


def get_odos_projects(workspace: Workspace) -> list[Project]:
    projects = list(Project.objects.filter(workspace=workspace, name__in=ODOS_PROJECT_NAMES))
    if len(projects) < len(ODOS_PROJECT_NAMES):
        fallback = list(Project.objects.filter(workspace=workspace, name__icontains="ODOS"))
        if fallback:
            projects = fallback
    if not projects:
        raise CommandError(
            f"No ODOS projects found in {workspace.slug}. Expected: {', '.join(ODOS_PROJECT_NAMES)}"
        )
    return projects


class Command(BaseCommand):
    help = "Create laura@galamat.com (ODOS-only) and aiganym@galamat.com (all workspaces admin)"

    def handle(self, *args, **options):
        admin = User.objects.filter(email=ADMIN_EMAIL).first()
        if not admin:
            raise CommandError(f"Admin user {ADMIN_EMAIL} not found")

        ihealth = Workspace.objects.filter(slug=IHEALTH_SLUG).first()
        if not ihealth:
            raise CommandError(f"Workspace '{IHEALTH_SLUG}' not found")

        odos_projects = get_odos_projects(ihealth)
        self.stdout.write(
            self.style.SUCCESS(
                f"ODOS projects: {', '.join(p.name for p in odos_projects)}"
            )
        )

        # Laura: iHealth member, ODOS projects only
        laura, laura_created = ensure_user(
            LAURA["email"], LAURA["password"], LAURA["display_name"]
        )
        if laura_created:
            self.stdout.write(self.style.SUCCESS(f"Created user {LAURA['email']}"))
        else:
            self.stdout.write(self.style.WARNING(f"Updated password for {LAURA['email']}"))

        ensure_workspace_member(ihealth, laura, role=15, admin=admin)
        self.stdout.write(self.style.SUCCESS(f"  {LAURA['email']} -> {IHEALTH_SLUG} (member)"))

        for other_ws in Workspace.objects.exclude(slug=IHEALTH_SLUG):
            removed = WorkspaceMember.objects.filter(workspace=other_ws, member=laura, is_active=True).update(
                is_active=False
            )
            if removed:
                self.stdout.write(
                    self.style.WARNING(f"  Deactivated {LAURA['email']} in {other_ws.slug}")
                )

        odos_project_ids = {p.id for p in odos_projects}
        for project in odos_projects:
            ensure_project_member(project, laura, role=15, admin=admin)
            self.stdout.write(self.style.SUCCESS(f"  {LAURA['email']} -> project {project.name}"))

        ProjectMember.objects.filter(
            member=laura,
            workspace=ihealth,
            is_active=True,
        ).exclude(project_id__in=odos_project_ids).update(is_active=False)

        ensure_profile(laura, ihealth)

        # Aiganym: admin in all workspaces and all projects
        aiganym, aiganym_created = ensure_user(
            AIGANYM["email"], AIGANYM["password"], AIGANYM["display_name"]
        )
        if aiganym_created:
            self.stdout.write(self.style.SUCCESS(f"Created user {AIGANYM['email']}"))
        else:
            self.stdout.write(self.style.WARNING(f"Updated password for {AIGANYM['email']}"))

        all_workspaces = list(Workspace.objects.all())
        last_workspace = all_workspaces[0] if all_workspaces else ihealth

        for workspace in all_workspaces:
            ensure_workspace_member(workspace, aiganym, role=20, admin=admin)
            self.stdout.write(self.style.SUCCESS(f"  {AIGANYM['email']} -> {workspace.slug} (admin)"))

            for project in Project.objects.filter(workspace=workspace):
                ensure_project_member(project, aiganym, role=20, admin=admin)

            last_workspace = workspace

        ensure_profile(aiganym, last_workspace)

        self.stdout.write(self.style.SUCCESS("Done. Users can log in at https://task.pro-ecta.kz"))
