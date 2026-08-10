# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Public HTTP smoke tests for InLab (inlab.kz)."""

INLAB_BASE = "https://inlab.kz"

INLAB_HTTP_CHECKS: list[dict] = [
    {
        "type": "http",
        "key": "homepage",
        "name": "Homepage",
        "url": f"{INLAB_BASE}/",
        "expect_status": 200,
    },
    {
        "type": "http",
        "key": "api_health",
        "name": "GET /api/health",
        "url": f"{INLAB_BASE}/api/health",
        "expect_status": 200,
        "expect_json": {"ok": True},
    },
]
