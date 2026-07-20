# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from datetime import date, timedelta
from unittest.mock import Mock

import pytest

from plane.utils.site_audit.permissions import can_run_site_audit, get_site_audit_recipient_emails, probe_renewal_reminder
from plane.utils.site_audit.probe_ssl import probe_ssl_expiry
from plane.utils.site_audit.report_formatter import format_audit_report, format_alert_message
from plane.utils.site_audit.types import ProbeResult, STATUS_CRITICAL, STATUS_OK, STATUS_SKIPPED, STATUS_WARN
from plane.utils.telegram_site_audit_bot import is_audit_trigger


@pytest.mark.unit
class TestSiteAuditPermissions:
    def test_default_recipient(self):
        assert "dimash@galamat.com" in get_site_audit_recipient_emails()

    def test_can_run_only_recipient(self, monkeypatch):
        monkeypatch.delenv("SITE_AUDIT_RECIPIENT_EMAILS", raising=False)
        assert can_run_site_audit(Mock(email="dimash@galamat.com")) is True
        assert can_run_site_audit(Mock(email="admin@galamat.com")) is False


@pytest.mark.unit
class TestRenewalReminder:
    def test_domain_warn(self):
        renewal = date.today() + timedelta(days=10)
        results = probe_renewal_reminder(site_name="Test", domain_renewal_at=renewal, vps_renewal_at=None)
        assert results[0].status == STATUS_WARN

    def test_domain_ok(self):
        renewal = date.today() + timedelta(days=60)
        results = probe_renewal_reminder(site_name="Test", domain_renewal_at=renewal, vps_renewal_at=None)
        assert results[0].status == STATUS_OK


@pytest.mark.unit
class TestReportFormatter:
    def test_format_all_ok(self):
        results = {"ProEcta": [ProbeResult(check_type="https_reachable", status=STATUS_OK, message="OK")]}
        msgs = format_audit_report(
            results_by_site=results,
            trigger_label="test",
            ok_count=1,
            warn_count=0,
            critical_count=0,
            error_count=0,
            duration_ms=100,
        )
        assert "в норме" in msgs[0].lower() or "✅" in msgs[0]

    def test_format_alert(self):
        msg = format_alert_message(
            "ODOS",
            [ProbeResult(check_type="https_reachable", status=STATUS_CRITICAL, message="down")],
        )
        assert "ODOS" in msg
        assert "down" in msg


@pytest.mark.unit
class TestHttpEndpointProbe:
    def test_ok_status(self, monkeypatch):
        class Resp:
            status_code = 200

            def json(self):
                return {"status": "ok"}

        monkeypatch.setattr("plane.utils.site_audit.probe_http.requests.get", lambda *a, **k: Resp())
        from plane.utils.site_audit.probe_http import probe_configured_http

        result = probe_configured_http(
            {
                "name": "Health",
                "url": "https://example.com/healthz",
                "expect_status": 200,
                "expect_json": {"status": "ok"},
            }
        )
        assert result.status == STATUS_OK

    def test_wrong_status(self, monkeypatch):
        class Resp:
            status_code = 500

            def json(self):
                return {}

        monkeypatch.setattr("plane.utils.site_audit.probe_http.requests.get", lambda *a, **k: Resp())
        from plane.utils.site_audit.probe_http import probe_configured_http

        result = probe_configured_http({"name": "API", "url": "https://example.com", "expect_status": 200})
        assert result.status == STATUS_CRITICAL

    def test_accepts_status_list(self, monkeypatch):
        class Resp:
            status_code = 401

            def json(self):
                return {}

        monkeypatch.setattr("plane.utils.site_audit.probe_http.requests.get", lambda *a, **k: Resp())
        from plane.utils.site_audit.probe_http import probe_configured_http

        result = probe_configured_http(
            {"name": "Auth", "url": "https://example.com/me", "expect_status": [401, 403]}
        )
        assert result.status == STATUS_OK


@pytest.mark.unit
class TestSslProbe:
    def test_skipped_without_url(self):
        result = probe_ssl_expiry("")
        assert result.status == STATUS_SKIPPED


@pytest.mark.unit
class TestTelegramAudit:
    def test_is_audit_trigger(self):
        assert is_audit_trigger("🔍 Аудит сайтов")
        assert is_audit_trigger("/audit")
        assert not is_audit_trigger("новый отчёт")
