# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import json
import logging
import os

import requests
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from plane.app.views.base import BaseAPIView
from plane.authentication.session import BaseSessionAuthentication
from plane.db.models import TelegramLinkToken, UserTelegramLink

logger = logging.getLogger("plane.telegram")


def get_bot_token() -> str | None:
    return os.environ.get("TELEGRAM_BOT_TOKEN")


def send_telegram_document(chat_id: int, file_bytes: bytes, filename: str, caption: str = "") -> tuple[bool, str]:
    token = get_bot_token()
    if not token:
        return False, "TELEGRAM_BOT_TOKEN не настроен"
    url = f"https://api.telegram.org/bot{token}/sendDocument"
    files = {"document": (filename, file_bytes, "application/pdf")}
    data = {"chat_id": chat_id}
    if caption:
        data["caption"] = caption[:1024]
    try:
        resp = requests.post(url, data=data, files=files, timeout=60)
        if resp.status_code == 200 and resp.json().get("ok"):
            return True, ""
        return False, resp.json().get("description", resp.text)
    except Exception as e:
        logger.exception("Telegram send failed")
        return False, str(e)


class TelegramLinkStatusEndpoint(BaseAPIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [BaseSessionAuthentication]

    def get(self, request):
        link = UserTelegramLink.objects.filter(user=request.user).first()
        if not link:
            return Response({"linked": False}, status=status.HTTP_200_OK)
        return Response(
            {
                "linked": True,
                "telegram_username": link.telegram_username,
                "linked_at": link.linked_at.isoformat() if link.linked_at else None,
            },
            status=status.HTTP_200_OK,
        )


class TelegramLinkTokenEndpoint(BaseAPIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [BaseSessionAuthentication]

    def post(self, request):
        if not get_bot_token():
            return Response(
                {"error": "Telegram бот не настроен на сервере"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        TelegramLinkToken.objects.filter(user=request.user, used_at__isnull=True).update(
            used_at=timezone.now()
        )
        link_token = TelegramLinkToken.create_for_user(request.user)
        bot_username = os.environ.get("TELEGRAM_BOT_USERNAME", "")
        return Response(
            {
                "token": link_token.token,
                "expires_at": link_token.expires_at.isoformat(),
                "bot_username": bot_username,
                "instruction": f"Откройте бота @{bot_username} и отправьте: /start {link_token.token}"
                if bot_username
                else f"Отправьте боту: /start {link_token.token}",
            },
            status=status.HTTP_201_CREATED,
        )


@method_decorator(csrf_exempt, name="dispatch")
class TelegramWebhookEndpoint(BaseAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, secret):
        expected = os.environ.get("TELEGRAM_WEBHOOK_SECRET", "")
        if not expected or secret != expected:
            return Response({"error": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)

        try:
            update = request.data if isinstance(request.data, dict) else json.loads(request.body)
        except (json.JSONDecodeError, TypeError):
            return Response({"ok": True}, status=status.HTTP_200_OK)

        message = update.get("message") or update.get("edited_message")
        if not message:
            return Response({"ok": True}, status=status.HTTP_200_OK)

        text = (message.get("text") or "").strip()
        chat = message.get("chat") or {}
        chat_id = chat.get("id")
        username = chat.get("username") or ""

        if not text.startswith("/start") or chat_id is None:
            return Response({"ok": True}, status=status.HTTP_200_OK)

        parts = text.split(maxsplit=1)
        if len(parts) < 2:
            _reply(chat_id, "Отправьте команду с токеном: /start <ваш_код>")
            return Response({"ok": True}, status=status.HTTP_200_OK)

        token_value = parts[1].strip()
        link_token = (
            TelegramLinkToken.objects.filter(token=token_value, used_at__isnull=True)
            .select_related("user")
            .first()
        )
        if link_token is None or link_token.expires_at < timezone.now():
            _reply(chat_id, "Токен недействителен или истёк. Создайте новый в настройках Plane.")
            return Response({"ok": True}, status=status.HTTP_200_OK)

        user = link_token.user
        UserTelegramLink.objects.filter(user=user).delete()
        UserTelegramLink.objects.filter(telegram_chat_id=chat_id).delete()
        UserTelegramLink.objects.create(
            user=user,
            telegram_chat_id=chat_id,
            telegram_username=username,
            created_by=user,
        )
        link_token.used_at = timezone.now()
        link_token.save(update_fields=["used_at"])

        _reply(chat_id, f"Аккаунт привязан к {user.email}. Теперь можно отправлять отчёты из Plane.")
        return Response({"ok": True}, status=status.HTTP_200_OK)


def _reply(chat_id: int, text: str) -> None:
    token = get_bot_token()
    if not token:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=15,
        )
    except Exception:
        logger.exception("Failed to send Telegram reply")
