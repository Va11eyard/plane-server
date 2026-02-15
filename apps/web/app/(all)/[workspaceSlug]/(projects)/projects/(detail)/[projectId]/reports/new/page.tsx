/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState, useCallback } from "react";
import { Link, useNavigate } from "react-router";
import { ChevronLeft } from "lucide-react";
import { Button } from "@plane/propel/button";
import { PageHead } from "@/components/core/page-title";
import { ReportService } from "@/services/report.service";
import type { ICreateReportPayload } from "@/services/report.service";
import type { Route } from "./+types/page";

export default function ProjectNewReportPage({ params }: Route.ComponentProps) {
  const { workspaceSlug, projectId } = params;
  const navigate = useNavigate();
  const [period_from, setPeriodFrom] = useState("");
  const [period_to, setPeriodTo] = useState("");
  const [title, setTitle] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const backUrl = `/${workspaceSlug}/projects/${projectId}/reports`;

  const setPeriod = useCallback((days: number) => {
    const end = new Date();
    const start = new Date();
    start.setDate(start.getDate() - (days - 1));
    setPeriodFrom(start.toISOString().slice(0, 10));
    setPeriodTo(end.toISOString().slice(0, 10));
  }, []);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    
    const reportService = new ReportService();
    const payload: ICreateReportPayload = {
      period_from,
      period_to,
      project_id: projectId,
      title: title || undefined,
    };
    
    void reportService.createReport(workspaceSlug, payload)
      .then((report) => {
        navigate(`/${workspaceSlug}/projects/${projectId}/reports/${report.id}`);
        return report;
      })
      .catch((err: unknown) => {
        setError((err as { error?: string })?.error ?? "Не удалось создать отчёт");
      })
      .finally(() => {
        setLoading(false);
      });
  };

  return (
    <>
      <PageHead title="Новый отчёт" />
      <div className="flex h-full w-full flex-col px-page-x py-page-y">
        <Link
          to={backUrl}
          className="mb-3 inline-flex w-fit items-center gap-1 text-13 text-tertiary hover:text-primary transition-colors"
        >
          <ChevronLeft className="size-3.5" /> Назад к отчётам
        </Link>

        <div className="pb-4">
          <h3 className="text-xl font-semibold text-primary">Новый отчёт по проекту</h3>
          <p className="mt-1 text-13 text-tertiary">
            Выберите период. AI сформирует Agile-отчёт по активности проекта на русском языке.
          </p>
        </div>

        <form
          onSubmit={handleSubmit}
          className="flex max-w-lg flex-col gap-5 rounded-lg border border-subtle bg-layer-2 p-5"
        >
          <div>
            <span className="mb-1.5 block text-13 font-medium text-primary">Период</span>
            <div className="flex gap-2">
              {[
                { label: "День", days: 1 },
                { label: "Неделя", days: 7 },
                { label: "Месяц", days: 30 },
              ].map(({ label, days }) => (
                <button
                  key={days}
                  type="button"
                  onClick={() => setPeriod(days)}
                  className="rounded-md border border-subtle bg-surface-1 px-3 py-1.5 text-13 text-secondary hover:border-strong hover:bg-surface-3 transition-all"
                >
                  {label}
                </button>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label htmlFor="period-from" className="mb-1.5 block text-13 font-medium text-primary">От</label>
              <input
                id="period-from"
                type="date"
                required
                value={period_from}
                onChange={(e) => setPeriodFrom(e.target.value)}
                className="w-full rounded-md border border-subtle bg-surface-1 px-3 py-2 text-13 text-primary focus:border-accent focus:outline-none"
              />
            </div>
            <div>
              <label htmlFor="period-to" className="mb-1.5 block text-13 font-medium text-primary">До</label>
              <input
                id="period-to"
                type="date"
                required
                value={period_to}
                onChange={(e) => setPeriodTo(e.target.value)}
                className="w-full rounded-md border border-subtle bg-surface-1 px-3 py-2 text-13 text-primary focus:border-accent focus:outline-none"
              />
            </div>
          </div>

          <div>
            <label htmlFor="report-title" className="mb-1.5 block text-13 font-medium text-primary">Название (необязательно)</label>
            <input
              id="report-title"
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Например: Спринт 1, Февраль 2025"
              className="w-full rounded-md border border-subtle bg-surface-1 px-3 py-2 text-13 text-primary placeholder:text-placeholder focus:border-accent focus:outline-none"
            />
          </div>

          {error && (
            <div className="rounded-md border border-red-300 bg-red-50 px-3 py-2 text-13 text-red-600 dark:border-red-800 dark:bg-red-950 dark:text-red-400">
              {error}
            </div>
          )}

          <div className="flex items-center gap-3 pt-1">
            <Button
              type="submit"
              variant="secondary"
              size="lg"
              className="rounded-lg px-4"
              loading={loading}
              disabled={loading}
            >
              {loading ? "Генерация..." : "Создать отчёт"}
            </Button>
            <Link to={backUrl}>
              <Button type="button" variant="tertiary" size="lg" className="rounded-lg px-4">
                Отмена
              </Button>
            </Link>
          </div>
        </form>
      </div>
    </>
  );
}
