/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { Link, useNavigate } from "react-router";
import useSWR from "swr";
import { Plus } from "lucide-react";
import { Button } from "@plane/propel/button";
// components
import { PageHead } from "@/components/core/page-title";
import { ReportService } from "@/services/report.service";
import type { IActivityReportListItem } from "@/services/report.service";
import type { Route } from "./+types/page";

const reportService = new ReportService();

function ReportsListPage({ params }: Route.ComponentProps) {
  const { workspaceSlug } = params;
  const navigate = useNavigate();

  const {
    data: reports,
    isLoading,
    error,
  } = useSWR(
    workspaceSlug ? `workspace-reports-${workspaceSlug}` : null,
    () => reportService.getReports(workspaceSlug),
    { revalidateOnFocus: false, shouldRetryOnError: false, errorRetryCount: 0 }
  );

  return (
    <>
      <PageHead title="Отчёты" />
      <div className="flex h-full w-full flex-col overflow-hidden py-5">
        <div className="flex items-center justify-between gap-2 px-5 md:px-9">
          <h3 className="text-16 font-medium text-primary">Отчёты</h3>
          <Link to={`/${workspaceSlug}/reports/new`}>
            <Button variant="primary" size="sm" prependIcon={<Plus className="size-4" />}>
              Сгенерировать
            </Button>
          </Link>
        </div>
        <div className="vertical-scrollbar scrollbar-md flex h-full flex-col overflow-y-auto px-5 md:px-9 pt-4">
          {isLoading ? (
            <p className="text-13 text-tertiary">Загрузка...</p>
          ) : error ? (
            <div className="max-w-md">
              <h4 className="text-16 font-semibold text-primary">Не удалось загрузить отчёты</h4>
              <p className="mt-2 text-13 text-tertiary">Проверьте, что бэкенд (API) запущен и доступен.</p>
            </div>
          ) : !reports?.length ? (
            <div className="max-w-md">
              <h4 className="text-16 font-semibold text-primary">Нет отчётов</h4>
              <p className="mt-2 text-13 text-tertiary">
                Нажмите «Сгенерировать», выберите проекты и период — будет создан отчёт по активности.
              </p>
              <div className="mt-6">
                <Link to={`/${workspaceSlug}/reports/new`}>
                  <Button variant="primary" size="base" prependIcon={<Plus className="size-4" />}>
                    Сгенерировать отчёт
                  </Button>
                </Link>
              </div>
            </div>
          ) : (
            <div className="flex flex-col gap-2">
              {(reports as IActivityReportListItem[]).map((r) => (
                <button
                  key={r.id}
                  type="button"
                  onClick={() => navigate(`/${workspaceSlug}/reports/${r.id}`)}
                  className="group flex w-full items-center justify-between rounded-lg border border-subtle bg-layer-2 px-4 py-3 text-left transition-all duration-200 hover:border-strong hover:shadow-raised-200"
                >
                  <div className="flex flex-col gap-0.5">
                    <span className="text-13 font-medium text-primary">{r.title || "Без названия"}</span>
                    {r.created_by && <span className="text-12 text-tertiary">Автор: {r.created_by}</span>}
                  </div>
                  <div className="flex items-center gap-3">
                    {r.period_from && r.period_to && (
                      <span className="rounded-md bg-surface-2 px-2 py-0.5 text-12 text-secondary">
                        {r.period_from} — {r.period_to}
                      </span>
                    )}
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </>
  );
}

export default ReportsListPage;
