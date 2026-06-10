# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import uuid

from django.conf import settings
from django.db import models

from .base import BaseModel


class UserTelegramLink(BaseModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="telegram_link",
    )
    telegram_chat_id = models.BigIntegerField(unique=True)
    telegram_username = models.CharField(max_length=255, blank=True, default="")
    linked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "user_telegram_links"
        verbose_name = "User Telegram Link"
        verbose_name_plural = "User Telegram Links"

    def __str__(self):
        return f"{self.user.email} -> {self.telegram_chat_id}"


class TelegramLinkToken(BaseModel):
    """One-time token for linking Telegram account via bot /start command."""

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="telegram_link_tokens",
    )
    token = models.CharField(max_length=64, unique=True, db_index=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "telegram_link_tokens"
        ordering = ("-created_at",)

    @classmethod
    def create_for_user(cls, user, ttl_minutes=15):
        from django.utils import timezone
        from datetime import timedelta

        token = uuid.uuid4().hex
        return cls.objects.create(
            user=user,
            token=token,
            expires_at=timezone.now() + timedelta(minutes=ttl_minutes),
            created_by=user,
        )
