/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { Link } from "react-router";
import useSWR from "swr";
import { ChevronLeft } from "lucide-react";
// components
import { PageHead } from "@/components/core/page-title";
import { ReportService } from "@/services/report.service";
import type { Route } from "./+types/page";

const reportService = new ReportService();

function ReportDetailPage({ params }: Route.ComponentProps) {
  const { workspaceSlug, reportId } = params;

  const {
    data: report,
    isLoading,
    error,
  } = useSWR(
    workspaceSlug && reportId ? `workspace-report-${workspaceSlug}-${reportId}` : null,
    () => reportService.getReport(workspaceSlug, reportId!),
    { revalidateOnFocus: false, shouldRetryOnError: false, errorRetryCount: 0 }
  );

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <PageHead title="Отчёт" />
        <p className="text-13 text-tertiary">Загрузка...</p>
      </div>
    );
  }

  if (error || !report) {
    return (
      <div className="flex h-full items-center justify-center px-5 py-5 md:px-9">
        <PageHead title="Отчёт" />
        <div className="max-w-md text-center">
          <h4 className="text-16 font-semibold text-primary">Не удалось загрузить отчёт</h4>
          <p className="mt-2 text-13 text-tertiary">Проверьте, что бэкенд (API) запущен и доступен.</p>
          <Link
            to={`/${workspaceSlug}/reports`}
            className="mt-4 inline-flex items-center gap-1 text-13 text-accent hover:underline"
          >
            <ChevronLeft className="size-3.5" /> Назад к отчётам
          </Link>
        </div>
      </div>
    );
  }

  return (
    <>
      <PageHead title={report.title || "Отчёт"} />
      <div className="flex h-full w-full flex-col overflow-hidden py-5">
        <div className="flex items-center justify-between gap-2 px-5 md:px-9">
          <Link
            to={`/${workspaceSlug}/reports`}
            className="inline-flex items-center gap-1 text-13 text-tertiary hover:text-primary transition-colors"
          >
            <ChevronLeft className="size-3.5" /> Назад к отчётам
          </Link>
        </div>
        <div className="vertical-scrollbar scrollbar-md flex h-full flex-col overflow-y-auto px-5 md:px-9 pt-4">
          <h3 className="text-16 font-medium text-primary">{report.title || "Без названия"}</h3>
          <div className="mt-1 flex items-center gap-3 text-13 text-tertiary">
            {report.period_from && report.period_to && (
              <span className="rounded bg-surface-2 px-2 py-0.5 text-12">
                {report.period_from} — {report.period_to}
              </span>
            )}
            {report.created_by && <span>Автор: {report.created_by}</span>}
          </div>
          <div className="mt-4 rounded border border-subtle bg-surface-1 p-4">
            <pre className="whitespace-pre-wrap font-sans text-13 leading-relaxed text-primary">{report.content}</pre>
          </div>
        </div>
      </div>
    </>
  );
}

export default ReportDetailPage;
