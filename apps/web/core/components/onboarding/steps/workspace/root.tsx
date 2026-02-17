/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useEffect, useState } from "react";
import { observer } from "mobx-react";
import { OctagonAlert } from "lucide-react";
// plane imports
import type { IWorkspaceMemberInvitation } from "@plane/types";
import { ECreateOrJoinWorkspaceViews, EOnboardingSteps } from "@plane/types";
// local components
import { WorkspaceJoinInvitesStep } from "./";

type Props = {
  invitations: IWorkspaceMemberInvitation[];
  handleStepChange: (step: EOnboardingSteps, skipInvites?: boolean) => void;
};

export const WorkspaceSetupStep = observer(function WorkspaceSetupStep({ invitations, handleStepChange }: Props) {
  // states
  const [currentView, setCurrentView] = useState<ECreateOrJoinWorkspaceViews | null>(null);

  useEffect(() => {
    if (invitations.length > 0) {
      setCurrentView(ECreateOrJoinWorkspaceViews.WORKSPACE_JOIN);
    } else {
      setCurrentView(ECreateOrJoinWorkspaceViews.WORKSPACE_CREATE);
    }
  }, [invitations]);

  return (
    <>
      {currentView === ECreateOrJoinWorkspaceViews.WORKSPACE_JOIN ? (
        <WorkspaceJoinInvitesStep
          invitations={invitations}
          handleNextStep={() => {
            handleStepChange(EOnboardingSteps.WORKSPACE_CREATE_OR_JOIN, true);
            return Promise.resolve();
          }}
          handleCurrentViewChange={() => setCurrentView(ECreateOrJoinWorkspaceViews.WORKSPACE_CREATE)}
        />
      ) : (
        <div className="flex flex-col gap-10">
          <div className="flex gap-2.5 w-full items-start justify-center text-13 leading-5 mt-4 px-6 py-4 rounded-sm border border-accent-strong/20 bg-accent-primary/10 text-accent-secondary">
            <OctagonAlert className="flex-shrink-0 size-5 mt-1" />
            <span>
              You don&apos;t seem to have any invites to a workspace and your instance admin has restricted creation of
              new workspaces. Please ask a workspace owner or admin to invite you to a workspace first and come back to
              this screen to join.
            </span>
          </div>
        </div>
      )}
    </>
  );
});
