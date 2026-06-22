# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import logging
import socket
import ssl
import time
from datetime import datetime, timezone
from urllib.parse import urlparse

from plane.utils.site_audit.types import (
    HTTP_TIMEOUT,
    ProbeResult,
    SSL_CRITICAL_DAYS,
    SSL_WARN_DAYS,
    STATUS_CRITICAL,
    STATUS_ERROR,
    STATUS_OK,
    STATUS_SKIPPED,
    STATUS_WARN,
)

logger = logging.getLogger("plane.site_audit")


def _hostname_from_url(url: str) -> str | None:
    if not url:
        return None
    parsed = urlparse(url if "://" in url else f"https://{url}")
    return parsed.hostname


def probe_ssl_expiry(url: str) -> ProbeResult:
    start = time.monotonic()
    host = _hostname_from_url(url)
    if not host:
        return ProbeResult(
            check_type="ssl_expiry",
            status=STATUS_SKIPPED,
            message="URL не задан",
        )

    try:
        context = ssl.create_default_context()
        with socket.create_connection((host, 443), timeout=HTTP_TIMEOUT) as sock:
            with context.wrap_socket(sock, server_hostname=host) as ssock:
                cert = ssock.getpeercert()
        not_after = cert.get("notAfter")
        if not not_after:
            raise ValueError("notAfter отсутствует в сертификате")
        expires = datetime.strptime(not_after, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
        days_left = (expires - datetime.now(timezone.utc)).days
        duration_ms = int((time.monotonic() - start) * 1000)

        if days_left < SSL_CRITICAL_DAYS:
            status = STATUS_CRITICAL
            message = f"SSL истекает через {days_left} дн. ({expires.date()})"
        elif days_left < SSL_WARN_DAYS:
            status = STATUS_WARN
            message = f"SSL истекает через {days_left} дн. ({expires.date()})"
        else:
            status = STATUS_OK
            message = f"SSL действителен ещё {days_left} дн. (до {expires.date()})"

        return ProbeResult(
            check_type="ssl_expiry",
            status=status,
            message=message,
            details={"host": host, "days_left": days_left, "expires": expires.isoformat()},
            duration_ms=duration_ms,
        )
    except Exception as e:
        logger.warning("SSL probe failed for %s: %s", host, e)
        return ProbeResult(
            check_type="ssl_expiry",
            status=STATUS_ERROR,
            message=f"Не удалось проверить SSL: {e}",
            details={"host": host},
            duration_ms=int((time.monotonic() - start) * 1000),
        )
