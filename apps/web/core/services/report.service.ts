/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import axios from "axios";
import type { AxiosInstance } from "axios";

export interface IActivityReportListItem {
  id: string;
  title: string;
  period_from: string | null;
  period_to: string | null;
  created_at: string | null;
  created_by: string | null;
}

export interface IActivityReportDetail extends IActivityReportListItem {
  content: string;
}

export interface ICreateReportPayload {
  period_from: string;
  period_to: string;
  project_id?: string;
  /** Один или несколько проектов; отчёт включит активность по всем выбранным проектам. */
  project_ids?: string[];
  title?: string;
}

/**
 * ReportService — работает через /api/workspaces/<slug>/reports/.
 * Использует собственный axios-инстанс (без 401-redirect перехватчика).
 */
export class ReportService {
  private http: AxiosInstance;

  constructor() {
    this.http = axios.create({
      withCredentials: true,
    });
  }

  async getReports(workspaceSlug: string, projectId?: string): Promise<IActivityReportListItem[]> {
    const config = projectId ? { params: { project_id: projectId } } : {};
    return this.http
      .get(`/api/workspaces/${workspaceSlug}/reports/`, config)
      .then((res) => res.data)
      .catch((err) => {
        throw err?.response?.data ?? { error: err.message ?? "Ошибка сети" };
      });
  }

  async getReport(workspaceSlug: string, id: string): Promise<IActivityReportDetail> {
    return this.http
      .get(`/api/workspaces/${workspaceSlug}/reports/${id}/`)
      .then((res) => res.data)
      .catch((err) => {
        throw err?.response?.data ?? { error: err.message ?? "Ошибка сети" };
      });
  }

  async createReport(workspaceSlug: string, payload: ICreateReportPayload): Promise<IActivityReportDetail> {
    return this.http
      .post(`/api/workspaces/${workspaceSlug}/reports/`, payload)
      .then((res) => res.data)
      .catch((err) => {
        throw err?.response?.data ?? { error: err.message ?? "Ошибка сети" };
      });
  }
}
