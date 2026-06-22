# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import logging
import os
from typing import Any

import requests
from django.conf import settings

logger = logging.getLogger("plane.github")


class GitHubAPIError(Exception):
    pass


def get_github_token() -> str | None:
    token = os.environ.get("GITHUB_ACCESS_TOKEN") or getattr(settings, "GITHUB_ACCESS_TOKEN", None)
    if token and token not in (False, "False", ""):
        return str(token)
    return None


def build_commit_url(owner: str, repo: str, sha: str) -> str:
    return f"https://github.com/{owner}/{repo}/commit/{sha}"


def _headers() -> dict[str, str]:
    token = get_github_token()
    if not token:
        raise GitHubAPIError("GITHUB_ACCESS_TOKEN не настроен")
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _get(url: str, params: dict | None = None) -> Any:
    resp = requests.get(url, headers=_headers(), params=params or {}, timeout=60)
    if resp.status_code == 404:
        raise GitHubAPIError(f"GitHub 404: {url}")
    if resp.status_code != 200:
        raise GitHubAPIError(f"GitHub API {resp.status_code}: {resp.text[:300]}")
    return resp.json()


def fetch_compare_commits(owner: str, repo: str, base_sha: str, head_branch: str) -> list[dict[str, Any]]:
    """Commits reachable from head but not base (oldest first in API, we return newest first)."""
    if not base_sha:
        url = f"https://api.github.com/repos/{owner}/{repo}/commits"
        data = _get(url, {"sha": head_branch, "per_page": 100})
        if isinstance(data, list):
            return list(reversed(data))
        return []

    url = f"https://api.github.com/repos/{owner}/{repo}/compare/{base_sha}...{head_branch}"
    data = _get(url)
    commits = data.get("commits") or []
    return list(reversed(commits))


def fetch_commit_detail(owner: str, repo: str, sha: str) -> dict[str, Any]:
    url = f"https://api.github.com/repos/{owner}/{repo}/commits/{sha}"
    return _get(url)


def commit_summary(commit: dict[str, Any], owner: str = "", repo: str = "") -> dict[str, str]:
    sha = commit.get("sha") or ""
    commit_data = commit.get("commit") or {}
    message = (commit_data.get("message") or "").strip()
    first_line = message.split("\n", 1)[0]
    url = commit.get("html_url") or (build_commit_url(owner, repo, sha) if owner and repo else "")
    return {
        "sha": sha,
        "short_sha": sha[:8] if sha else "",
        "message": first_line,
        "full_message": message,
        "url": url,
    }


def extract_commit_files(detail: dict[str, Any], max_files: int = 80) -> list[dict[str, str]]:
    files: list[dict[str, str]] = []
    for item in (detail.get("files") or [])[:max_files]:
        files.append(
            {
                "filename": item.get("filename") or "",
                "status": item.get("status") or "",
                "changes": str(item.get("changes") or 0),
            }
        )
    return files


def is_merge_commit(commit: dict[str, Any]) -> bool:
    parents = commit.get("parents") or []
    message = ((commit.get("commit") or {}).get("message") or "").lower()
    return len(parents) > 1 or message.startswith("merge ")
