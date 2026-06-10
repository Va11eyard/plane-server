# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from datetime import datetime

import jwt
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from plane.db.models import Profile, Project, ProjectMember, User, Workspace, WorkspaceMember, WorkspaceMemberInvite

INVITES = [
    ("syrym@galamat.com", 20),
    ("zhs@galamat.com", 20),
    ("dimash@galamat.com", 15),
]

WORKSPACE_SLUG = "ihealth"
ADMIN_EMAIL = "admin@pro-ecta.kz"


class Command(BaseCommand):
    help = "Invite users to iHealth workspace and add them as members if accounts exist"

    def handle(self, *args, **options):
        workspace = Workspace.objects.filter(slug=WORKSPACE_SLUG).first()
        if not workspace:
            raise CommandError(f"Workspace '{WORKSPACE_SLUG}' not found")

        admin = User.objects.filter(email=ADMIN_EMAIL).first()
        if not admin:
            raise CommandError(f"Admin user {ADMIN_EMAIL} not found")

        projects = list(Project.objects.filter(workspace=workspace))

        for email, role in INVITES:
            email = email.strip().lower()
            invite, created = WorkspaceMemberInvite.objects.get_or_create(
                email=email,
                workspace=workspace,
                defaults={
                    "token": jwt.encode(
                        {"email": email, "timestamp": datetime.now().timestamp()},
                        settings.SECRET_KEY,
                        algorithm="HS256",
                    ),
                    "role": role,
                    "accepted": False,
                    "created_by": admin,
                },
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"Invite created for {email}"))
            else:
                if invite.role != role:
                    invite.role = role
                    invite.save(update_fields=["role"])
                self.stdout.write(self.style.WARNING(f"Invite already exists for {email}"))

            user = User.objects.filter(email=email).first()
            if not user:
                self.stdout.write(f"  No user account yet for {email} — invite pending signup")
                continue

            member, member_created = WorkspaceMember.objects.get_or_create(
                workspace=workspace,
                member=user,
                defaults={"role": role, "created_by": admin, "is_active": True},
            )
            if not member_created and (member.role != role or not member.is_active):
                member.role = role
                member.is_active = True
                member.save(update_fields=["role", "is_active"])

            for project in projects:
                ProjectMember.objects.get_or_create(
                    project=project,
                    member=user,
                    defaults={
                        "workspace": workspace,
                        "role": 20 if role == 20 else 15,
                        "created_by": admin,
                    },
                )

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

            self.stdout.write(self.style.SUCCESS(f"  Member access granted for {email} (role {role})"))

        if workspace.owner_id != admin.id:
            workspace.owner = admin
            workspace.save(update_fields=["owner"])
            self.stdout.write(self.style.SUCCESS(f"Workspace owner set to {ADMIN_EMAIL}"))

        self.stdout.write(self.style.SUCCESS("Done. Users can refresh and open iHealth."))
