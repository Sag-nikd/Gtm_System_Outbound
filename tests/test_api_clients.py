"""
Tests for Stories 2.1-2.4: Apollo API client, ZeroBounce API client,
per-integration mock/live toggle, HubSpot batch API.
"""
from __future__ import annotations

import pytest
import requests


# ── Story 2.1: Apollo API client ──────────────────────────────────────────────

class TestApolloAPIClient:
    def _make_client(self):
        from src.integrations.apollo.api_client import ApolloAPIClient
        return ApolloAPIClient(api_key="test-key")

    def test_get_companies_calls_apollo_endpoint(self, monkeypatch):
        client = self._make_client()
        called = {}

        def fake_post(url, **kwargs):
            called["url"] = url
            called["payload"] = kwargs.get("json", {})

            class FakeResp:
                ok = True
                status_code = 200
                def raise_for_status(self): pass
                def json(self): return {"accounts": [
                    {"id": "org1", "name": "Acme Corp", "industry": "B2B Technology",
                     "estimated_num_employees": 500, "website_url": "https://acme.com"}
                ]}
            return FakeResp()

        monkeypatch.setattr(requests, "post", fake_post)
        result = client.get_companies("")
        assert "apollo.io" in called["url"]
        assert "mixed_companies" in called["url"]
        assert len(result) == 1
        assert result[0]["company_name"] == "Acme Corp"
        assert result[0]["employee_count"] == 500

    def test_get_contacts_calls_apollo_endpoint(self, monkeypatch):
        client = self._make_client()
        called = {}

        def fake_post(url, **kwargs):
            called["url"] = url

            class FakeResp:
                ok = True
                status_code = 200
                def raise_for_status(self): pass
                def json(self): return {"people": [
                    {"id": "p1", "first_name": "Alice", "last_name": "Chen",
                     "email": "alice@acme.com", "title": "VP Sales",
                     "linkedin_url": "https://linkedin.com/in/alice",
                     "organization": {"id": "org1", "name": "Acme Corp"}}
                ]}
            return FakeResp()

        monkeypatch.setattr(requests, "post", fake_post)
        result = client.get_contacts("")
        assert "mixed_people" in called["url"]
        assert len(result) == 1
        assert result[0]["first_name"] == "Alice"
        assert result[0]["email"] == "alice@acme.com"

    def test_map_company_handles_missing_fields(self):
        client = self._make_client()
        result = client._map_company({})
        assert result["employee_count"] == 0
        assert result["tech_stack_signal"] == "Unknown"
        assert result["primary_volume_metric"] == 0

    def test_map_contact_handles_missing_org(self):
        client = self._make_client()
        result = client._map_contact({"first_name": "Bob", "email": "bob@example.com"})
        assert result["first_name"] == "Bob"
        assert result["company_id"] == ""


# ── Story 2.2: ZeroBounce API client ─────────────────────────────────────────

class TestZeroBounceAPIClient:
    def _make_client(self):
        from src.integrations.zerobounce.api_client import ZeroBounceAPIClient
        return ZeroBounceAPIClient(api_key="test-key")

    def _fake_response(self, results):
        class FakeResp:
            ok = True
            status_code = 200
            def raise_for_status(self): pass
            def json(self): return {"email_batch": results}
        return FakeResp()

    def test_validate_contacts_calls_validatebatch(self, monkeypatch):
        client = self._make_client()
        called = {}

        def fake_post(url, **kwargs):
            called["url"] = url
            called["payload"] = kwargs.get("json", {})
            return self._fake_response([
                {"address": "alice@acme.com", "status": "valid"}
            ])

        monkeypatch.setattr(requests, "post", fake_post)
        contacts = [{"email": "alice@acme.com", "first_name": "Alice"}]
        result = client.validate_contacts(contacts)
        assert "zerobounce" in called["url"]
        assert "validatebatch" in called["url"]
        assert result[0]["zerobounce_status"] == "valid"
        assert result[0]["final_validation_status"] == "approved"

    def test_invalid_email_set_to_suppressed(self, monkeypatch):
        client = self._make_client()

        def fake_post(url, **kwargs):
            return self._fake_response([
                {"address": "bad@spam.com", "status": "spamtrap"}
            ])

        monkeypatch.setattr(requests, "post", fake_post)
        contacts = [{"email": "bad@spam.com"}]
        result = client.validate_contacts(contacts)
        assert result[0]["final_validation_status"] == "suppressed"

    def test_catch_all_mapped_to_risky(self, monkeypatch):
        client = self._make_client()

        def fake_post(url, **kwargs):
            return self._fake_response([
                {"address": "maybe@domain.com", "status": "catch-all"}
            ])

        monkeypatch.setattr(requests, "post", fake_post)
        contacts = [{"email": "maybe@domain.com"}]
        result = client.validate_contacts(contacts)
        assert result[0]["final_validation_status"] == "review"

    def test_empty_email_contacts_not_sent_to_api(self, monkeypatch):
        client = self._make_client()
        api_called = []

        def fake_post(url, **kwargs):
            api_called.append(url)
            return self._fake_response([])

        monkeypatch.setattr(requests, "post", fake_post)
        contacts = [{"email": ""}]
        result = client.validate_contacts(contacts)
        assert not api_called
        assert result[0]["zerobounce_status"] == "unknown"
        assert result[0]["final_validation_status"] == "suppressed"

    def test_batch_size_respected(self, monkeypatch):
        """101 contacts should trigger 2 batch API calls (100 + 1)."""
        from src.integrations.zerobounce.api_client import _BATCH_SIZE
        client = self._make_client()
        call_count = [0]

        def fake_post(url, **kwargs):
            call_count[0] += 1
            batch = kwargs.get("json", {}).get("email_batch", [])
            return self._fake_response(
                [{"address": item["email_address"], "status": "valid"} for item in batch]
            )

        monkeypatch.setattr(requests, "post", fake_post)
        contacts = [{"email": f"user{i}@example.com"} for i in range(_BATCH_SIZE + 1)]
        client.validate_contacts(contacts)
        assert call_count[0] == 2


# ── Story 2.3: Per-integration mock/live toggle ───────────────────────────────

class TestPerIntegrationToggle:
    def _make_settings(self, monkeypatch, **env_vars):
        from src.config.settings import Settings
        for k, v in env_vars.items():
            monkeypatch.setenv(k, v)
        for key in [
            "MOCK_MODE", "APOLLO_MODE", "CLAY_MODE", "HUBSPOT_MODE",
            "ZEROBOUNCE_MODE", "NEVERBOUNCE_MODE", "VALIDITY_MODE",
            "APOLLO_API_KEY", "CLAY_API_KEY", "HUBSPOT_PRIVATE_APP_TOKEN",
            "ZEROBOUNCE_API_KEY", "NEVERBOUNCE_API_KEY", "VALIDITY_API_KEY",
        ]:
            if key not in env_vars:
                monkeypatch.delenv(key, raising=False)
        return Settings()

    def test_global_mock_mode_sets_all_integrations_to_mock(self, monkeypatch):
        s = self._make_settings(monkeypatch, MOCK_MODE="true")
        assert s.APOLLO_MODE == "mock"
        assert s.ZEROBOUNCE_MODE == "mock"
        assert s.HUBSPOT_MODE == "mock"

    def test_global_live_mode_sets_all_integrations_to_live(self, monkeypatch):
        s = self._make_settings(
            monkeypatch,
            MOCK_MODE="false",
            APOLLO_API_KEY="k1", CLAY_API_KEY="k2", HUBSPOT_PRIVATE_APP_TOKEN="k3",
            ZEROBOUNCE_API_KEY="k4", NEVERBOUNCE_API_KEY="k5", VALIDITY_API_KEY="k6",
        )
        assert s.APOLLO_MODE == "live"
        assert s.ZEROBOUNCE_MODE == "live"

    def test_per_integration_override_in_mock_mode(self, monkeypatch):
        """APOLLO_MODE=live overrides global MOCK_MODE=true."""
        with pytest.raises(EnvironmentError):
            self._make_settings(monkeypatch, MOCK_MODE="true", APOLLO_MODE="live")

    def test_per_integration_override_in_live_mode(self, monkeypatch):
        """APOLLO_MODE=mock means Apollo key is not required even in global live mode."""
        # Only APOLLO_MODE=mock, rest are live with keys provided
        s = self._make_settings(
            monkeypatch,
            MOCK_MODE="false",
            APOLLO_MODE="mock",
            CLAY_API_KEY="k2", HUBSPOT_PRIVATE_APP_TOKEN="k3",
            ZEROBOUNCE_API_KEY="k4", NEVERBOUNCE_API_KEY="k5", VALIDITY_API_KEY="k6",
        )
        assert s.APOLLO_MODE == "mock"
        assert s.CLAY_MODE == "live"

    def test_settings_has_mode_attributes(self, monkeypatch):
        s = self._make_settings(monkeypatch, MOCK_MODE="true")
        for attr in ["APOLLO_MODE", "CLAY_MODE", "HUBSPOT_MODE",
                     "ZEROBOUNCE_MODE", "NEVERBOUNCE_MODE", "VALIDITY_MODE"]:
            assert hasattr(s, attr)


# ── Story 2.4: HubSpot batch API ─────────────────────────────────────────────

class TestHubSpotBatchAPI:
    def _make_client(self, token="test-token"):
        from src.integrations.hubspot.api_client import HubSpotAPIClient
        return HubSpotAPIClient(token=token)

    def _ok_response(self, results):
        class FakeResp:
            ok = True
            status_code = 200
            def raise_for_status(self): pass
            def json(self): return {"results": results}
        return FakeResp()

    def test_upsert_companies_uses_batch_create(self, monkeypatch):
        client = self._make_client()
        calls = []

        def fake_post(url, **kwargs):
            calls.append(url)
            if "search" in url:
                return _search_empty()
            return self._ok_response([{"id": "hs1"}])

        def _search_empty():
            class R:
                ok = True
                status_code = 200
                def raise_for_status(self): pass
                def json(self): return {"results": []}
            return R()

        monkeypatch.setattr(requests, "post", fake_post)
        companies = [{"company_id": "C001", "company_name": "Acme", "website": "acme.com",
                      "industry": "B2B Technology", "employee_count": 100,
                      "icp_tier": "Tier 1", "icp_score": 82}]
        client.upsert_companies(companies)
        batch_calls = [u for u in calls if "batch/create" in u]
        assert batch_calls, "Expected at least one batch/create call"

    def test_hubspot_sync_client_has_batch_methods(self):
        from src.crm.hubspot.sync import HubSpotSyncClient
        assert hasattr(HubSpotSyncClient, "batch_upsert_companies")
        assert hasattr(HubSpotSyncClient, "batch_upsert_contacts")

    def test_batch_upsert_companies_returns_id_map(self, monkeypatch):
        from src.crm.hubspot.sync import HubSpotSyncClient

        def fake_post(self_inner, path, payload):
            if "search" in path:
                return {"results": []}
            return {"results": [{"id": "hs-new"}]}

        monkeypatch.setattr(HubSpotSyncClient, "_post", fake_post)
        client = HubSpotSyncClient.__new__(HubSpotSyncClient)
        client._headers = {}

        companies = [{"company_id": "C001", "company_name": "Test Co",
                      "website": "testco.com", "industry": "Retail",
                      "employee_count": 50, "icp_tier": "Tier 2", "icp_score": 65}]
        result = client.batch_upsert_companies(companies)
        assert isinstance(result, dict)
