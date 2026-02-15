/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import { useState, useCallback, useMemo } from "react";
import { Link, useNavigate } from "react-router";
import { ChevronLeft } from "lucide-react";
import { Button } from "@plane/propel/button";
import { PageHead } from "@/components/core/page-title";
import { ReportService } from "@/services/report.service";
import type { ICreateReportPayload } from "@/services/report.service";
import { useProject } from "@/hooks/store/use-project";
import type { Route } from "./+types/page";

function NewReportPage({ params }: Route.ComponentProps) {
  const { workspaceSlug } = params;
  const navigate = useNavigate();
  const { workspaceProjectIds, getProjectById } = useProject();
  const [period_from, setPeriodFrom] = useState("");
  const [period_to, setPeriodTo] = useState("");
  const [selectedProjectIds, setSelectedProjectIds] = useState<Set<string>>(new Set());
  const [useWholeWorkspace, setUseWholeWorkspace] = useState(false);
  const [title, setTitle] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const workspaceProjects = useMemo(
    () =>
      (workspaceProjectIds ?? []).map((id) => getProjectById(id)).filter(Boolean) as Array<{
        id: string;
        name: string;
      }>,
    [workspaceProjectIds, getProjectById]
  );

  const setPeriod = useCallback((days: number) => {
    const end = new Date();
    const start = new Date();
    start.setDate(start.getDate() - (days - 1));
    setPeriodFrom(end.toISOString().slice(0, 10));
    setPeriodTo(start.toISOString().slice(0, 10));
  }, []);

  const toggleProject = (projectId: string) => {
    setUseWholeWorkspace(false);
    setSelectedProjectIds((prev) => {
      const next = new Set(prev);
      if (next.has(projectId)) next.delete(projectId);
      else next.add(projectId);
      return next;
    });
  };

  const selectAllProjects = () => {
    setUseWholeWorkspace(false);
    setSelectedProjectIds(new Set(workspaceProjects.map((p) => p.id)));
  };

  const clearProjects = () => {
    setSelectedProjectIds(new Set());
    setUseWholeWorkspace(true);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    
    const reportService = new ReportService();
    const payload: ICreateReportPayload = {
      period_from,
      period_to,
      title: title || undefined,
      project_ids: !useWholeWorkspace && selectedProjectIds.size > 0 
        ? Array.from(selectedProjectIds) 
        : undefined,
    };
    
    void reportService.createReport(workspaceSlug, payload)
      .then((report) => {
        navigate(`/${workspaceSlug}/reports/${report.id}`);
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
      <div className="flex h-full w-full flex-col overflow-hidden py-5">
        <div className="flex items-center justify-between gap-2 px-5 md:px-9">
          <div className="flex items-center gap-2">
            <Link
              to={`/${workspaceSlug}/reports`}
              className="inline-flex items-center gap-1 text-13 text-tertiary hover:text-primary transition-colors"
            >
              <ChevronLeft className="size-3.5" /> Назад к отчётам
            </Link>
          </div>
        </div>
        <div className="vertical-scrollbar scrollbar-md flex h-full flex-col overflow-y-auto px-5 md:px-9 pt-4">
          <h3 className="text-16 font-medium text-primary">Новый отчёт</h3>
          <p className="mt-1 text-13 text-tertiary">
            Выберите проекты и период. AI сформирует отчёт по активности на русском языке.
          </p>
          <form onSubmit={handleSubmit} className="mt-5 flex max-w-lg flex-col gap-5">
            <div>
              <span className="mb-1.5 block text-13 font-medium text-primary">Проекты</span>
              <div className="mb-2 flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={selectAllProjects}
                  className="rounded border border-subtle bg-surface-1 px-2.5 py-1 text-12 text-secondary hover:bg-surface-3 transition-colors"
                >
                  Выбрать все
                </button>
                <button
                  type="button"
                  onClick={clearProjects}
                  className="rounded border border-subtle bg-surface-1 px-2.5 py-1 text-12 text-secondary hover:bg-surface-3 transition-colors"
                >
                  Весь воркспейс
                </button>
              </div>
              <div className="max-h-40 overflow-y-auto rounded border border-subtle bg-surface-1 p-2">
                {workspaceProjects.length === 0 ? (
                  <p className="text-13 text-placeholder">Нет проектов в воркспейсе</p>
                ) : (
                  <ul className="flex flex-col gap-1">
                    {workspaceProjects.map((p) => (
                      <li key={p.id}>
                        <label className="flex cursor-pointer items-center gap-2 rounded-md px-2 py-1 text-13 text-primary hover:bg-surface-2 transition-colors">
                          <input
                            type="checkbox"
                            checked={useWholeWorkspace ? false : selectedProjectIds.has(p.id)}
                            onChange={() => toggleProject(p.id)}
                            className="rounded border-subtle"
                          />
                          <span>{p.name}</span>
                        </label>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
              <p className="mt-1.5 text-12 text-placeholder">
                {useWholeWorkspace || selectedProjectIds.size === 0
                  ? "Будет использован весь воркспейс"
                  : `Выбрано проектов: ${selectedProjectIds.size}`}
              </p>
            </div>

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
                    className="rounded border border-subtle bg-surface-1 px-3 py-1.5 text-13 text-secondary hover:bg-surface-3 transition-colors"
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
                  className="w-full rounded border border-subtle bg-surface-1 px-3 py-2 text-13 text-primary focus:outline-none focus:ring-1 focus:ring-accent"
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
                  className="w-full rounded border border-subtle bg-surface-1 px-3 py-2 text-13 text-primary focus:outline-none focus:ring-1 focus:ring-accent"
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
                className="w-full rounded border border-subtle bg-surface-1 px-3 py-2 text-13 text-primary placeholder:text-placeholder focus:outline-none focus:ring-1 focus:ring-accent"
              />
            </div>

            {error && (
              <div className="rounded border border-red-300 bg-red-50 px-3 py-2 text-13 text-red-600 dark:border-red-800 dark:bg-red-950 dark:text-red-400">
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
                {loading ? "Генерация..." : "Сгенерировать отчёт"}
              </Button>
              <Link to={`/${workspaceSlug}/reports`}>
                <Button type="button" variant="tertiary" size="lg" className="rounded-lg px-4">
                  Отмена
                </Button>
              </Link>
            </div>
          </form>
        </div>
      </div>
    </>
  );
}

export default observer(NewReportPage);
