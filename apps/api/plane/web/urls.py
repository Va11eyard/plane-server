# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.urls import path, re_path
from plane.web.views import health_check, robots_txt, uploads_proxy

urlpatterns = [
    path("robots.txt", robots_txt),
    re_path(r"^uploads", uploads_proxy),
    path("", health_check),
]
