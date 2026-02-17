# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Django imports
from django.conf import settings
from django.http import HttpRequest

# Third party imports
from rest_framework.request import Request

# Module imports
from plane.utils.ip_address import get_client_ip


def _is_localhost_url(url: str) -> bool:
    """Check if URL points to localhost (redirect would fail for remote users)."""
    if not url:
        return False
    return "localhost" in url.lower() or "127.0.0.1" in url


def _request_origin(request: Request | HttpRequest) -> str:
    """Get scheme + host from request (works behind proxy with X-Forwarded-*)."""
    if getattr(request, "build_absolute_uri", None):
        base = request.build_absolute_uri("/").rstrip("/")
        return base
    scheme = "https" if getattr(request, "is_secure", lambda: False)() else "http"
    host = request.META.get("HTTP_HOST") or request.META.get("SERVER_NAME", "localhost")
    return f"{scheme}://{host}"


def base_host(
    request: Request | HttpRequest,
    is_admin: bool = False,
    is_space: bool = False,
    is_app: bool = False,
) -> str:
    """Utility function to return host / origin from the request"""
    # Calculate the base origin from request
    base_origin = settings.WEB_URL or settings.APP_BASE_URL

    # Admin redirection
    if is_admin:
        admin_base_path = getattr(settings, "ADMIN_BASE_PATH", None)
        if not isinstance(admin_base_path, str):
            admin_base_path = "/god-mode/"
        if not admin_base_path.startswith("/"):
            admin_base_path = "/" + admin_base_path
        if not admin_base_path.endswith("/"):
            admin_base_path += "/"

        admin_url = settings.ADMIN_BASE_URL
        # Avoid redirecting to localhost when user accesses via real host (e.g. 192.168.1.132)
        if admin_url and _is_localhost_url(admin_url):
            return _request_origin(request) + admin_base_path
        if admin_url:
            return admin_url + admin_base_path
        else:
            return (base_origin or _request_origin(request)) + admin_base_path

    # Space redirection
    if is_space:
        space_base_path = getattr(settings, "SPACE_BASE_PATH", None)
        if not isinstance(space_base_path, str):
            space_base_path = "/spaces/"
        if not space_base_path.startswith("/"):
            space_base_path = "/" + space_base_path
        if not space_base_path.endswith("/"):
            space_base_path += "/"

        if settings.SPACE_BASE_URL:
            return settings.SPACE_BASE_URL + space_base_path
        else:
            return base_origin + space_base_path

    # App Redirection
    if is_app:
        if settings.APP_BASE_URL:
            return settings.APP_BASE_URL
        else:
            return base_origin

    return base_origin


def user_ip(request: Request | HttpRequest) -> str:
    return get_client_ip(request=request)
