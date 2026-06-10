# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Python imports
from collections import defaultdict
from datetime import date, datetime, timedelta

from django.http import HttpResponse
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

# Module imports
from plane.app.views.external.base import get_llm_config, get_llm_response
from plane.app.views.base import BaseAPIView
from plane.app.views.telegram import send_telegram_document
from plane.db.models import ActivityReport, Issue, UserTelegramLink, Workspace
from plane.authentication.session import BaseSessionAuthentication
from plane.utils.pdf_report import render_report_pdf


REPORT_PROMPT_TEMPLATE = """
Ты — система формирования Agile-отчёта по проекту.
Сформируй структурированный отчёт за указанный период в формате, готовом для выгрузки в PDF.
Стиль — деловой, краткий, без лишних пояснений.
Отчёт пиши на русском языке.

Входные данные:

Название проекта: {project_name}
Период отчёта: {period_from} — {period_to}
Команда: {team}

Данные по задачам (каждая задача: ID, Название, Ответственный, Статус, Приоритет, Story Points, Плановая дата, Фактическая дата, Комментарий):

{tasks_text}

Сформируй отчёт в следующей структуре:
1. Краткое резюме (что планировалось, что выполнено, процент выполнения, основные проблемы)
2. Статистика по задачам (всего, завершено, в работе, заблокировано, просрочено)
3. Выполненные задачи (таблица)
4. В работе (таблица)
5. Проблемы и блокеры (таблица)
6. План на следующий период
7. Риски и проблемы (вероятность, влияние, план реагирования)
8. Вывод (стабильность процесса, проблемные зоны, рекомендации)

Используй чёткие таблицы. Не пиши объяснения вне структуры. Формат — управленческий отчёт.
"""

WEEKLY_REPORT_PROMPT_TEMPLATE = """
Ты — ассистент руководителя IT-портфеля. Сформируй сводный отчёт за период на русском языке.
Стиль: краткий, деловой, готовый для PDF. Без вводных фраз вне структуры.

Период: {period_from} — {period_to}
Workspace: {workspace_name}

Данные по проектам и задачам:

{projects_text}

Сформируй отчёт СТРОГО в такой структуре:

Отчёт за последние 7 дней

Для каждого проекта (нумерованный список, только проекты с активностью за период):
N) Название проекта
- Что сделано (bullet points, кратко, по факту из данных)
- Следующий микро-шаг: (одна строка — главный следующий шаг по проекту)

В конце добавь блок «Итого» — 3–5 предложений: общий прогресс, риски, приоритеты на следующую неделю.
"""


def state_group_to_label(group: str) -> str:
    mapping = {
        "backlog": "Backlog",
        "unstarted": "To Do",
        "started": "In Progress",
        "completed": "Done",
        "cancelled": "Cancelled",
        "triage": "Triage",
    }
    return mapping.get(group, group or "")


def _issue_line(i: Issue) -> str:
    state_label = state_group_to_label(i.state.group) if i.state else ""
    assignee_names = ", ".join(a.display_name or a.email or "" for a in i.assignees.all()) or "—"
    points = str(i.point) if i.point is not None else ""
    target = i.target_date.isoformat() if i.target_date else ""
    completed = i.completed_at.date().isoformat() if i.completed_at else ""
    comment = (i.description_stripped or "")[:500] if i.description_stripped else ""
    return (
        f"ID: {i.sequence_id} | {i.name} | Ответственный: {assignee_names} | "
        f"Статус: {state_label} | Приоритет: {i.priority} | Story Points: {points} | "
        f"Плановая дата: {target} | Фактическая дата: {completed} | Комментарий: {comment}"
    )


def _fetch_issues(project_id=None, project_ids=None, workspace_slug=None, period_from=None, period_to=None):
    qs = Issue.issue_objects
    if project_ids:
        qs = qs.filter(project_id__in=project_ids)
    elif project_id:
        qs = qs.filter(project_id=project_id)
    elif workspace_slug:
        qs = qs.filter(project__workspace__slug=workspace_slug)
    else:
        qs = qs.none()

    if period_from:
        qs = qs.filter(updated_at__date__gte=period_from)
    if period_to:
        qs = qs.filter(updated_at__date__lte=period_to)

    return list(
        qs.select_related("state", "project").prefetch_related("assignees").order_by("project__name", "created_at")[:500]
    )


def build_report_input(project_id=None, project_ids=None, workspace_slug=None, period_from=None, period_to=None):
    """Build task list and metadata for the report prompt."""
    issues = _fetch_issues(project_id, project_ids, workspace_slug, period_from, period_to)

    project_name = "Все проекты"
    team_list = []
    if issues:
        if project_ids and len(project_ids) > 1:
            names = list({i.project.name for i in issues if i.project})
            project_name = "Проекты: " + ", ".join(names) if names else "Несколько проектов"
        elif project_ids or project_id:
            project_name = issues[0].project.name
        else:
            project_name = f"Workspace {workspace_slug}"
        assignees = set()
        for i in issues:
            for a in i.assignees.all():
                assignees.add(a.display_name or a.email or str(a.id))
        team_list = sorted(assignees)

    lines = [_issue_line(i) for i in issues]
    tasks_text = "\n".join(lines) if lines else "Нет задач за выбранный период."
    team = ", ".join(team_list) if team_list else "—"
    period_from_str = period_from.isoformat() if period_from else ""
    period_to_str = period_to.isoformat() if period_to else ""

    return {
        "project_name": project_name,
        "period_from": period_from_str,
        "period_to": period_to_str,
        "team": team,
        "tasks_text": tasks_text,
    }


def build_weekly_report_input(workspace_slug, period_from, period_to):
    issues = _fetch_issues(workspace_slug=workspace_slug, period_from=period_from, period_to=period_to)
    by_project: dict[str, list[Issue]] = defaultdict(list)
    for issue in issues:
        by_project[issue.project.name].append(issue)

    sections = []
    for project_name in sorted(by_project.keys()):
        lines = [_issue_line(i) for i in by_project[project_name]]
        sections.append(f"## {project_name}\n" + "\n".join(lines))

    projects_text = "\n\n".join(sections) if sections else "Нет активности за период."
    workspace = Workspace.objects.filter(slug=workspace_slug).first()
    return {
        "workspace_name": workspace.name if workspace else workspace_slug,
        "period_from": period_from.isoformat() if period_from else "",
        "period_to": period_to.isoformat() if period_to else "",
        "projects_text": projects_text,
    }


def _generate_report_content(prompt_template, input_data, task_instruction):
    api_key, model, provider = get_llm_config()
    if not api_key or not model or not provider:
        return None, "LLM не настроен (нужен API-ключ и провайдер)."
    prompt = prompt_template.format(**input_data)
    return get_llm_response(task_instruction, prompt, api_key, model, provider)


def _report_response(report: ActivityReport):
    return {
        "id": str(report.id),
        "title": report.title,
        "content": report.content,
        "period_from": report.period_from.isoformat() if report.period_from else None,
        "period_to": report.period_to.isoformat() if report.period_to else None,
        "created_at": report.created_at.isoformat() if report.created_at else None,
        "created_by": report.created_by.display_name if report.created_by else None,
    }


class WorkspaceReportsEndpoint(BaseAPIView):
    """List and create activity reports scoped to a workspace."""
    permission_classes = [IsAuthenticated]
    authentication_classes = [BaseSessionAuthentication]

    def get(self, request, slug):
        project_id = request.query_params.get("project_id")
        workspace = Workspace.objects.filter(slug=slug).first()
        if not workspace:
            return Response({"error": "Рабочее пространство не найдено"}, status=status.HTTP_404_NOT_FOUND)
        qs = ActivityReport.objects.filter(workspace=workspace).order_by("-created_at")
        if project_id:
            qs = qs.filter(project_id=project_id)
        reports = qs[:50]
        data = [
            {
                "id": str(r.id),
                "title": r.title or f"Отчёт {r.period_from or ''} — {r.period_to or ''}",
                "period_from": r.period_from.isoformat() if r.period_from else None,
                "period_to": r.period_to.isoformat() if r.period_to else None,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "created_by": r.created_by.display_name if r.created_by else None,
            }
            for r in reports
        ]
        return Response(data, status=status.HTTP_200_OK)

    def post(self, request, slug):
        period_from = request.data.get("period_from")
        period_to = request.data.get("period_to")
        project_id = request.data.get("project_id")
        project_ids = request.data.get("project_ids")
        title = request.data.get("title", "").strip()

        workspace = Workspace.objects.filter(slug=slug).first()
        if not workspace:
            return Response({"error": "Рабочее пространство не найдено"}, status=status.HTTP_404_NOT_FOUND)

        if not period_from or not period_to:
            return Response(
                {"error": "period_from и period_to обязательны (YYYY-MM-DD)"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            period_from = datetime.strptime(period_from, "%Y-%m-%d").date()
            period_to = datetime.strptime(period_to, "%Y-%m-%d").date()
        except ValueError:
            return Response(
                {"error": "Неверный формат даты. Используйте YYYY-MM-DD"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not project_ids and not project_id:
            project_ids = None

        if project_ids and not isinstance(project_ids, list):
            project_ids = [project_ids]
        if project_ids:
            project_ids = [p for p in project_ids if p]

        input_data = build_report_input(
            project_id=project_id if not project_ids else None,
            project_ids=project_ids or None,
            workspace_slug=slug,
            period_from=period_from,
            period_to=period_to,
        )
        text, error = _generate_report_content(
            REPORT_PROMPT_TEMPLATE,
            input_data,
            "Сформируй Agile-отчёт по проекту на основе приведённых входных данных.",
        )
        if error or not text:
            return Response(
                {"error": error or "Не удалось сгенерировать отчёт"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        report_project_id = None
        if project_ids and len(project_ids) == 1:
            report_project_id = project_ids[0]
        elif project_id:
            report_project_id = project_id

        report = ActivityReport.objects.create(
            title=title or f"Отчёт {period_from} — {period_to}",
            content=text,
            period_from=period_from,
            period_to=period_to,
            project_id=report_project_id,
            workspace_id=workspace.id,
            created_by=request.user,
        )
        return Response(_report_response(report), status=status.HTTP_201_CREATED)


class WorkspaceWeeklyReportEndpoint(BaseAPIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [BaseSessionAuthentication]

    def post(self, request, slug):
        workspace = Workspace.objects.filter(slug=slug).first()
        if not workspace:
            return Response({"error": "Рабочее пространство не найдено"}, status=status.HTTP_404_NOT_FOUND)

        period_to = date.today()
        period_from = period_to - timedelta(days=6)

        input_data = build_weekly_report_input(slug, period_from, period_to)
        text, error = _generate_report_content(
            WEEKLY_REPORT_PROMPT_TEMPLATE,
            input_data,
            "Сформируй сводный недельный отчёт по всем проектам workspace.",
        )
        if error or not text:
            return Response(
                {"error": error or "Не удалось сгенерировать отчёт"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        report = ActivityReport.objects.create(
            title="Отчёт за последние 7 дней",
            content=text,
            period_from=period_from,
            period_to=period_to,
            workspace_id=workspace.id,
            created_by=request.user,
        )
        return Response(_report_response(report), status=status.HTTP_201_CREATED)


class WorkspaceReportDetailEndpoint(BaseAPIView):
    """Get one report by id."""
    permission_classes = [IsAuthenticated]
    authentication_classes = [BaseSessionAuthentication]

    def get(self, request, slug, pk):
        try:
            report = ActivityReport.objects.get(pk=pk, workspace__slug=slug)
        except ActivityReport.DoesNotExist:
            return Response({"error": "Отчёт не найден"}, status=status.HTTP_404_NOT_FOUND)
        return Response(_report_response(report), status=status.HTTP_200_OK)


class WorkspaceReportPdfEndpoint(BaseAPIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [BaseSessionAuthentication]

    def get(self, request, slug, pk):
        try:
            report = ActivityReport.objects.get(pk=pk, workspace__slug=slug)
        except ActivityReport.DoesNotExist:
            return Response({"error": "Отчёт не найден"}, status=status.HTTP_404_NOT_FOUND)

        pdf_bytes = render_report_pdf(
            title=report.title or "Отчёт",
            content=report.content,
            period_from=report.period_from.isoformat() if report.period_from else "",
            period_to=report.period_to.isoformat() if report.period_to else "",
        )
        filename = f"report-{report.id}.pdf"
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response


class WorkspaceReportSendTelegramEndpoint(BaseAPIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [BaseSessionAuthentication]

    def post(self, request, slug, pk):
        try:
            report = ActivityReport.objects.get(pk=pk, workspace__slug=slug)
        except ActivityReport.DoesNotExist:
            return Response({"error": "Отчёт не найден"}, status=status.HTTP_404_NOT_FOUND)

        link = UserTelegramLink.objects.filter(user=request.user).first()
        if not link:
            return Response(
                {"error": "Telegram не привязан. Создайте токен привязки в настройках профиля."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        pdf_bytes = render_report_pdf(
            title=report.title or "Отчёт",
            content=report.content,
            period_from=report.period_from.isoformat() if report.period_from else "",
            period_to=report.period_to.isoformat() if report.period_to else "",
        )
        ok, err = send_telegram_document(
            chat_id=link.telegram_chat_id,
            file_bytes=pdf_bytes,
            filename=f"{report.title or 'report'}.pdf",
            caption=report.title or "Отчёт Plane",
        )
        if not ok:
            return Response({"error": err or "Не удалось отправить в Telegram"}, status=status.HTTP_502_BAD_GATEWAY)
        return Response({"success": True, "message": "Отчёт отправлен в Telegram"}, status=status.HTTP_200_OK)
