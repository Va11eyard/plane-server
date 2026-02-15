# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Python imports
from datetime import datetime

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

# Module imports
from plane.app.views.external.base import get_llm_config, get_llm_response
from plane.app.views.base import BaseAPIView
from plane.db.models import ActivityReport, Issue, Project, Workspace
from plane.authentication.session import BaseSessionAuthentication


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


def build_report_input(project_id=None, project_ids=None, workspace_slug=None, period_from=None, period_to=None):
    """Build task list and metadata for the report prompt. Use project_ids (list) for multiple projects."""
    qs = Issue.issue_objects
    if project_ids:
        qs = qs.filter(project_id__in=project_ids)
    elif project_id:
        qs = qs.filter(project_id=project_id)
    elif workspace_slug:
        qs = qs.filter(project__workspace__slug=workspace_slug)
    else:
        qs = qs.none()

    # Activity in period: issues updated (or created) in range — captures "moved to done", etc.
    if period_from:
        qs = qs.filter(updated_at__date__gte=period_from)
    if period_to:
        qs = qs.filter(updated_at__date__lte=period_to)

    qs = qs.select_related("state", "project").prefetch_related("assignees").order_by("created_at")
    issues = list(qs[:500])  # limit for token size

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

    lines = []
    for i in issues:
        state_label = state_group_to_label(i.state.group) if i.state else ""
        assignee_names = ", ".join(a.display_name or a.email or "" for a in i.assignees.all()) or "—"
        points = str(i.point) if i.point is not None else ""
        start = i.start_date.isoformat() if i.start_date else ""
        target = i.target_date.isoformat() if i.target_date else ""
        completed = i.completed_at.date().isoformat() if i.completed_at else ""
        comment = (i.description_stripped or "")[:200] if i.description_stripped else ""
        lines.append(
            f"ID: {i.sequence_id} | {i.name} | Ответственный: {assignee_names} | "
            f"Статус: {state_label} | Приоритет: {i.priority} | Story Points: {points} | "
            f"Плановая дата: {target} | Фактическая дата: {completed} | Комментарий: {comment}"
        )
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
        project_ids = request.data.get("project_ids")  # list of UUIDs
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
            # Use entire workspace
            project_ids = None

        if project_ids and not isinstance(project_ids, list):
            project_ids = [project_ids]
        if project_ids:
            project_ids = [p for p in project_ids if p]

        api_key, model, provider = get_llm_config()
        if not api_key or not model or not provider:
            return Response(
                {"error": "LLM не настроен (нужен API-ключ и провайдер). Настройте DeepSeek или другого провайдера в настройках инстанса."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        input_data = build_report_input(
            project_id=project_id if not project_ids else None,
            project_ids=project_ids or None,
            workspace_slug=slug,
            period_from=period_from,
            period_to=period_to,
        )
        prompt = REPORT_PROMPT_TEMPLATE.format(**input_data)
        task_instruction = "Сформируй Agile-отчёт по проекту на основе приведённых входных данных."

        text, error = get_llm_response(task_instruction, prompt, api_key, model, provider)
        if error or not text:
            return Response(
                {"error": error or "Не удалось сгенерировать отчёт"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        # For list filtering: single project -> report.project_id; multiple or workspace -> workspace only
        report_project_id = None
        if project_ids:
            if len(project_ids) == 1:
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
        return Response(
            {
                "id": str(report.id),
                "title": report.title,
                "content": report.content,
                "period_from": report.period_from.isoformat() if report.period_from else None,
                "period_to": report.period_to.isoformat() if report.period_to else None,
                "created_at": report.created_at.isoformat() if report.created_at else None,
            },
            status=status.HTTP_201_CREATED,
        )


class WorkspaceReportDetailEndpoint(BaseAPIView):
    """Get one report by id."""
    permission_classes = [IsAuthenticated]
    authentication_classes = [BaseSessionAuthentication]

    def get(self, request, slug, pk):
        try:
            report = ActivityReport.objects.get(pk=pk, workspace__slug=slug)
        except ActivityReport.DoesNotExist:
            return Response({"error": "Отчёт не найден"}, status=status.HTTP_404_NOT_FOUND)
        return Response(
            {
                "id": str(report.id),
                "title": report.title,
                "content": report.content,
                "period_from": report.period_from.isoformat() if report.period_from else None,
                "period_to": report.period_to.isoformat() if report.period_to else None,
                "created_at": report.created_at.isoformat() if report.created_at else None,
                "created_by": report.created_by.display_name if report.created_by else None,
            },
            status=status.HTTP_200_OK,
        )
