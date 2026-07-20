# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""HTTP endpoint smoke tests for ODOS — static routes + dynamic follow-up probes."""

import logging
import time
from typing import Any

import requests

from plane.utils.site_audit.probe_http import DEFAULT_HEADERS
from plane.utils.site_audit.types import HTTP_TIMEOUT, STATUS_CRITICAL, STATUS_ERROR, STATUS_OK, STATUS_SKIPPED, STATUS_WARN, ProbeResult

logger = logging.getLogger("plane.site_audit")

API_BASE = "https://api.odos.kz"

ODOS_HTTP_CHECKS: list[dict] = [
    {
        "type": "http",
        "key": "api_healthz",
        "name": "API /healthz",
        "url": f"{API_BASE}/healthz",
        "expect_status": 200,
        "expect_json": {"status": "ok"},
    },
    {
        "type": "http",
        "key": "api_readyz",
        "name": "API /readyz",
        "url": f"{API_BASE}/readyz",
        "expect_status": 200,
        "expect_json": {"ready": True},
    },
    {
        "type": "http",
        "key": "public_health_articles",
        "name": "GET /public/health-articles",
        "url": f"{API_BASE}/api/v1/public/health-articles?locale=ru",
        "expect_status": 200,
    },
    {
        "type": "http",
        "key": "public_organizations",
        "name": "GET /public/organizations",
        "url": f"{API_BASE}/api/v1/public/organizations",
        "expect_status": 200,
    },
    {
        "type": "http",
        "key": "auth_me_unauthorized",
        "name": "GET /auth/me (no token)",
        "url": f"{API_BASE}/api/v1/auth/me",
        "expect_status": 401,
    },
    {
        "type": "http",
        "key": "auth_login_route",
        "name": "POST /auth/login (smoke)",
        "url": f"{API_BASE}/api/v1/auth/login",
        "method": "POST",
        "json": {},
        "expect_status": [400, 401, 422],
    },
    {
        "type": "http",
        "key": "auth_patient_login",
        "name": "POST /auth/patient/login (smoke)",
        "url": f"{API_BASE}/api/v1/auth/patient/login",
        "method": "POST",
        "json": {},
        "expect_status": [400, 401, 422],
    },
    {
        "type": "http",
        "key": "auth_forgot_password",
        "name": "POST /auth/forgot-password (smoke)",
        "url": f"{API_BASE}/api/v1/auth/forgot-password",
        "method": "POST",
        "json": {"email": "audit-smoke@example.com"},
        "expect_status": [200, 202, 400, 404, 422],
    },
    {
        "type": "http",
        "key": "public_ai_chat_smoke",
        "name": "POST /public/ai-assistant/chat (smoke)",
        "url": f"{API_BASE}/api/v1/public/ai-assistant/chat",
        "method": "POST",
        "json": {},
        "expect_status": [400, 422],
    },
    {
        "type": "http",
        "key": "public_referral_screening",
        "name": "POST /public/referral-screening (smoke)",
        "url": f"{API_BASE}/api/v1/public/referral-screening",
        "method": "POST",
        "json": {},
        "expect_status": [400, 401, 422],
    },
    {
        "type": "http",
        "key": "landing_home_ru",
        "name": "Landing /ru",
        "url": "https://odos.kz/ru",
        "expect_status": [200, 301, 302, 307, 308],
    },
    {
        "type": "http",
        "key": "landing_home_en",
        "name": "Landing /en",
        "url": "https://odos.kz/en",
        "expect_status": [200, 301, 302, 307, 308],
    },
    {
        "type": "http",
        "key": "landing_articles",
        "name": "Landing /ru/articles",
        "url": "https://odos.kz/ru/articles",
        "expect_status": [200, 301, 302, 307, 308],
    },
    {
        "type": "http",
        "key": "landing_sitemap",
        "name": "Landing sitemap",
        "url": "https://odos.kz/sitemap.xml",
        "expect_status": 200,
    },
    {
        "type": "http",
        "key": "patient_app",
        "name": "Patient app",
        "url": "https://patient.odos.kz/",
        "expect_status": [200, 301, 302, 307, 308],
    },
    {
        "type": "http",
        "key": "staff_app",
        "name": "Staff app",
        "url": "https://staff.odos.kz/",
        "expect_status": [200, 301, 302, 307, 308],
    },
]


def _extract_article_slug(payload: Any) -> str | None:
    if isinstance(payload, list) and payload:
        first = payload[0]
        if isinstance(first, dict):
            return first.get("slug") or first.get("id")
    if isinstance(payload, dict):
        items = payload.get("items") or payload.get("articles") or payload.get("data")
        if isinstance(items, list) and items:
            first = items[0]
            if isinstance(first, dict):
                return first.get("slug") or first.get("id")
    return None


def _http_get_probe(*, name: str, url: str, check_key: str, expect_status: int | list = 200) -> ProbeResult:
    start = time.monotonic()
    try:
        resp = requests.get(url, timeout=HTTP_TIMEOUT, headers=DEFAULT_HEADERS, allow_redirects=True)
        duration_ms = int((time.monotonic() - start) * 1000)
        expected = expect_status if isinstance(expect_status, list) else [expect_status]
        if resp.status_code not in expected:
            return ProbeResult(
                check_type="http_endpoint",
                check_key=check_key,
                status=STATUS_CRITICAL,
                message=f"{name}: HTTP {resp.status_code}",
                details={"url": url, "status_code": resp.status_code},
                duration_ms=duration_ms,
            )
        return ProbeResult(
            check_type="http_endpoint",
            check_key=check_key,
            status=STATUS_OK,
            message=f"{name}: HTTP {resp.status_code}, {duration_ms} ms",
            details={"url": url, "status_code": resp.status_code},
            duration_ms=duration_ms,
        )
    except Exception as e:
        logger.warning("ODOS deep probe failed %s: %s", url, e)
        return ProbeResult(
            check_type="http_endpoint",
            check_key=check_key,
            status=STATUS_ERROR,
            message=f"{name}: {e}",
            details={"url": url},
            duration_ms=int((time.monotonic() - start) * 1000),
        )


def probe_odos_deep_endpoints() -> list[ProbeResult]:
    """Follow-up probes that depend on live API responses (article detail, etc.)."""
    results: list[ProbeResult] = []
    list_url = f"{API_BASE}/api/v1/public/health-articles?locale=ru"

    try:
        resp = requests.get(list_url, timeout=HTTP_TIMEOUT, headers=DEFAULT_HEADERS)
        if resp.status_code != 200:
            results.append(
                ProbeResult(
                    check_type="http_endpoint",
                    check_key="health_article_chain",
                    status=STATUS_CRITICAL,
                    message=f"Health articles list: HTTP {resp.status_code}",
                    details={"url": list_url},
                )
            )
            return results

        try:
            payload = resp.json()
        except Exception:
            results.append(
                ProbeResult(
                    check_type="http_endpoint",
                    check_key="health_article_chain",
                    status=STATUS_WARN,
                    message="Health articles list: ответ не JSON",
                    details={"url": list_url},
                )
            )
            return results

        slug = _extract_article_slug(payload)
        if not slug:
            results.append(
                ProbeResult(
                    check_type="http_endpoint",
                    check_key="health_article_detail",
                    status=STATUS_SKIPPED,
                    message="Health article detail: нет опубликованных статей для проверки",
                )
            )
        else:
            detail_url = f"{API_BASE}/api/v1/public/health-articles/{slug}?locale=ru"
            results.append(
                _http_get_probe(
                    name=f"GET /public/health-articles/{slug}",
                    url=detail_url,
                    check_key="health_article_detail",
                )
            )
    except Exception as e:
        logger.warning("ODOS health article chain failed: %s", e)
        results.append(
            ProbeResult(
                check_type="http_endpoint",
                check_key="health_article_chain",
                status=STATUS_ERROR,
                message=f"Health articles chain: {e}",
                details={"url": list_url},
            )
        )

    return results
