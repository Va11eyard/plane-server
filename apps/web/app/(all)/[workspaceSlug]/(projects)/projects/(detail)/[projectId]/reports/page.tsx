/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { Link, useNavigate } from "react-router";
import useSWR from "swr";
import { Plus } from "lucide-react";
import { Button } from "@plane/propel/button";
import { PageHead } from "@/components/core/page-title";
import { ReportService } from "@/services/report.service";
import type { IActivityReportListItem } from "@/services/report.service";
import type { Route } from "./+types/page";

const reportService = new ReportService();

function ProjectReportsPage({ params }: Route.ComponentProps) {
  const { workspaceSlug, projectId } = params;
  const navigate = useNavigate();

  const {
    data: reports,
    isLoading,
    error,
  } = useSWR(
    workspaceSlug && projectId ? `workspace-reports-${workspaceSlug}-${projectId}` : null,
    () => reportService.getReports(workspaceSlug, projectId),
    { revalidateOnFocus: false, shouldRetryOnError: false, errorRetryCount: 0 }
  );

  return (
    <>
      <PageHead title="Отчёты по проекту" />
      <div className="flex h-full w-full flex-col px-page-x py-page-y">
        <div className="flex items-center justify-between pb-3.5">
          <div>
            <h3 className="text-xl font-semibold text-primary">Отчёты по проекту</h3>
            <p className="mt-1 text-13 text-tertiary">
              Agile-отчёты по активности в этом проекте. Генерируются AI на основе обновлений задач.
            </p>
          </div>
          <Link to={`/${workspaceSlug}/projects/${projectId}/reports/new`}>
            <Button variant="primary" size="sm" prependIcon={<Plus className="size-4" />}>
              Создать отчёт
            </Button>
          </Link>
        </div>

        {isLoading ? (
          <div className="flex h-full items-center justify-center">
            <p className="text-13 text-tertiary">Загрузка...</p>
          </div>
        ) : error ? (
          <div className="flex h-full items-center justify-center">
            <div className="max-w-md text-center">
              <h4 className="text-16 font-semibold text-primary">Не удалось загрузить отчёты</h4>
              <p className="mt-2 text-13 text-tertiary">Проверьте, что бэкенд (API) запущен и доступен.</p>
            </div>
          </div>
        ) : !reports?.length ? (
          <div className="flex h-full items-center justify-center">
            <div className="max-w-md text-center">
              <h4 className="text-16 font-semibold text-primary">Нет отчётов</h4>
              <p className="mt-2 text-13 text-tertiary">
                Создайте первый отчёт, выбрав период (день / неделя / месяц).
              </p>
              <div className="mt-6">
                <Link to={`/${workspaceSlug}/projects/${projectId}/reports/new`}>
                  <Button variant="primary" size="base" prependIcon={<Plus className="size-4" />}>
                    Создать отчёт
                  </Button>
                </Link>
              </div>
            </div>
          </div>
        ) : (
          <div className="flex flex-col gap-2">
            {(reports as IActivityReportListItem[]).map((r) => (
              <button
                key={r.id}
                type="button"
                onClick={() => navigate(`/${workspaceSlug}/projects/${projectId}/reports/${r.id}`)}
                className="group flex w-full items-center justify-between rounded-lg border border-subtle bg-layer-2 px-4 py-3 text-left transition-all duration-200 hover:border-strong hover:shadow-raised-200"
              >
                <div className="flex flex-col gap-0.5">
                  <span className="text-13 font-medium text-primary">{r.title || "Без названия"}</span>
                  {r.created_by && <span className="text-12 text-tertiary">Автор: {r.created_by}</span>}
                </div>
                {r.period_from && r.period_to && (
                  <span className="rounded-md bg-surface-2 px-2 py-0.5 text-12 text-secondary">
                    {r.period_from} — {r.period_to}
                  </span>
                )}
              </button>
            ))}
          </div>
        )}
      </div>
    </>
  );
}

export default ProjectReportsPage;
