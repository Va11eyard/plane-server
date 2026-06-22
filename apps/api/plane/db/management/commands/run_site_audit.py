# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from django.core.management.base import BaseCommand, CommandError

from plane.db.models import MonitorRun, User
from plane.utils.site_audit.orchestrator import build_telegram_messages, run_site_audit, send_audit_to_telegram
from plane.utils.site_audit.permissions import can_run_site_audit


class Command(BaseCommand):
    help = "Run site audit probes and optionally send Telegram report"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Run without saving or sending Telegram")
        parser.add_argument("--fast", action="store_true", help="SSL/HTTP only, skip SSH")
        parser.add_argument("--site", help="Monitor slug e.g. odos")
        parser.add_argument("--send", action="store_true", help="Send report to Telegram")
        parser.add_argument("--actor", default="dimash@galamat.com")

    def handle(self, *args, **options):
        actor = User.objects.filter(email=options["actor"]).first()
        if not actor:
            raise CommandError(f"User {options['actor']} not found")
        if not can_run_site_audit(actor):
            raise CommandError(f"{options['actor']} cannot run site audit")

        audit = run_site_audit(
            trigger=MonitorRun.Trigger.MANUAL,
            fast_only=options["fast"],
            site_slug=options.get("site"),
            persist=not options["dry_run"],
            send_alerts=not options["dry_run"],
        )

        for site_name, site_results in audit.results_by_site.items():
            self.stdout.write(f"\n{site_name}:")
            for r in site_results:
                self.stdout.write(f"  [{r.status}] {r.check_type}: {r.message}")

        self.stdout.write(
            f"\nSummary: ok={audit.ok_count} warn={audit.warn_count} "
            f"critical={audit.critical_count} error={audit.error_count} ({audit.duration_ms}ms)"
        )

        if options["dry_run"]:
            messages = build_telegram_messages(audit, "dry-run")
            for msg in messages:
                self.stdout.write("\n--- Telegram preview ---\n" + msg[:2000])
            return

        if options["send"]:
            messages = build_telegram_messages(audit, "ручной")
            send_audit_to_telegram(messages, alerts=audit.alerts)
