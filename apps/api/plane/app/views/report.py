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


PORTFOLIO_REPORT_PROMPT_TEMPLATE = """
Ты — ассистент руководителя IT-портфеля в здравоохранении. Сформируй управленческий отчёт о деятельности
за период на русском языке. Стиль — как портфельный отчёт для руководства: суммаризация, выводы, приоритеты.
Не перечисляй задачи дословно — группируй в бизнес-результаты и управленческие выводы.
Если данных недостаточно для раздела — кратко укажи «н/д» или опусти подпункт, не выдумывай факты.

Портфель / workspace: {workspace_name}
Период: {period_from} — {period_to}
Автор отчёта: {author_name}
Команда: {team}

Сводная статистика:
{stats_summary}

Детализация по проектам:
{projects_summary}

Сформируй отчёт СТРОГО в Markdown по структуре ниже (заголовки и таблицы обязательны):

# ОТЧЁТ О ДЕЯТЕЛЬНОСТИ
## {workspace_name}
Период: {period_from} — {period_to}
{author_name}

### Масштаб портфеля
2–4 предложения: сколько проектов в работе, общая картина за период, ключевой вывод.

## РАЗДЕЛ 1. СВОДНАЯ ТАБЛИЦА ПО ВСЕМ ПРОЕКТАМ
| Проект | Статус | Завершено | В работе | Что произошло за период |
|--------|--------|-----------|----------|-------------------------|
(строка на каждый проект с активностью; «Что произошло» — 1–2 предложения суммаризации, не список задач)

## РАЗДЕЛ 2. ЧТО КОНКРЕТНО ИЗМЕНИЛОСЬ В ПРОЕКТАХ
Для каждого проекта с активностью:

### Название проекта
**Старт vs. текущее состояние**
Кратко: что было в начале периода → что сейчас (по данным задач).

**Что было сделано**
- 3–7 bullet points с суммаризацией завершённой работы

**Проблемы и выводы**
- 1–3 bullet points: блокеры, риски, инсайты

## РАЗДЕЛ 3. СТАТИСТИКА И РИСКИ
| Показатель | Значение |
|------------|----------|
| Всего задач с активностью | ... |
| Завершено | ... |
| В работе | ... |
| Просрочено | ... |
| Проектов с активностью | ... |

Краткий абзац: главные риски и узкие места.

## РАЗДЕЛ 4. ПРИОРИТЕТЫ НА СЛЕДУЮЩИЙ ПЕРИОД
| Проект | Конкретный следующий шаг | Что это проверит |
|--------|--------------------------|------------------|
(топ-5–7 приоритетов по проектам)

---
Отчёт подготовлен: {report_date} · {author_name}
"""

PROJECT_REPORT_PROMPT_TEMPLATE = """
Ты — ассистент руководителя проекта. Сформируй отчёт о деятельности за период на русском языке.
Стиль — управленческий, с суммаризацией. Не перечисляй задачи дословно — группируй в результаты.

Проект: {project_name}
Период: {period_from} — {period_to}
Автор: {author_name}
Команда: {team}

Статистика:
{stats_summary}

Задачи:
{tasks_text}

Сформируй отчёт в Markdown:

# ОТЧЁТ О ДЕЯТЕЛЬНОСТИ
## {project_name}
Период: {period_from} — {period_to}
{author_name}

### Краткое резюме
2–3 предложения: прогресс, % выполнения, главная проблема.

## Статистика
| Показатель | Значение |
|------------|----------|
| Всего задач | ... |
| Завершено | ... |
| В работе | ... |
| Просрочено | ... |

## Что сделано
- bullet points (суммаризация завершённых задач)

## В работе и блокеры
- bullet points

## План и приоритеты
| Задача / направление | Следующий шаг | Срок |
|----------------------|---------------|------|

## Выводы
2–4 предложения: стабильность, риски, рекомендации.

---
Отчёт подготовлен: {report_date} · {author_name}
"""

WEEKLY_REPORT_PROMPT_TEMPLATE = PORTFOLIO_REPORT_PROMPT_TEMPLATE


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


def _project_status_label(completed: int, in_progress: int, total: int) -> str:
    if total == 0:
        return "Без активности"
    if completed == total:
        return "Завершён"
    if in_progress > 0:
        return "Активно"
    return "В планах"


def _aggregate_issues(issues: list[Issue]) -> dict[str, dict]:
    today = date.today()
    by_project: dict[str, dict] = {}
    for issue in issues:
        project_name = issue.project.name if issue.project else "Без проекта"
        if project_name not in by_project:
            by_project[project_name] = {
                "total": 0,
                "completed": 0,
                "in_progress": 0,
                "backlog": 0,
                "overdue": 0,
                "cancelled": 0,
                "completed_tasks": [],
                "active_tasks": [],
                "assignees": set(),
            }
        stats = by_project[project_name]
        stats["total"] += 1
        group = issue.state.group if issue.state else ""
        if group == "completed":
            stats["completed"] += 1
            if len(stats["completed_tasks"]) < 20:
                stats["completed_tasks"].append(issue.name)
        elif group in ("started",):
            stats["in_progress"] += 1
            if len(stats["active_tasks"]) < 15:
                stats["active_tasks"].append(issue.name)
        elif group in ("cancelled",):
            stats["cancelled"] += 1
        else:
            stats["backlog"] += 1
            if len(stats["active_tasks"]) < 15:
                stats["active_tasks"].append(issue.name)

        if issue.target_date and issue.target_date < today and group != "completed":
            stats["overdue"] += 1

        for assignee in issue.assignees.all():
            stats["assignees"].add(assignee.display_name or assignee.email or str(assignee.id))

    return by_project


def _build_stats_summary(by_project: dict[str, dict]) -> str:
    if not by_project:
        return "Нет активности за выбранный период."

    total = sum(s["total"] for s in by_project.values())
    completed = sum(s["completed"] for s in by_project.values())
    in_progress = sum(s["in_progress"] for s in by_project.values())
    overdue = sum(s["overdue"] for s in by_project.values())
    active_projects = sum(1 for s in by_project.values() if s["total"] > 0)

    pct = round(completed / total * 100) if total else 0
    return (
        f"Проектов с активностью: {active_projects}\n"
        f"Всего задач с активностью: {total}\n"
        f"Завершено: {completed} ({pct}%)\n"
        f"В работе: {in_progress}\n"
        f"Просрочено: {overdue}"
    )


def _build_projects_summary(by_project: dict[str, dict], issues: list[Issue]) -> str:
    if not by_project:
        return "Нет данных по проектам."

    sections = []
    issues_by_project: dict[str, list[Issue]] = defaultdict(list)
    for issue in issues:
        pname = issue.project.name if issue.project else "Без проекта"
        issues_by_project[pname].append(issue)

    for project_name in sorted(by_project.keys()):
        stats = by_project[project_name]
        status = _project_status_label(stats["completed"], stats["in_progress"], stats["total"])
        lines = [
            f"### {project_name}",
            f"Статус: {status} | Всего: {stats['total']} | Завершено: {stats['completed']} | "
            f"В работе: {stats['in_progress']} | Просрочено: {stats['overdue']}",
            f"Команда: {', '.join(sorted(stats['assignees'])) or '—'}",
        ]
        if stats["completed_tasks"]:
            lines.append("Завершено (ключевые задачи): " + "; ".join(stats["completed_tasks"][:12]))
        if stats["active_tasks"]:
            lines.append("В работе / открыто: " + "; ".join(stats["active_tasks"][:10]))

        sample_lines = [_issue_line(i) for i in issues_by_project[project_name][:25]]
        if sample_lines:
            lines.append("Детали задач:\n" + "\n".join(sample_lines))
        sections.append("\n".join(lines))

    return "\n\n".join(sections)


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


def _is_portfolio_scope(project_id=None, project_ids=None) -> bool:
    if project_ids and len(project_ids) > 1:
        return True
    if not project_id and not project_ids:
        return True
    return False


def build_report_input(
    project_id=None,
    project_ids=None,
    workspace_slug=None,
    period_from=None,
    period_to=None,
    author_name="",
):
    """Build task list and metadata for the report prompt."""
    issues = _fetch_issues(project_id, project_ids, workspace_slug, period_from, period_to)
    by_project = _aggregate_issues(issues)

    workspace = Workspace.objects.filter(slug=workspace_slug).first() if workspace_slug else None
    workspace_name = workspace.name if workspace else (workspace_slug or "Портфель")

    project_name = "Все проекты"
    team_list: set[str] = set()
    if issues:
        if project_ids and len(project_ids) > 1:
            names = list({i.project.name for i in issues if i.project})
            project_name = "Проекты: " + ", ".join(names) if names else "Несколько проектов"
        elif project_ids or project_id:
            project_name = issues[0].project.name
        else:
            project_name = workspace_name
        for stats in by_project.values():
            team_list.update(stats["assignees"])

    lines = [_issue_line(i) for i in issues[:80]]
    tasks_text = "\n".join(lines) if lines else "Нет задач за выбранный период."
    team = ", ".join(sorted(team_list)) if team_list else "—"
    period_from_str = period_from.isoformat() if period_from else ""
    period_to_str = period_to.isoformat() if period_to else ""
    report_date = date.today().isoformat()

    return {
        "project_name": project_name,
        "workspace_name": workspace_name,
        "period_from": period_from_str,
        "period_to": period_to_str,
        "team": team,
        "tasks_text": tasks_text,
        "stats_summary": _build_stats_summary(by_project),
        "projects_summary": _build_projects_summary(by_project, issues),
        "author_name": author_name or "—",
        "report_date": report_date,
        "is_portfolio": _is_portfolio_scope(project_id, project_ids),
    }


def build_weekly_report_input(workspace_slug, period_from, period_to, author_name=""):
    issues = _fetch_issues(workspace_slug=workspace_slug, period_from=period_from, period_to=period_to)
    by_project = _aggregate_issues(issues)
    workspace = Workspace.objects.filter(slug=workspace_slug).first()

    team_list: set[str] = set()
    for stats in by_project.values():
        team_list.update(stats["assignees"])

    return {
        "workspace_name": workspace.name if workspace else workspace_slug,
        "period_from": period_from.isoformat() if period_from else "",
        "period_to": period_to.isoformat() if period_to else "",
        "team": ", ".join(sorted(team_list)) if team_list else "—",
        "stats_summary": _build_stats_summary(by_project),
        "projects_summary": _build_projects_summary(by_project, issues),
        "author_name": author_name or "—",
        "report_date": date.today().isoformat(),
    }


def _generate_report_content(prompt_template, input_data, task_instruction):
    api_key, model, provider = get_llm_config()
    if not api_key or not model or not provider:
        return None, "LLM не настроен (нужен API-ключ и провайдер)."
    prompt = prompt_template.format(**input_data)
    return get_llm_response(task_instruction, prompt, api_key, model, provider)


def generate_activity_report(
    *,
    workspace,
    user,
    period_from: date,
    period_to: date,
    project_id=None,
    project_ids=None,
    title: str = "",
) -> tuple[ActivityReport | None, str | None]:
    """Create an activity report via LLM. Shared by API and Telegram bot."""
    if not project_ids and not project_id:
        project_ids = None

    if project_ids and not isinstance(project_ids, list):
        project_ids = [project_ids]
    if project_ids:
        project_ids = [p for p in project_ids if p]

    author_name = user.display_name or user.email or ""
    input_data = build_report_input(
        project_id=project_id if not project_ids else None,
        project_ids=project_ids or None,
        workspace_slug=workspace.slug,
        period_from=period_from,
        period_to=period_to,
        author_name=author_name,
    )
    prompt_template = (
        PORTFOLIO_REPORT_PROMPT_TEMPLATE if input_data["is_portfolio"] else PROJECT_REPORT_PROMPT_TEMPLATE
    )
    task_instruction = (
        "Сформируй портфельный отчёт о деятельности с суммаризацией по проектам."
        if input_data["is_portfolio"]
        else "Сформируй отчёт о деятельности по одному проекту с суммаризацией."
    )
    text, error = _generate_report_content(prompt_template, input_data, task_instruction)
    if error or not text:
        return None, error or "Не удалось сгенерировать отчёт"

    report_project_id = None
    if project_ids and len(project_ids) == 1:
        report_project_id = project_ids[0]
    elif project_id:
        report_project_id = project_id

    default_title = (
        f"Отчёт о деятельности {period_from} — {period_to}"
        if input_data["is_portfolio"]
        else f"Отчёт {input_data['project_name']} {period_from} — {period_to}"
    )
    report = ActivityReport.objects.create(
        title=title or default_title,
        content=text,
        period_from=period_from,
        period_to=period_to,
        project_id=report_project_id,
        workspace_id=workspace.id,
        created_by=user,
    )
    return report, None


def _report_response(report: ActivityReport):
    return {
        "id": str(report.id),
        "title": report.title,
        "content": report.content or "",
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

        report, error = generate_activity_report(
            workspace=workspace,
            user=request.user,
            period_from=period_from,
            period_to=period_to,
            project_id=project_id if not project_ids else None,
            project_ids=project_ids or None,
            title=title,
        )
        if error or not report:
            return Response(
                {"error": error or "Не удалось сгенерировать отчёт"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
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

        author_name = request.user.display_name or request.user.email or ""
        input_data = build_weekly_report_input(slug, period_from, period_to, author_name=author_name)
        text, error = _generate_report_content(
            WEEKLY_REPORT_PROMPT_TEMPLATE,
            input_data,
            "Сформируй портфельный отчёт о деятельности за неделю с суммаризацией по проектам.",
        )
        if error or not text:
            return Response(
                {"error": error or "Не удалось сгенерировать отчёт"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        report = ActivityReport.objects.create(
            title=f"Отчёт о деятельности {period_from} — {period_to}",
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
            author=report.created_by.display_name if report.created_by else "",
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
            author=report.created_by.display_name if report.created_by else "",
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
