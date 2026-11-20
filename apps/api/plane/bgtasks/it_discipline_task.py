# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import logging
import os

from celery import shared_task

from plane.utils.it_discipline import run_reminders

logger = logging.getLogger("plane.it_discipline")

DEFAULT_WORKSPACE_SLUG = "ihealth"


def _run(kind: str) -> None:
    slug = os.environ.get("IT_WORKSPACE_SLUG", DEFAULT_WORKSPACE_SLUG)
    try:
        run_reminders(kind, slug)
    except Exception:
        logger.exception("IT %s reminders failed for workspace %s", kind, slug)


def refresh_overdue_for_slug(slug: str) -> None:
    from plane.db.management.commands.setup_it_department import refresh_overdue_view
    from plane.db.models import Workspace

    workspace = Workspace.objects.filter(slug=slug).first()
    if workspace:
        refresh_overdue_view(workspace)


@shared_task
def refresh_overdue_view_task() -> None:
    slug = os.environ.get("IT_WORKSPACE_SLUG", DEFAULT_WORKSPACE_SLUG)
    try:
        refresh_overdue_for_slug(slug)
    except Exception:
        logger.exception("Refreshing the overdue view failed for workspace %s", slug)


@shared_task
def send_morning_reminders() -> None:
    _run("morning")


@shared_task
def send_evening_reminders() -> None:
    _run("evening")


@shared_task
def send_manager_digest() -> None:
    _run("digest")
