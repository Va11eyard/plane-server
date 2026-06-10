/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { Link } from "react-router";
import useSWR from "swr";
import { ChevronLeft } from "lucide-react";
import { PageHead } from "@/components/core/page-title";
import { MarkdownRenderer } from "@/components/ui/markdown-to-component";
import { ReportService } from "@/services/report.service";
import type { IActivityReportDetail } from "@/services/report.service";
import type { Route } from "./+types/page";

const reportService = new ReportService();

function ProjectReportDetailPage({ params }: Route.ComponentProps) {
  const { workspaceSlug, projectId, reportId } = params;

  const reportQuery = useSWR<IActivityReportDetail>(
    workspaceSlug && reportId ? `workspace-report-${workspaceSlug}-${reportId}` : null,
    () => reportService.getReport(workspaceSlug, reportId),
    { revalidateOnFocus: false, shouldRetryOnError: false, errorRetryCount: 0 }
  );
  const report = reportQuery.data;
  const isLoading = reportQuery.isLoading;
  const hasError = Boolean(reportQuery.error);

  const backUrl = `/${workspaceSlug}/projects/${projectId}/reports`;

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <PageHead title="Отчёт" />
        <p className="text-13 text-tertiary">Загрузка...</p>
      </div>
    );
  }

  if (hasError || !report) {
    return (
      <div className="flex h-full items-center justify-center px-page-x py-page-y">
        <PageHead title="Отчёт" />
        <div className="max-w-md text-center">
          <h4 className="text-16 font-semibold text-primary">Не удалось загрузить отчёт</h4>
          <p className="mt-2 text-13 text-tertiary">Проверьте, что бэкенд (API) запущен и доступен.</p>
          <Link to={backUrl} className="mt-4 inline-flex items-center gap-1 text-13 text-accent hover:underline">
            <ChevronLeft className="size-3.5" /> Назад к отчётам
          </Link>
        </div>
      </div>
    );
  }

  return (
    <>
      <PageHead title={report.title || "Отчёт"} />
      <div className="flex h-full w-full flex-col px-page-x py-page-y">
        <Link
          to={backUrl}
          className="mb-3 inline-flex w-fit items-center gap-1 text-13 text-tertiary hover:text-primary transition-colors"
        >
          <ChevronLeft className="size-3.5" /> Назад к отчётам
        </Link>

        <div className="flex items-center justify-between pb-4 border-b border-subtle">
          <div>
            <h3 className="text-xl font-semibold text-primary">{report.title || "Без названия"}</h3>
            <div className="mt-1 flex items-center gap-3 text-13 text-tertiary">
              {report.period_from && report.period_to && (
                <span className="rounded-md bg-surface-2 px-2 py-0.5 text-12">
                  {report.period_from} — {report.period_to}
                </span>
              )}
              {report.created_by && <span>Автор: {report.created_by}</span>}
            </div>
          </div>
        </div>

        <div className="mt-4 rounded-lg border border-subtle bg-layer-2 p-5">
          <MarkdownRenderer markdown={report.content} className="text-13 leading-relaxed" />
        </div>
      </div>
    </>
  );
}

export default ProjectReportDetailPage;
