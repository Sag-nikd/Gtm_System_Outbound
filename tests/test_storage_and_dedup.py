"""Tests for Stories 3.1 (SQLite storage) and 3.5 (cross-run deduplication)."""
from __future__ import annotations

import json
import os
import pytest


# ── Story 3.1: SQLite storage layer ──────────────────────────────────────────

class TestSQLiteBackend:
    @pytest.fixture
    def db(self, tmp_path):
        from src.storage.sqlite_backend import SQLiteBackend
        return SQLiteBackend(str(tmp_path / "test.db"))

    def test_save_and_retrieve_pipeline_run(self, db):
        run_id = "run-001"
        db.save_pipeline_run({
            "run_id": run_id,
            "started_at": "2026-04-29T08:00:00Z",
            "status": "running",
            "company_count": 10,
            "contact_count": 20,
        })
        result = db.get_run(run_id)
        assert result is not None
        assert result["run_id"] == run_id
        assert result["status"] == "running"

    def test_update_pipeline_run(self, db):
        db.save_pipeline_run({"run_id": "r1", "started_at": "2026-01-01T00:00:00Z", "status": "running"})
        db.update_pipeline_run("r1", {"status": "completed", "company_count": 5})
        result = db.get_run("r1")
        assert result["status"] == "completed"
        assert result["company_count"] == 5

    def test_get_latest_run_returns_most_recent(self, db):
        db.save_pipeline_run({"run_id": "r1", "started_at": "2026-01-01T00:00:00Z", "status": "completed"})
        db.save_pipeline_run({"run_id": "r2", "started_at": "2026-01-02T00:00:00Z", "status": "completed"})
        latest = db.get_latest_run()
        assert latest["run_id"] == "r2"

    def test_get_latest_run_returns_none_when_empty(self, db):
        assert db.get_latest_run() is None

    def test_get_nonexistent_run_returns_none(self, db):
        assert db.get_run("does-not-exist") is None

    def test_save_companies_stores_records(self, db):
        db.save_pipeline_run({"run_id": "r1", "started_at": "2026-01-01T00:00:00Z", "status": "running"})
        companies = [
            {"company_id": "C001", "company_name": "Acme", "industry": "B2B Technology",
             "icp_tier": "Tier 1", "icp_score": 82.5},
            {"company_id": "C002", "company_name": "Beta", "industry": "E-commerce",
             "icp_tier": "Tier 2", "icp_score": 70.0},
        ]
        db.save_companies(companies, "r1")
        with db._conn() as conn:
            rows = conn.execute("SELECT * FROM companies WHERE run_id = 'r1'").fetchall()
        assert len(rows) == 2

    def test_save_contacts_stores_records(self, db):
        db.save_pipeline_run({"run_id": "r1", "started_at": "2026-01-01T00:00:00Z", "status": "running"})
        contacts = [
            {"contact_id": "K001", "company_id": "C001", "email": "a@example.com",
             "persona_type": "VP Sales", "final_validation_status": "approved"},
        ]
        db.save_contacts(contacts, "r1")
        with db._conn() as conn:
            rows = conn.execute("SELECT * FROM contacts WHERE run_id = 'r1'").fetchall()
        assert len(rows) == 1

    def test_save_campaign_health(self, db):
        db.save_pipeline_run({"run_id": "r1", "started_at": "2026-01-01T00:00:00Z", "status": "running"})
        metrics = [{"campaign_name": "Test Campaign", "emails_sent": 100,
                    "open_rate": 0.4, "reply_rate": 0.05, "meetings_booked": 3,
                    "domain_health_score": 85}]
        db.save_campaign_health(metrics, "r1")
        with db._conn() as conn:
            rows = conn.execute("SELECT * FROM campaign_health WHERE run_id = 'r1'").fetchall()
        assert len(rows) == 1

    def test_storage_backend_is_abstract(self):
        from src.storage.base import StorageBackend
        with pytest.raises(TypeError):
            StorageBackend()

    def test_sqlite_backend_implements_interface(self):
        from src.storage.base import StorageBackend
        from src.storage.sqlite_backend import SQLiteBackend
        assert issubclass(SQLiteBackend, StorageBackend)


# ── Story 3.5: Cross-run deduplication ───────────────────────────────────────

class TestSyncHistory:
    def test_load_returns_empty_when_file_absent(self, tmp_path):
        from src.utils.sync_history import load_sync_history
        history = load_sync_history(str(tmp_path))
        assert history == {"synced_domains": {}, "synced_emails": {}}

    def test_save_and_load_roundtrip(self, tmp_path):
        from src.utils.sync_history import load_sync_history, save_sync_history
        history = {
            "synced_domains": {"acme.com": {"hubspot_id": "hs1", "icp_score": 82.5, "synced_at": "..."}},
            "synced_emails": {},
        }
        save_sync_history(history, str(tmp_path))
        loaded = load_sync_history(str(tmp_path))
        assert loaded["synced_domains"]["acme.com"]["hubspot_id"] == "hs1"

    def test_save_adds_last_updated(self, tmp_path):
        from src.utils.sync_history import load_sync_history, save_sync_history
        save_sync_history({"synced_domains": {}, "synced_emails": {}}, str(tmp_path))
        loaded = load_sync_history(str(tmp_path))
        assert "last_updated" in loaded

    def test_filter_new_companies_skips_unchanged(self, tmp_path):
        from src.utils.sync_history import filter_new_companies
        history = {
            "synced_domains": {"acme.com": {"icp_score": 82.5, "synced_at": "..."}}
        }
        companies = [
            {"domain": "acme.com", "icp_score": 82.5, "company_id": "C001"},
            {"domain": "beta.com", "icp_score": 70.0, "company_id": "C002"},
        ]
        new, skipped = filter_new_companies(companies, history)
        assert skipped == 1
        assert len(new) == 1
        assert new[0]["domain"] == "beta.com"

    def test_filter_new_companies_includes_changed_score(self, tmp_path):
        from src.utils.sync_history import filter_new_companies
        history = {
            "synced_domains": {"acme.com": {"icp_score": 75.0, "synced_at": "..."}}
        }
        companies = [{"domain": "acme.com", "icp_score": 82.5, "company_id": "C001"}]
        new, skipped = filter_new_companies(companies, history)
        assert skipped == 0
        assert len(new) == 1

    def test_filter_new_contacts_skips_synced_email(self):
        from src.utils.sync_history import filter_new_contacts
        history = {"synced_emails": {"alice@acme.com": {"synced_at": "..."}}}
        contacts = [
            {"email": "alice@acme.com", "contact_id": "K001"},
            {"email": "bob@acme.com", "contact_id": "K002"},
        ]
        new, skipped = filter_new_contacts(contacts, history)
        assert skipped == 1
        assert new[0]["email"] == "bob@acme.com"

    def test_filter_new_contacts_includes_empty_email(self):
        from src.utils.sync_history import filter_new_contacts
        history = {"synced_emails": {}}
        contacts = [{"email": "", "contact_id": "K016"}]
        new, skipped = filter_new_contacts(contacts, history)
        assert skipped == 0
        assert len(new) == 1

    def test_record_synced_companies_updates_history(self):
        from src.utils.sync_history import record_synced_companies
        history = {"synced_domains": {}}
        companies = [{"domain": "acme.com", "icp_score": 82.5, "icp_tier": "Tier 1",
                      "company_id": "C001"}]
        id_map = {"C001": "hs-123"}
        updated = record_synced_companies(companies, id_map, history)
        assert "acme.com" in updated["synced_domains"]
        assert updated["synced_domains"]["acme.com"]["hubspot_id"] == "hs-123"
        assert updated["synced_domains"]["acme.com"]["icp_score"] == 82.5

    def test_record_synced_contacts_updates_history(self):
        from src.utils.sync_history import record_synced_contacts
        history = {"synced_emails": {}}
        contacts = [{"email": "alice@acme.com", "hubspot_id": "hs-456"}]
        updated = record_synced_contacts(contacts, history)
        assert "alice@acme.com" in updated["synced_emails"]

    def test_filter_empty_companies_list(self):
        from src.utils.sync_history import filter_new_companies
        new, skipped = filter_new_companies([], {"synced_domains": {}})
        assert new == [] and skipped == 0
