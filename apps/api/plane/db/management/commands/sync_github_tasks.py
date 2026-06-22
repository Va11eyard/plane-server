# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import json

from django.core.management.base import BaseCommand, CommandError

from plane.db.models import GitHubCommitImportLog, GitHubRepoSync, User
from plane.utils.github_commit_import_service import import_commit_plan, validate_plan
from plane.utils.github_sync_orchestrator import execute_import_log, scan_all_repos, scan_repo_sync, set_last_imported_sha


class Command(BaseCommand):
    help = "Scan GitHub repos for new commits and import task trees into Plane"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Scan and show previews only")
        parser.add_argument("--yes", action="store_true", help="Import without confirmation")
        parser.add_argument("--repo", help="Owner/name e.g. Va11eyard/ODOS")
        parser.add_argument("--actor", default="admin@pro-ecta.kz")
        parser.add_argument("--set-last-sha", help="Update last imported SHA without importing")
        parser.add_argument("--sha", help="Import specific commit SHA")
        parser.add_argument("--plan", help="Path to plan JSON file (with --sha)")

    def handle(self, *args, **options):
        actor = User.objects.filter(email=options["actor"]).first()
        if not actor:
            raise CommandError(f"Actor {options['actor']} not found")

        if options["set_last_sha"]:
            self._set_last_sha(options)
            return

        if options["sha"]:
            self._import_from_plan_file(options, actor)
            return

        if options["repo"]:
            owner, name = options["repo"].split("/", 1)
            repo_sync = GitHubRepoSync.objects.filter(repo_owner=owner, repo_name=name, enabled=True).first()
            if not repo_sync:
                raise CommandError(f"Sync config not found for {options['repo']}")
            results = [scan_repo_sync(repo_sync, actor, GitHubCommitImportLog.TriggerSource.CLI)]
        else:
            results = scan_all_repos(actor, GitHubCommitImportLog.TriggerSource.CLI)

        any_preview = False
        for result in results:
            if result.error:
                self.stdout.write(self.style.ERROR(f"{result.repo_sync.full_name}: {result.error}"))
                continue
            if not result.previews:
                self.stdout.write(self.style.WARNING(f"{result.repo_sync.full_name}: нет новых коммитов"))
                continue
            for preview in result.previews:
                any_preview = True
                self.stdout.write(
                    f"\n{preview.repo_label} {preview.short_sha}: {preview.message}\n"
                    f"  {preview.section_count} секций, {preview.task_count} задач"
                )
                if options["dry_run"]:
                    self.stdout.write(json.dumps(preview.plan, ensure_ascii=False, indent=2)[:2000])

        if options["dry_run"] or not any_preview:
            return

        if not options["yes"]:
            confirm = input("Импортировать все найденные коммиты? [y/N]: ").strip().lower()
            if confirm != "y":
                self.stdout.write("Отменено")
                return

        for result in results:
            for preview in result.previews:
                if not preview.log_id:
                    continue
                ok, msg = execute_import_log(preview.log_id, actor)
                if ok:
                    self.stdout.write(self.style.SUCCESS(f"{preview.short_sha}: {msg}"))
                else:
                    self.stdout.write(self.style.ERROR(f"{preview.short_sha}: {msg}"))

    def _set_last_sha(self, options):
        repo = options["repo"]
        if not repo:
            raise CommandError("--repo required with --set-last-sha")
        owner, name = repo.split("/", 1)
        repo_sync = GitHubRepoSync.objects.filter(repo_owner=owner, repo_name=name).first()
        if not repo_sync:
            raise CommandError(f"Sync not found: {repo}")
        set_last_imported_sha(repo_sync, options["set_last_sha"])
        self.stdout.write(self.style.SUCCESS(f"last_imported_sha = {options['set_last_sha'][:12]}…"))

    def _import_from_plan_file(self, options, actor):
        if not options["plan"]:
            raise CommandError("--plan required with --sha")
        repo = options["repo"]
        if not repo:
            raise CommandError("--repo required with --sha")
        owner, name = repo.split("/", 1)
        repo_sync = GitHubRepoSync.objects.filter(repo_owner=owner, repo_name=name).first()
        if not repo_sync:
            raise CommandError(f"Sync not found: {repo}")

        with open(options["plan"], encoding="utf-8") as f:
            raw = json.load(f)
        plan, error = validate_plan(raw)
        if error:
            raise CommandError(error)

        epic, count, error = import_commit_plan(
            repo_sync=repo_sync,
            sha=options["sha"],
            plan=plan or {},
            actor=actor,
        )
        if error:
            raise CommandError(error)
        self.stdout.write(self.style.SUCCESS(f"Imported {count} tasks, epic {epic.name if epic else '—'}"))
