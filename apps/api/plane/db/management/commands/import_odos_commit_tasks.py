# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from plane.db.models import Issue, IssueAssignee, IssueLink, Project, State, User, Workspace

COMMIT_SHA = "616bfbc2"
COMMIT_URL = "https://github.com/Va11eyard/ODOS/commit/616bfbc2cc1e6919c87f201bbdff63128ffe9bdf"
ROOT_MARKER = f"[GitHub {COMMIT_SHA}]"

WORKSPACE_SLUG = "ihealth"
PROJECT_NAME = "ODOS Check UP"
OWNER_EMAIL = "admin@pro-ecta.kz"
ASSIGNEE_EMAIL = "dimash@galamat.com"

EPIC = {
    "title": "feat(patient,web): результаты скрининга, выход из сессии, анкета по коррекции",
    "summary": (
        "Результаты скрининга, выход из сессии, анкета по коррекции (очки/линзы v2) "
        "и колонка «Коррекция» в списке пациентов. "
        "Затронуто: apps/patient, apps/web, internal/domain, internal/usecase, "
        "internal/delivery/http, internal/repository/postgres, packages/test-ui."
    ),
    "sections": [
        {
            "title": "Пациентское приложение — хаб и «Мой результат»",
            "tasks": [
                "Кнопка «Мой результат» в TestHubHeader → /test/[sessionId]/results",
                "Страница PatientMyResults + route results/page.tsx",
                "Парсинг результатов: patient-test-results.ts (карточки риска, сводка сессии)",
                "Rule-based ODOS AI: patient-results-ai.ts (рекомендации, Q&A, ai_summary из анкеты)",
                "fetchSessionTestResults() в api.ts",
                "TestHubHeader на странице результатов (отправка теста, профиль, выход)",
                "Навигация «Назад» — иконка ArrowLeft вместо «←»",
            ],
        },
        {
            "title": "Пациентское приложение — пост-тест и навигация",
            "tasks": [
                "После теста основная кнопка ведёт на хаб («На главную»), не к следующему тесту",
                "primaryButtonLabel в PostTestFlow / RiskResult / OdosTestRiskResultShell (@odos/test-ui)",
                "IshiharaManualAnswerPad: иконка Delete вместо «←» на клавиатуре ответов",
            ],
        },
        {
            "title": "Пациентское приложение — выход из сессии",
            "tasks": [
                "exitPatientSession() (patient-session-exit.ts) — единая точка выхода",
                "Маршрут после выхода: accessCode → /enter-code, аккаунт → /login",
                "router.replace с ?logged_out=1 / ?expired=1 вместо push",
                "PatientSessionProvider: не восстанавливать сессию при logged_out/expired на login/enter-code",
                "Обновлены обработчики выхода: хаб, тесты, результаты, PatientSessionChrome, анкета (401)",
                "Сообщения «Вы вышли из сессии» на enter-code и login",
            ],
        },
        {
            "title": "Анкета о здоровье — очки/линзы (v2)",
            "tasks": [
                "Вопрос glasses: «Использовали ли вы когда-либо очки или контактные линзы?»",
                "Ответы: no / yes (сейчас не ношу) / still_wearing (ношу сейчас)",
                "Backend: валидация v2; legacy distance/near/always → still_wearing",
                "domain/glasses_history.go: NormalizeGlassesHistory, IsValidGlassesHistoryAnswer, GlassesHistoryFromQuestionnaireJSON",
                "AI summary анкеты учитывает текущую и прошлую коррекцию",
            ],
        },
        {
            "title": "Админка (web) — колонка «Коррекция»",
            "tasks": [
                "GET /patients и GET /patients/:id возвращают glasses_history",
                "PatientScreeningSnapshot + поле GlassesHistory из health_questionnaire_json",
                "Тип GlassesHistory в api.ts; GLASSES_HISTORY_LABELS в patients.ts",
                "PatientTable: колонка «Коррекция» (Нет / Да / Ношу сейчас / —)",
                "Карта миопии (heatmap) без изменений — только risk_level из тестов",
            ],
        },
        {
            "title": "Тесты",
            "tasks": [
                "domain/glasses_history_test.go, health_questionnaire_test.go (still_wearing в AI summary)",
                "screening_test.go: CompleteSessionValidated для patient с заполненной анкетой",
            ],
        },
    ],
}


def html_desc(text: str) -> str:
    return f"<p>{text}</p>"


class Command(BaseCommand):
    help = "Import latest ODOS GitHub commit tasks into Plane (iHealth / ODOS Check UP)"

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Delete existing import and re-create")

    def handle(self, *args, **options):
        workspace = Workspace.objects.filter(slug=WORKSPACE_SLUG).first()
        if not workspace:
            raise CommandError(f"Workspace {WORKSPACE_SLUG} not found")

        project = Project.objects.filter(workspace=workspace, name=PROJECT_NAME).first()
        if not project:
            raise CommandError(f"Project '{PROJECT_NAME}' not found in {WORKSPACE_SLUG}")

        owner = User.objects.filter(email=OWNER_EMAIL).first()
        assignee = User.objects.filter(email=ASSIGNEE_EMAIL).first()
        if not owner or not assignee:
            raise CommandError("Owner or assignee user not found")

        done_state = State.objects.filter(project=project, group="completed").first()
        if not done_state:
            raise CommandError("Completed state not found for project")

        root_name = f"{ROOT_MARKER} {EPIC['title']}"[:255]
        existing = Issue.objects.filter(project=project, name=root_name).first()
        if existing and not options["force"]:
            self.stdout.write(self.style.WARNING(f"Import already exists: {root_name}. Use --force to re-import."))
            return

        with transaction.atomic():
            if existing and options["force"]:
                Issue.objects.filter(project=project, name__startswith=ROOT_MARKER).delete()
                self.stdout.write(self.style.WARNING("Removed previous import"))

            root = self._create_issue(
                project=project,
                workspace=workspace,
                name=root_name,
                description=EPIC["summary"],
                state=done_state,
                owner=owner,
                assignee=assignee,
                parent=None,
            )
            IssueLink.objects.create(
                issue=root,
                project=project,
                workspace=workspace,
                title="GitHub commit",
                url=COMMIT_URL,
                created_by=owner,
            )

            section_count = 0
            task_count = 0
            for section in EPIC["sections"]:
                section_issue = self._create_issue(
                    project=project,
                    workspace=workspace,
                    name=section["title"][:255],
                    description=f"Section from {COMMIT_URL}",
                    state=done_state,
                    owner=owner,
                    assignee=assignee,
                    parent=root,
                )
                section_count += 1
                for task_title in section["tasks"]:
                    self._create_issue(
                        project=project,
                        workspace=workspace,
                        name=task_title[:255],
                        description=f"Imported from ODOS commit {COMMIT_SHA}",
                        state=done_state,
                        owner=owner,
                        assignee=assignee,
                        parent=section_issue,
                    )
                    task_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Created epic + {section_count} sections + {task_count} tasks in {PROJECT_NAME}"
            )
        )

    def _create_issue(self, *, project, workspace, name, description, state, owner, assignee, parent):
        issue = Issue(
            project=project,
            workspace=workspace,
            name=name,
            description_html=html_desc(description),
            description_stripped=description,
            state=state,
            parent=parent,
            priority="medium",
            created_by=owner,
            updated_by=owner,
        )
        issue.save()
        Issue.objects.filter(pk=issue.pk).update(completed_at=timezone.now())
        IssueAssignee.objects.get_or_create(
            issue=issue,
            assignee=assignee,
            project=project,
            workspace=workspace,
            defaults={"created_by": owner, "updated_by": owner},
        )
        return issue
