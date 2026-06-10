# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import uuid

from django.core.management.base import BaseCommand, CommandError

from plane.db.models import User
from plane.license.models import Instance, InstanceAdmin

USERS = [
    {
        "email": "admin@pro-ecta.kz",
        "password": "administrator!",
        "display_name": "Admin",
        "instance_admin": True,
    },
    {
        "email": "syrym@galamat.com",
        "password": "Syrym123!",
        "display_name": "Сырым",
    },
    {
        "email": "zhs@galamat.com",
        "password": "Zhannur123!",
        "display_name": "Жаннур",
    },
    {
        "email": "dimash@galamat.com",
        "password": "Dimash123!",
        "display_name": "Димаш",
    },
]


class Command(BaseCommand):
    help = "Create or update instance users (idempotent)"

    def handle(self, *args, **options):
        for spec in USERS:
            email = spec["email"]
            user = User.objects.filter(email=email).first()
            if user is None:
                user = User(
                    email=email,
                    username=uuid.uuid4().hex,
                    display_name=spec.get("display_name", email.split("@")[0]),
                    is_active=True,
                    is_email_verified=True,
                )
                user.set_password(spec["password"])
                user.save()
                self.stdout.write(self.style.SUCCESS(f"Created user {email}"))
            else:
                user.is_active = True
                user.set_password(spec["password"])
                user.save(update_fields=["password", "is_active"])
                self.stdout.write(self.style.WARNING(f"Updated password for {email}"))

            if spec.get("instance_admin"):
                instance = Instance.objects.last()
                if instance is None:
                    raise CommandError("No instance found. Complete God Mode setup first.")
                _, created = InstanceAdmin.objects.get_or_create(
                    user=user, instance=instance, defaults={"role": 20}
                )
                if created:
                    self.stdout.write(self.style.SUCCESS(f"Granted instance admin to {email}"))
                else:
                    self.stdout.write(self.style.WARNING(f"{email} is already instance admin"))

        self.stdout.write(self.style.SUCCESS("All users ready."))
