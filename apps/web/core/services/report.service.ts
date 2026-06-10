/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import axios, { isAxiosError } from "axios";
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

export interface ITelegramLinkStatus {
  linked: boolean;
  telegram_username?: string;
  linked_at?: string;
}

export interface ITelegramLinkToken {
  token: string;
  expires_at: string;
  bot_username?: string;
  instruction: string;
}

function throwServiceError(err: unknown): never {
  if (isAxiosError<{ error?: string }>(err)) {
    throw new Error(err.response?.data?.error ?? err.message ?? "Ошибка сети");
  }
  if (err instanceof Error) {
    throw err;
  }
  throw new Error("Ошибка сети");
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
    try {
      const res = await this.http.get<IActivityReportListItem[]>(`/api/workspaces/${workspaceSlug}/reports/`, config);
      return res.data;
    } catch (err) {
      throwServiceError(err);
    }
  }

  async getReport(workspaceSlug: string, id: string): Promise<IActivityReportDetail> {
    try {
      const res = await this.http.get<IActivityReportDetail>(`/api/workspaces/${workspaceSlug}/reports/${id}/`);
      return res.data;
    } catch (err) {
      throwServiceError(err);
    }
  }

  async createReport(workspaceSlug: string, payload: ICreateReportPayload): Promise<IActivityReportDetail> {
    try {
      const res = await this.http.post<IActivityReportDetail>(`/api/workspaces/${workspaceSlug}/reports/`, payload);
      return res.data;
    } catch (err) {
      throwServiceError(err);
    }
  }

  async createWeeklyReport(workspaceSlug: string): Promise<IActivityReportDetail> {
    try {
      const res = await this.http.post<IActivityReportDetail>(`/api/workspaces/${workspaceSlug}/reports/weekly/`);
      return res.data;
    } catch (err) {
      throwServiceError(err);
    }
  }

  getReportPdfUrl(workspaceSlug: string, id: string): string {
    return `/api/workspaces/${workspaceSlug}/reports/${id}/pdf/`;
  }

  async sendReportToTelegram(workspaceSlug: string, id: string): Promise<{ success: boolean; message: string }> {
    try {
      const res = await this.http.post<{ success: boolean; message: string }>(
        `/api/workspaces/${workspaceSlug}/reports/${id}/send-telegram/`
      );
      return res.data;
    } catch (err) {
      throwServiceError(err);
    }
  }

  async getTelegramStatus(): Promise<ITelegramLinkStatus> {
    try {
      const res = await this.http.get<ITelegramLinkStatus>("/api/users/me/telegram/");
      return res.data;
    } catch (err) {
      throwServiceError(err);
    }
  }

  async createTelegramLinkToken(): Promise<ITelegramLinkToken> {
    try {
      const res = await this.http.post<ITelegramLinkToken>("/api/users/me/telegram/link-token/");
      return res.data;
    } catch (err) {
      throwServiceError(err);
    }
  }
}
