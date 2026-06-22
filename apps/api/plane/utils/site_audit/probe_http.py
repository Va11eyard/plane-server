# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import logging
import time

import requests

from plane.utils.site_audit.types import (
    HTTP_TIMEOUT,
    ProbeResult,
    STATUS_CRITICAL,
    STATUS_ERROR,
    STATUS_OK,
    STATUS_SKIPPED,
    STATUS_WARN,
)

logger = logging.getLogger("plane.site_audit")


def probe_http_url(url: str, *, check_type: str, label: str | None = None) -> ProbeResult:
    start = time.monotonic()
    if not url:
        return ProbeResult(
            check_type=check_type,
            status=STATUS_SKIPPED,
            message=f"{label or check_type}: URL не задан",
        )

    try:
        resp = requests.get(
            url,
            timeout=HTTP_TIMEOUT,
            allow_redirects=True,
            headers={"User-Agent": "PlaneSiteAudit/1.0"},
        )
        duration_ms = int((time.monotonic() - start) * 1000)
        status_code = resp.status_code

        if 200 <= status_code < 400:
            status = STATUS_OK
            message = f"{label or url}: HTTP {status_code}, {duration_ms} ms"
        elif 400 <= status_code < 500:
            status = STATUS_WARN
            message = f"{label or url}: HTTP {status_code}"
        else:
            status = STATUS_CRITICAL
            message = f"{label or url}: HTTP {status_code}"

        details: dict = {"url": url, "status_code": status_code, "latency_ms": duration_ms}
        if check_type == "health_url":
            try:
                data = resp.json()
                if isinstance(data, dict):
                    details["body"] = data
                    if data.get("status") not in (None, "ok", "healthy"):
                        status = STATUS_WARN
                        message = f"Health: status={data.get('status')}"
            except Exception:
                if status == STATUS_OK:
                    status = STATUS_WARN
                    message = f"Health URL не вернул JSON ({status_code})"

        return ProbeResult(
            check_type=check_type,
            status=status,
            message=message,
            details=details,
            duration_ms=duration_ms,
        )
    except requests.exceptions.SSLError as e:
        return ProbeResult(
            check_type=check_type,
            status=STATUS_CRITICAL,
            message=f"{label or url}: SSL ошибка — {e}",
            details={"url": url},
            duration_ms=int((time.monotonic() - start) * 1000),
        )
    except requests.exceptions.Timeout:
        return ProbeResult(
            check_type=check_type,
            status=STATUS_CRITICAL,
            message=f"{label or url}: таймаут ({HTTP_TIMEOUT}s)",
            details={"url": url},
            duration_ms=int((time.monotonic() - start) * 1000),
        )
    except Exception as e:
        logger.warning("HTTP probe failed %s: %s", url, e)
        return ProbeResult(
            check_type=check_type,
            status=STATUS_ERROR,
            message=f"{label or url}: {e}",
            details={"url": url},
            duration_ms=int((time.monotonic() - start) * 1000),
        )


def probe_https_reachable(base_url: str) -> ProbeResult:
    result = probe_http_url(base_url, check_type="https_reachable", label="Главная")
    result.check_key = "base"
    return result


def probe_health_url(health_url: str) -> ProbeResult:
    result = probe_http_url(health_url, check_type="health_url", label="Health")
    result.check_key = "health"
    return result
