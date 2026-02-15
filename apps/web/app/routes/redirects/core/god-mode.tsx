/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 *
 * Redirect /god-mode to home so users stay on the same port (3000) when
 * admin app is not running. For instance setup, run: pnpm --filter=admin dev
 */

import { redirect } from "react-router";

export const clientLoader = () => {
  throw redirect("/");
};

export default function GodModeRedirect() {
  return null;
}
