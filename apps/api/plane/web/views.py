# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import os

import requests
from django.conf import settings
from django.http import HttpResponse, JsonResponse, StreamingHttpResponse


def health_check(request):
    return JsonResponse({"status": "OK"})


def robots_txt(request):
    return HttpResponse("User-agent: *\nDisallow: /", content_type="text/plain")


def uploads_proxy(request):
    """Proxy /uploads to S3/MinIO so presigned POST URLs work when API and storage share the same host."""
    endpoint = os.environ.get("AWS_S3_ENDPOINT_URL") or getattr(settings, "AWS_S3_ENDPOINT_URL", None)
    if not endpoint:
        return HttpResponse("Uploads proxy not configured (AWS_S3_ENDPOINT_URL)", status=502)
    endpoint = endpoint.rstrip("/")
    path = request.get_full_path()  # /uploads/... or /uploads?...
    if not path.startswith("/uploads"):
        return HttpResponse("Invalid path", status=400)
    url = f"{endpoint}{path}"
    headers = {
        k: v
        for k, v in request.headers.items()
        if k.lower() not in ("host", "connection", "content-length")
    }
    try:
        if request.method == "GET":
            resp = requests.get(url, headers=headers, timeout=30, stream=True)
        elif request.method == "POST":
            resp = requests.post(
                url,
                data=request.body,
                headers=headers,
                timeout=60,
                stream=True,
            )
        elif request.method == "PUT":
            resp = requests.put(
                url,
                data=request.body,
                headers=headers,
                timeout=60,
                stream=True,
            )
        elif request.method == "HEAD":
            resp = requests.head(url, headers=headers, timeout=10)
        else:
            return HttpResponse("Method not allowed", status=405)
    except requests.RequestException as e:
        return HttpResponse(f"Proxy error: {e}", status=502)
    response_headers = {
        k: v
        for k, v in resp.headers.items()
        if k.lower() not in ("transfer-encoding", "connection")
    }
    if resp.headers.get("content-length"):
        return HttpResponse(resp.content, status=resp.status_code, headers=response_headers)
    return StreamingHttpResponse(
        resp.iter_content(chunk_size=8192),
        status=resp.status_code,
        content_type=resp.headers.get("content-type", "application/octet-stream"),
        headers=response_headers,
    )
