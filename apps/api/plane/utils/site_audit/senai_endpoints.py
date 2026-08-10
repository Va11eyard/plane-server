# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Public HTTP smoke tests for SenAI (sen-ai.kz)."""

SENAI_BASE = "https://sen-ai.kz"

SENAI_HTTP_CHECKS: list[dict] = [
    {
        "type": "http",
        "key": "homepage",
        "name": "Homepage",
        "url": f"{SENAI_BASE}/",
        "expect_status": 200,
    },
]
