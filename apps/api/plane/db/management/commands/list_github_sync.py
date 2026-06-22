# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.core.management.base import BaseCommand

from plane.db.models import GitHubRepoSync


class Command(BaseCommand):
    help = "List GitHub repository sync configurations"

    def handle(self, *args, **options):
        syncs = GitHubRepoSync.objects.select_related("workspace", "project", "assignee").order_by("repo_owner", "repo_name")
        if not syncs.exists():
            self.stdout.write("No GitHub sync configs. Use setup_github_sync.")
            return

        for sync in syncs:
            assignee = sync.assignee.email if sync.assignee else "—"
            last = sync.last_imported_sha[:12] + "…" if sync.last_imported_sha else "—"
            status = "ON" if sync.enabled else "OFF"
            self.stdout.write(
                f"[{status}] {sync.full_name} @ {sync.default_branch}\n"
                f"  → {sync.workspace.slug} / {sync.project.name}\n"
                f"  assignee: {assignee} | last_sha: {last} | llm: {sync.use_llm}"
            )
