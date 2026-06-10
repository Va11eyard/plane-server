/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { Link } from "react-router";
import useSWR from "swr";
import { useState } from "react";
import { ChevronLeft, Download, Send } from "lucide-react";
import { Button } from "@plane/propel/button";
// components
import { PageHead } from "@/components/core/page-title";
import { ReportService } from "@/services/report.service";
import type { IActivityReportDetail } from "@/services/report.service";
import type { Route } from "./+types/page";

const reportService = new ReportService();

function ReportDetailPage({ params }: Route.ComponentProps) {
  const { workspaceSlug, reportId } = params;
  const [telegramLoading, setTelegramLoading] = useState(false);
  const [telegramMessage, setTelegramMessage] = useState<string | null>(null);
  const [telegramError, setTelegramError] = useState<string | null>(null);
  const [linkToken, setLinkToken] = useState<string | null>(null);

  const reportQuery = useSWR<IActivityReportDetail>(
    workspaceSlug && reportId ? `workspace-report-${workspaceSlug}-${reportId}` : null,
    () => reportService.getReport(workspaceSlug, reportId),
    { revalidateOnFocus: false, shouldRetryOnError: false, errorRetryCount: 0 }
  );
  const report = reportQuery.data;
  const isLoading = reportQuery.isLoading;
  const hasLoadError = Boolean(reportQuery.error);

  const { data: telegramStatus } = useSWR("telegram-link-status", () => reportService.getTelegramStatus(), {
    revalidateOnFocus: false,
    shouldRetryOnError: false,
    errorRetryCount: 0,
  });

  const handleDownloadPdf = () => {
    window.open(reportService.getReportPdfUrl(workspaceSlug, reportId), "_blank");
  };

  const handleSendTelegram = () => {
    setTelegramLoading(true);
    setTelegramError(null);
    setTelegramMessage(null);
    void reportService
      .sendReportToTelegram(workspaceSlug, reportId)
      .then((res) => {
        setTelegramMessage(res.message);
        return res;
      })
      .catch((err: unknown) => {
        setTelegramError(err instanceof Error ? err.message : "Не удалось отправить");
      })
      .finally(() => {
        setTelegramLoading(false);
      });
  };

  const handleLinkTelegram = () => {
    void reportService
      .createTelegramLinkToken()
      .then((res) => {
        setLinkToken(res.instruction);
        return res;
      })
      .catch((err: unknown) => {
        setTelegramError(err instanceof Error ? err.message : "Не удалось создать токен");
      });
  };

  if (isLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <PageHead title="Отчёт" />
        <p className="text-13 text-tertiary">Загрузка...</p>
      </div>
    );
  }

  if (hasLoadError || !report) {
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
          <div className="flex items-center gap-2">
            <Button
              variant="secondary"
              size="sm"
              onClick={handleDownloadPdf}
              prependIcon={<Download className="size-4" />}
            >
              Скачать PDF
            </Button>
            {telegramStatus?.linked ? (
              <Button
                variant="secondary"
                size="sm"
                loading={telegramLoading}
                disabled={telegramLoading}
                onClick={handleSendTelegram}
                prependIcon={<Send className="size-4" />}
              >
                Отправить в Telegram
              </Button>
            ) : (
              <Button variant="tertiary" size="sm" onClick={handleLinkTelegram}>
                Привязать Telegram
              </Button>
            )}
          </div>
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

          {linkToken && (
            <div className="mt-3 rounded border border-subtle bg-surface-2 px-3 py-2 text-13 text-primary">
              {linkToken}
            </div>
          )}
          {telegramMessage && (
            <div className="mt-3 rounded border border-green-300 bg-green-50 px-3 py-2 text-13 text-green-700 dark:border-green-800 dark:bg-green-950 dark:text-green-400">
              {telegramMessage}
            </div>
          )}
          {telegramError && (
            <div className="mt-3 rounded border border-red-300 bg-red-50 px-3 py-2 text-13 text-red-600 dark:border-red-800 dark:bg-red-950 dark:text-red-400">
              {telegramError}
            </div>
          )}

          <div className="mt-4 rounded border border-subtle bg-surface-1 p-4">
            <pre className="whitespace-pre-wrap font-sans text-13 leading-relaxed text-primary">{report.content}</pre>
          </div>
        </div>
      </div>
    </>
  );
}

export default ReportDetailPage;
