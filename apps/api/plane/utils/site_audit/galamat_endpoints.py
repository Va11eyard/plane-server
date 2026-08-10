# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""Public HTTP smoke tests for Galamat (galamat.pro-ecta.kz, galamat.com)."""

GALAMAT_HTTP_CHECKS: list[dict] = [
    {
        "type": "http",
        "key": "proecta_home",
        "name": "galamat.pro-ecta.kz",
        "url": "https://galamat.pro-ecta.kz/",
        "expect_status": 200,
    },
    {
        "type": "http",
        "key": "com_home",
        "name": "galamat.com",
        "url": "https://galamat.com/",
        "expect_status": 200,
    },
    {
        "type": "http",
        "key": "com_www",
        "name": "www.galamat.com",
        "url": "https://www.galamat.com/",
        "expect_status": [200, 301, 302, 307, 308],
    },
]
