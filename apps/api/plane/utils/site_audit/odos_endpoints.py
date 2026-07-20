# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Smoke-test HTTP endpoints for ODOS (api.odos.kz, odos.kz, patient, staff)."""

ODOS_HTTP_CHECKS: list[dict] = [
    {
        "type": "http",
        "key": "api_healthz",
        "name": "API /healthz",
        "url": "https://api.odos.kz/healthz",
        "expect_status": 200,
        "expect_json": {"status": "ok"},
    },
    {
        "type": "http",
        "key": "api_readyz",
        "name": "API /readyz",
        "url": "https://api.odos.kz/readyz",
        "expect_status": 200,
        "expect_json": {"ready": True},
    },
    {
        "type": "http",
        "key": "public_health_articles",
        "name": "GET /public/health-articles",
        "url": "https://api.odos.kz/api/v1/public/health-articles?locale=ru",
        "expect_status": 200,
    },
    {
        "type": "http",
        "key": "public_organizations",
        "name": "GET /public/organizations",
        "url": "https://api.odos.kz/api/v1/public/organizations",
        "expect_status": 200,
    },
    {
        "type": "http",
        "key": "auth_me_unauthorized",
        "name": "GET /auth/me (no token)",
        "url": "https://api.odos.kz/api/v1/auth/me",
        "expect_status": 401,
    },
    {
        "type": "http",
        "key": "auth_login_route",
        "name": "POST /auth/login (smoke)",
        "url": "https://api.odos.kz/api/v1/auth/login",
        "method": "POST",
        "json": {},
        "expect_status": [400, 401, 422],
    },
    {
        "type": "http",
        "key": "landing_home",
        "name": "Landing /ru",
        "url": "https://odos.kz/ru",
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
