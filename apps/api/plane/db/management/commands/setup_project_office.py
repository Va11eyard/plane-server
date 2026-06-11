# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import uuid

from django.core.management.base import BaseCommand, CommandError

from plane.bgtasks.workspace_seed_task import workspace_seed
from plane.db.models import Profile, User, Workspace, WorkspaceMember
from plane.license.models import Instance, InstanceAdmin

WORKSPACE_NAME = "Project Office"
WORKSPACE_SLUG = "project-office"
ADMIN_EMAIL = "admin@galamat.com"
ADMIN_PASSWORD = "Galamat123!"

MEMBERS = [
    {
        "email": "akbota@galamat.com",
        "password": "Akbota123!",
        "display_name": "Akbota",
        "role": 20,
    },
    {
        "email": "zhuldyz@galamat.com",
        "password": "Akbota123!",
        "display_name": "Жулдыз",
        "role": 20,
    },
]


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


def ensure_instance_admin(user: User) -> bool:
    instance = Instance.objects.last()
    if instance is None:
        raise CommandError("No instance found. Complete God Mode setup first.")
    _, created = InstanceAdmin.objects.get_or_create(user=user, instance=instance, defaults={"role": 20})
    return created


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


class Command(BaseCommand):
    help = "Create Project Office workspace, instance admin admin@galamat.com, and member users"

    def handle(self, *args, **options):
        admin, admin_created = ensure_user(ADMIN_EMAIL, ADMIN_PASSWORD, "Admin Galamat")
        if admin_created:
            self.stdout.write(self.style.SUCCESS(f"Created user {ADMIN_EMAIL}"))
        else:
            self.stdout.write(self.style.WARNING(f"Updated password for {ADMIN_EMAIL}"))

        if ensure_instance_admin(admin):
            self.stdout.write(self.style.SUCCESS(f"Granted instance admin to {ADMIN_EMAIL}"))
        else:
            self.stdout.write(self.style.WARNING(f"{ADMIN_EMAIL} is already instance admin"))

        workspace = Workspace.objects.filter(slug=WORKSPACE_SLUG).first()
        workspace_created = False
        if workspace is None:
            workspace = Workspace.objects.create(
                name=WORKSPACE_NAME,
                slug=WORKSPACE_SLUG,
                owner=admin,
                created_by=admin,
            )
            workspace_created = True
            self.stdout.write(self.style.SUCCESS(f"Created workspace {WORKSPACE_NAME} ({WORKSPACE_SLUG})"))
        else:
            if workspace.owner_id != admin.id:
                workspace.owner = admin
                workspace.save(update_fields=["owner"])
                self.stdout.write(self.style.SUCCESS(f"Workspace owner set to {ADMIN_EMAIL}"))

        WorkspaceMember.objects.get_or_create(
            workspace=workspace,
            member=admin,
            defaults={"role": 20, "created_by": admin, "is_active": True},
        )

        if workspace_created:
            workspace_seed(workspace.id)
            self.stdout.write(self.style.SUCCESS("Workspace seeded with default project"))

        for spec in MEMBERS:
            user, created = ensure_user(spec["email"], spec["password"], spec["display_name"])
            if created:
                self.stdout.write(self.style.SUCCESS(f"Created user {spec['email']}"))
            else:
                self.stdout.write(self.style.WARNING(f"Updated password for {spec['email']}"))

            member, member_created = WorkspaceMember.objects.get_or_create(
                workspace=workspace,
                member=user,
                defaults={"role": spec["role"], "created_by": admin, "is_active": True},
            )
            if not member_created and (member.role != spec["role"] or not member.is_active):
                member.role = spec["role"]
                member.is_active = True
                member.save(update_fields=["role", "is_active"])

            ensure_profile(user, workspace)
            self.stdout.write(self.style.SUCCESS(f"  Added {spec['email']} to {WORKSPACE_SLUG} (role {spec['role']})"))

        ensure_profile(admin, workspace)
        self.stdout.write(self.style.SUCCESS("Done. Instance admin sees all workspaces after re-login."))
