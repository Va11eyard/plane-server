# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.urls import path

from plane.app.views.telegram import (
    TelegramLinkStatusEndpoint,
    TelegramLinkTokenEndpoint,
    TelegramWebhookEndpoint,
)

urlpatterns = [
    path("users/me/telegram/", TelegramLinkStatusEndpoint.as_view(), name="telegram-link-status"),
    path("users/me/telegram/link-token/", TelegramLinkTokenEndpoint.as_view(), name="telegram-link-token"),
    path(
        "telegram/webhook/<str:secret>/",
        TelegramWebhookEndpoint.as_view(),
        name="telegram-webhook",
    ),
]
