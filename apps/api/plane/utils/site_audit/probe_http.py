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

DEFAULT_HEADERS = {"User-Agent": "PlaneSiteAudit/1.0"}


def _status_matches(code: int, expected) -> bool:
    if isinstance(expected, (list, tuple, set)):
        return code in expected
    return code == expected


def _json_contains(actual: dict, expected: dict) -> bool:
    for key, value in expected.items():
        if actual.get(key) != value:
            return False
    return True


def probe_configured_http(check: dict) -> ProbeResult:
    """Run a configurable HTTP smoke test from checks_json (type: http)."""
    name = str(check.get("name") or check.get("url") or "HTTP")
    url = str(check.get("url") or "").strip()
    method = str(check.get("method") or "GET").upper()
    expect_status = check.get("expect_status", 200)
    expect_json = check.get("expect_json")
    check_key = str(check.get("key") or name)

    start = time.monotonic()
    if not url:
        return ProbeResult(
            check_type="http_endpoint",
            check_key=check_key,
            status=STATUS_SKIPPED,
            message=f"{name}: URL не задан",
        )

    try:
        kwargs: dict = {
            "timeout": HTTP_TIMEOUT,
            "allow_redirects": bool(check.get("allow_redirects", True)),
            "headers": {**DEFAULT_HEADERS, **(check.get("headers") or {})},
        }
        if method == "GET":
            resp = requests.get(url, **kwargs)
        elif method == "POST":
            resp = requests.post(url, json=check.get("json"), **kwargs)
        elif method == "HEAD":
            resp = requests.head(url, **kwargs)
        else:
            resp = requests.request(method, url, json=check.get("json"), **kwargs)

        duration_ms = int((time.monotonic() - start) * 1000)
        status_code = resp.status_code
        details: dict = {"url": url, "method": method, "status_code": status_code, "latency_ms": duration_ms}

        if not _status_matches(status_code, expect_status):
            return ProbeResult(
                check_type="http_endpoint",
                check_key=check_key,
                status=STATUS_CRITICAL,
                message=f"{name}: HTTP {status_code} (ожидался {expect_status})",
                details=details,
                duration_ms=duration_ms,
            )

        if expect_json and isinstance(expect_json, dict):
            try:
                data = resp.json()
                details["body"] = data
                if not isinstance(data, dict) or not _json_contains(data, expect_json):
                    return ProbeResult(
                        check_type="http_endpoint",
                        check_key=check_key,
                        status=STATUS_WARN,
                        message=f"{name}: JSON не совпал с ожиданием",
                        details=details,
                        duration_ms=duration_ms,
                    )
            except Exception:
                return ProbeResult(
                    check_type="http_endpoint",
                    check_key=check_key,
                    status=STATUS_WARN,
                    message=f"{name}: ответ не JSON",
                    details=details,
                    duration_ms=duration_ms,
                )

        return ProbeResult(
            check_type="http_endpoint",
            check_key=check_key,
            status=STATUS_OK,
            message=f"{name}: HTTP {status_code}, {duration_ms} ms",
            details=details,
            duration_ms=duration_ms,
        )
    except requests.exceptions.SSLError as e:
        return ProbeResult(
            check_type="http_endpoint",
            check_key=check_key,
            status=STATUS_CRITICAL,
            message=f"{name}: SSL ошибка — {e}",
            details={"url": url},
            duration_ms=int((time.monotonic() - start) * 1000),
        )
    except requests.exceptions.Timeout:
        return ProbeResult(
            check_type="http_endpoint",
            check_key=check_key,
            status=STATUS_CRITICAL,
            message=f"{name}: таймаут ({HTTP_TIMEOUT}s)",
            details={"url": url},
            duration_ms=int((time.monotonic() - start) * 1000),
        )
    except Exception as e:
        logger.warning("HTTP endpoint probe failed %s: %s", url, e)
        return ProbeResult(
            check_type="http_endpoint",
            check_key=check_key,
            status=STATUS_ERROR,
            message=f"{name}: {e}",
            details={"url": url},
            duration_ms=int((time.monotonic() - start) * 1000),
        )


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
            headers=DEFAULT_HEADERS,
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
