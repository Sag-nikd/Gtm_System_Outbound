"""
Tests for Stories 4.1-4.5: outreach enrollment, dashboard, Docker files,
Salesforce live mode, NeverBounce validator.
"""
from __future__ import annotations

import os
import pytest
import requests


# ── Story 4.1: Outreach enrollment API ───────────────────────────────────────

class TestOutreachEnrollment:
    def test_mock_client_enrolls_approved_contacts(self):
        from src.outreach.enrollment import MockEnrollmentClient
        client = MockEnrollmentClient()
        contacts = [
            {"email": "a@x.com", "final_validation_status": "approved"},
            {"email": "b@x.com", "final_validation_status": "suppressed"},
        ]
        result = client.enroll_contacts(contacts, seq_id="seq-001")
        approved = [c for c in result if c.get("sequence_enrolled")]
        assert len(approved) == 1
        assert approved[0]["email"] == "a@x.com"

    def test_mock_client_sets_sequence_id(self):
        from src.outreach.enrollment import MockEnrollmentClient
        client = MockEnrollmentClient()
        contacts = [{"email": "a@x.com", "final_validation_status": "approved"}]
        result = client.enroll_contacts(contacts, seq_id="seq-xyz")
        assert result[0]["sequence_id"] == "seq-xyz"

    def test_apollo_client_calls_enrollment_endpoint(self, monkeypatch):
        from src.outreach.enrollment import ApolloSequenceClient
        client = ApolloSequenceClient(api_key="test-key")
        calls = []

        def fake_post(url, **kwargs):
            calls.append(url)
            class R:
                ok = True
                status_code = 200
                def raise_for_status(self): pass
                def json(self): return {"status": "success"}
            return R()

        monkeypatch.setattr(requests, "post", fake_post)
        contacts = [{"email": "a@x.com", "final_validation_status": "approved",
                     "first_name": "Alice", "last_name": "Chen"}]
        result = client.enroll_contacts(contacts, seq_id="seq-001")
        assert calls
        assert result[0].get("sequence_enrolled") is True

    def test_get_enrollment_client_returns_mock_by_default(self):
        from src.outreach.enrollment import get_enrollment_client, MockEnrollmentClient
        client = get_enrollment_client()
        assert isinstance(client, MockEnrollmentClient)

    def test_get_enrollment_client_returns_apollo_when_live(self):
        from src.outreach.enrollment import get_enrollment_client, ApolloSequenceClient
        client = get_enrollment_client(api_key="key", mock=False)
        assert isinstance(client, ApolloSequenceClient)

    def test_enrollment_base_is_abstract(self):
        from src.outreach.enrollment import EnrollmentBase
        with pytest.raises(TypeError):
            EnrollmentBase()

    # Allow keyword arg or positional for seq_id
    def test_mock_client_no_approved_contacts(self):
        from src.outreach.enrollment import MockEnrollmentClient
        client = MockEnrollmentClient()
        contacts = [{"email": "a@x.com", "final_validation_status": "suppressed"}]
        result = client.enroll_contacts(contacts, seq_id="seq-001")
        assert not any(c.get("sequence_enrolled") for c in result)


# ── Story 4.2: Pipeline health dashboard ─────────────────────────────────────

class TestDashboard:
    def test_get_pipeline_summary_with_no_files(self, tmp_path):
        from src.monitoring.dashboard import get_pipeline_summary
        summary = get_pipeline_summary(str(tmp_path))
        assert summary["overall_health"] == "unknown"
        assert summary["total_companies"] == 0

    def test_get_pipeline_summary_reads_manifest(self, tmp_path):
        import json
        from src.monitoring.dashboard import get_pipeline_summary
        manifest = {
            "run_id": "abc-123",
            "started_at": "2026-04-29T08:00:00Z",
            "completed_at": "2026-04-29T08:01:00Z",
            "mock_mode": True,
            "stages": [
                {"name": "company_pipeline", "record_count": 12, "status": "completed"},
                {"name": "contact_pipeline", "record_count": 22, "status": "completed"},
            ],
            "config_hash": "abc123",
        }
        (tmp_path / "run_manifest.json").write_text(json.dumps(manifest))
        summary = get_pipeline_summary(str(tmp_path))
        assert summary["run_id"] == "abc-123"
        assert summary["total_companies"] == 12
        assert summary["total_contacts"] == 22

    def test_print_dashboard_does_not_raise(self, tmp_path, capsys):
        from src.monitoring.dashboard import print_dashboard
        print_dashboard(str(tmp_path))
        output = capsys.readouterr().out
        assert "DASHBOARD" in output

    def test_overall_health_critical_when_any_critical_campaign(self, tmp_path):
        import json, csv
        from src.monitoring.dashboard import get_pipeline_summary
        rows = [{"campaign_name": "A", "health_status": "critical", "primary_issue": "spam"}]
        path = tmp_path / "11_campaign_health_report.csv"
        with open(path, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        summary = get_pipeline_summary(str(tmp_path))
        assert summary["overall_health"] == "critical"


# ── Story 4.3: Dockerize ─────────────────────────────────────────────────────

class TestDockerFiles:
    def _project_root(self):
        # Navigate from tests/ up to project root
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    def test_dockerfile_exists(self):
        assert os.path.exists(os.path.join(self._project_root(), "Dockerfile"))

    def test_dockerfile_uses_python_311(self):
        with open(os.path.join(self._project_root(), "Dockerfile")) as f:
            content = f.read()
        assert "python:3.11" in content

    def test_docker_compose_exists(self):
        assert os.path.exists(os.path.join(self._project_root(), "docker-compose.yml"))

    def test_docker_compose_has_pipeline_service(self):
        import yaml
        with open(os.path.join(self._project_root(), "docker-compose.yml")) as f:
            compose = yaml.safe_load(f)
        assert "pipeline" in compose.get("services", {})

    def test_docker_compose_has_db_service(self):
        import yaml
        with open(os.path.join(self._project_root(), "docker-compose.yml")) as f:
            compose = yaml.safe_load(f)
        assert "db" in compose.get("services", {})


# ── Story 4.4: Salesforce live mode ──────────────────────────────────────────

class TestSalesforceClient:
    def _make_client(self):
        from src.crm.salesforce.client import SalesforceClient
        return SalesforceClient(
            client_id="cid", client_secret="csec",
            username="user@sf.com", password="pass",
            security_token="tok", instance_url="https://test.salesforce.com",
        )

    def test_authenticate_posts_to_oauth_endpoint(self, monkeypatch):
        client = self._make_client()
        called = {}

        def fake_post(url, **kwargs):
            called["url"] = url
            called["data"] = kwargs.get("data", {})
            class R:
                ok = True
                status_code = 200
                def raise_for_status(self): pass
                def json(self): return {"access_token": "tok123"}
            return R()

        monkeypatch.setattr(requests, "post", fake_post)
        result = client.authenticate()
        assert result is True
        assert "oauth2/token" in called["url"]
        assert called["data"]["grant_type"] == "password"
        assert client._access_token == "tok123"

    def test_get_object_fields_requires_authentication(self):
        client = self._make_client()
        with pytest.raises(RuntimeError, match="authenticate"):
            client.get_object_fields("Account")

    def test_get_object_fields_calls_describe_endpoint(self, monkeypatch):
        client = self._make_client()
        client._access_token = "tok123"
        called = {}

        def fake_get(url, **kwargs):
            called["url"] = url
            class R:
                ok = True
                status_code = 200
                def raise_for_status(self): pass
                def json(self): return {"fields": [{"name": "Id"}, {"name": "Name"}]}
            return R()

        monkeypatch.setattr(requests, "get", fake_get)
        fields = client.get_object_fields("Account")
        assert "describe" in called["url"]
        assert len(fields) == 2

    def test_upsert_account_patches_to_correct_url(self, monkeypatch):
        client = self._make_client()
        client._access_token = "tok123"
        called = {}

        def fake_patch(url, **kwargs):
            called["url"] = url
            class R:
                ok = True
                status_code = 200
                def raise_for_status(self): pass
                def json(self): return {"id": "acc001"}
            return R()

        monkeypatch.setattr(requests, "patch", fake_patch)
        result = client.upsert_account("GTM_Company_ID__c", "C001", {"Name": "Acme"})
        assert "Account/GTM_Company_ID__c/C001" in called["url"]
        assert result == "acc001"


# ── Story 4.5: NeverBounce second-pass validator ──────────────────────────────

class TestNeverBounceAPIClient:
    def _make_client(self):
        from src.integrations.neverbounce.api_client import NeverBounceAPIClient
        return NeverBounceAPIClient(api_key="nb-test-key")

    def _fake_get(self, status):
        def fake(url, **kwargs):
            class R:
                ok = True
                status_code = 200
                def raise_for_status(self): pass
                def json(self): return {"result": status}
            return R()
        return fake

    def test_valid_email_remains_approved(self, monkeypatch):
        client = self._make_client()
        monkeypatch.setattr(requests, "get", self._fake_get("valid"))
        contacts = [{"email": "a@x.com", "final_validation_status": "approved"}]
        result = client.validate_contacts(contacts)
        assert result[0]["neverbounce_status"] == "valid"
        assert result[0]["final_validation_status"] == "approved"

    def test_invalid_email_overrides_approved_status(self, monkeypatch):
        client = self._make_client()
        monkeypatch.setattr(requests, "get", self._fake_get("invalid"))
        contacts = [{"email": "a@x.com", "final_validation_status": "approved"}]
        result = client.validate_contacts(contacts)
        assert result[0]["final_validation_status"] == "suppressed"

    def test_catchall_maps_to_risky(self, monkeypatch):
        client = self._make_client()
        monkeypatch.setattr(requests, "get", self._fake_get("catchall"))
        contacts = [{"email": "a@domain.com", "final_validation_status": "suppressed"}]
        result = client.validate_contacts(contacts)
        assert result[0]["neverbounce_status"] == "risky"

    def test_api_failure_falls_back_to_unknown(self, monkeypatch):
        client = self._make_client()

        def fail(*args, **kwargs):
            raise requests.RequestException("timeout")

        monkeypatch.setattr(requests, "get", fail)
        contacts = [{"email": "a@x.com", "final_validation_status": "approved"}]
        result = client.validate_contacts(contacts)
        assert result[0]["neverbounce_status"] == "unknown"
        assert result[0]["final_validation_status"] == "approved"

    def test_empty_email_skipped(self, monkeypatch):
        client = self._make_client()
        api_called = []
        monkeypatch.setattr(requests, "get", lambda *a, **k: api_called.append(1) or (_ for _ in ()).throw(AssertionError("should not call")))
        contacts = [{"email": ""}]
        result = client.validate_contacts(contacts)
        assert not api_called
        assert result[0]["email"] == ""

    def test_calls_single_check_endpoint(self, monkeypatch):
        client = self._make_client()
        urls = []

        def fake_get(url, **kwargs):
            urls.append(url)
            class R:
                ok = True
                status_code = 200
                def raise_for_status(self): pass
                def json(self): return {"result": "valid"}
            return R()

        monkeypatch.setattr(requests, "get", fake_get)
        client.validate_contacts([{"email": "test@example.com", "final_validation_status": "approved"}])
        assert any("single/check" in u for u in urls)
