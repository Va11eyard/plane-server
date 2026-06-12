# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from plane.db.models import Issue, IssueAssignee, IssueLink, Project, State, User, Workspace

COMMIT_SHA = "bc13e762"
COMMIT_URL = "https://github.com/Va11eyard/ODOS/commit/bc13e762b6413feea6c5f45913fe4c96b6d18b5a"
ROOT_MARKER = f"[GitHub {COMMIT_SHA}]"

WORKSPACE_SLUG = "ihealth"
PROJECT_NAME = "ODOS Check UP"
OWNER_EMAIL = "admin@pro-ecta.kz"
ASSIGNEE_EMAIL = "dimash@galamat.com"

EPIC = {
    "title": "feat(patient): patient accounts, full screening UX, and post-test risk flows",
    "summary": (
        "End-to-end patient self-service and Figma-aligned vision screening across patient app, "
        "shared test packages, staff web app, and API."
    ),
    "sections": [
        {
            "title": "Patient authentication and onboarding",
            "tasks": [
                "Login, registration, mandatory password change, and multi-step onboarding wizard",
                "Session-scoped storage for pending onboarding and password-change credentials",
                "Extend usePatientAuth: password login, registration, onboarding, forced password-change routing",
                "Patient-account API client (org search, onboarding, change-password)",
                "Shared FormSubmitHandler type; replace deprecated React FormEvent on auth forms",
                "Fix react-hooks/set-state-in-effect lint (lazy useState, useEffect for redirects only)",
            ],
        },
        {
            "title": "Backend: patient accounts, PHI, and questionnaire",
            "tasks": [
                "Migrations 000013–000020: patient accounts, onboarding, encrypted payloads, questionnaire",
                "Patient account auth HTTP handlers, repository, and use cases",
                "Encrypt test-result payloads at rest; extend PHI/crypto helpers",
                "Health questionnaire domain, use case, and persistence",
                "Wire new routes in API router; update screening/patient use cases",
                "Report findings helpers and screening rule updates",
            ],
        },
        {
            "title": "Patient app: test hub and session flow",
            "tasks": [
                "Rebuild test session hub: program cards, prep, calibration, comprehensive ordering",
                "Fix session expiry: defer token clear until post-test UI finishes",
                "Remove staff-only placeholders; unify flow via test-program meta",
                "Health questionnaire route and wizard UI under test session",
                "Expand test orchestration: prep → live test → disclaimer → risk → deferred API submit",
            ],
        },
        {
            "title": "Vision tests — Shared test-engine",
            "tasks": [
                "Risk/summary modules: landolt, stress, duochrome, ishihara, radiant, pelli, amsler",
                "Align Pelli–Robson risk bands and subtitles with ТЗ",
                "Amsler risk subtitles per finding type",
                "Replace deprecated ISHIHARA_DIAGNOSIS_LABEL_RU with DIAGNOSIS_LABELS",
                "Fix DOM typing: globalThis instead of window in test-engine",
                "Fix radiant-acuity pair-id narrowing; extend purkinje-csf tests",
            ],
        },
        {
            "title": "Vision tests — Shared test-ui",
            "tasks": [
                "Figma-aligned shells: how-to, layouts, complete transitions, post-test flows",
                "OdosTestRiskResultShell with inline risk-banner colors (Tailwind purge fix)",
                "Pelli–Robson results: TZ-based copy, logCS / accuracy / time metrics",
                "Amsler results: per-eye outcomes, distortion zone count, risk-colored banner",
                "Astigmatism dial geometry fixes; export full test-ui surface",
            ],
        },
        {
            "title": "Vision tests — Patient implementations",
            "tasks": [
                "Landolt & Stress: MonocularTestFlow, StressTestUI, deferred submit + post-test flow",
                "Ishihara: manual answer pad, plate flow, post-test risk UI",
                "Duochrome, Astigmatism, Amsler, Pelli–Robson: live UI wired to new layouts",
                "Amsler: 3-step how-to, distortion choice, draw canvas, zone scanning payload",
                "Pelli–Robson: Sloan input, contrast steps, stop rule, 4.36 mm letter sizing",
                "Radiant figure: dial-based axis selection and updated sizing hooks",
            ],
        },
        {
            "title": "Staff web app",
            "tasks": [
                "CreatePatientDialog: optional patient account provisioning with credentials modal",
                "Update patient table/detail tabs, screening creation, triage, and results views",
                "Align web test components and Ishihara results with shared engine labels",
                "Screening session events API route; session event hook updates",
            ],
        },
        {
            "title": "Assets and tooling",
            "tasks": [
                "Patient/web public assets (Amsler SVGs, astigmatism, prep icons, logos, favicons)",
                "Point patient Tailwind @source at packages/test-ui",
                "Update .env.example, docker-compose, and root package scripts",
            ],
        },
        {
            "title": "Lint and TypeScript hygiene",
            "tasks": [
                "OrganizationPicker: drop redundant value→query sync effect",
                "MonocularTestFlow: remove unused onClose prop",
                "CreatePatientDialog: handleCreateDialogOpenChange for form reset on close",
                "Patient/web IshiharaResultsScreen: migrate to DIAGNOSIS_LABELS",
            ],
        },
        {
            "title": "Breaking changes & rollout",
            "tasks": [
                "Apply DB migrations 000013–000020 on all environments",
                "Configure new patient-auth env vars",
                "Verify account-backed patient app flows after deploy",
                "Verify staff can provision logins from Create Patient dialog",
            ],
        },
    ],
}


def html_desc(text: str) -> str:
    return f"<p>{text}</p>"


class Command(BaseCommand):
    help = "Import ODOS GitHub commit bc13e762 tasks into Plane (iHealth / ODOS Check UP)"

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
