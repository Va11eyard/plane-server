# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from plane.db.models import Project, ProjectMember, Workspace, WorkspaceMember
from plane.license.models import InstanceAdmin

from .workspace_project_join import process_workspace_project_invitations


def _add_user_to_default_workspace(user):
    """Add new user to the workspace created by instance admin and all its projects."""
    admin_user_ids = list(InstanceAdmin.objects.values_list("user_id", flat=True))
    default_workspace = (
        Workspace.objects.filter(owner_id__in=admin_user_ids).order_by("created_at").first()
        or Workspace.objects.order_by("created_at").first()
    )
    if not default_workspace:
        return
    if WorkspaceMember.objects.filter(workspace=default_workspace, member=user).exists():
        return
    WorkspaceMember.objects.create(
        workspace=default_workspace,
        member=user,
        role=15,  # Member
    )
    # Add to all projects in the workspace so user can see and work on tasks
    for project in Project.objects.filter(workspace=default_workspace):
        if not ProjectMember.objects.filter(project=project, member=user).exists():
            ProjectMember.objects.create(
                workspace=default_workspace,
                project=project,
                member=user,
                role=15,  # Member
            )


def post_user_auth_workflow(user, is_signup, request):
    process_workspace_project_invitations(user=user)
    if is_signup:
        _add_user_to_default_workspace(user)
