"""Story 14: Verify expanded mock data edge cases are handled gracefully."""
from __future__ import annotations

import json
import os

import pytest

from src.config.settings import settings


def _load_json(filename: str) -> list:
    path = os.path.join(settings.DATA_DIR, filename)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ── Company edge cases ────────────────────────────────────────────────────────

def test_companies_file_has_at_least_15_entries():
    companies = _load_json("fake_companies.json")
    assert len(companies) >= 15


def test_companies_file_contains_duplicate_company_id():
    companies = _load_json("fake_companies.json")
    ids = [c["company_id"] for c in companies]
    duplicated = [cid for cid in set(ids) if ids.count(cid) > 1]
    assert duplicated, "Expected at least one duplicate company_id for dedup testing"


def test_companies_file_has_zero_employee_count_entry():
    companies = _load_json("fake_companies.json")
    assert any(c.get("employee_count") == 0 for c in companies)


def test_companies_file_has_empty_tech_stack_signal():
    companies = _load_json("fake_companies.json")
    assert any(c.get("tech_stack_signal") == "" for c in companies)


def test_companies_file_has_unknown_industry():
    from src.scoring.icp_scoring import load_icp_rules
    icp_rules = load_icp_rules(os.path.join(settings.CONFIG_DIR, "icp_rules.json"))
    known = set(icp_rules.get("industry_scores", {}).keys()) - {"default"}
    companies = _load_json("fake_companies.json")
    assert any(c.get("industry") not in known for c in companies)


def test_companies_file_has_long_name_entry():
    companies = _load_json("fake_companies.json")
    assert any(len(c.get("company_name", "")) > 100 for c in companies)


def test_ingestion_deduplicates_companies_in_fake_file(tmp_path):
    """After dedup, unique company_ids are fewer than total raw entries."""
    from src.ingestion.company_ingestion import load_companies

    companies = _load_json("fake_companies.json")
    raw_count = len(companies)
    duplicate_ids = sum(
        1 for cid in set(c["company_id"] for c in companies)
        if sum(1 for c in companies if c["company_id"] == cid) > 1
    )
    result = load_companies(os.path.join(settings.DATA_DIR, "fake_companies.json"))
    assert len(result) == raw_count - duplicate_ids


# ── Contact edge cases ────────────────────────────────────────────────────────

def test_contacts_file_has_at_least_20_entries():
    contacts = _load_json("fake_contacts.json")
    assert len(contacts) >= 20


def test_contacts_file_has_empty_email_entry():
    contacts = _load_json("fake_contacts.json")
    assert any(c.get("email") == "" for c in contacts)


def test_contacts_file_has_duplicate_email_entry():
    contacts = _load_json("fake_contacts.json")
    emails = [c["email"] for c in contacts if c.get("email")]
    duplicated = [e for e in set(emails) if emails.count(e) > 1]
    assert duplicated, "Expected at least one duplicate email for dedup testing"


def test_contacts_file_has_unknown_persona():
    from src.outreach.sequence_export import EMAIL_ANGLES
    contacts = _load_json("fake_contacts.json")
    assert any(c.get("persona_type") not in EMAIL_ANGLES for c in contacts)


def test_contacts_file_has_unicode_name():
    contacts = _load_json("fake_contacts.json")
    has_unicode = any(
        any(ord(ch) > 127 for ch in (c.get("first_name", "") + c.get("last_name", "")))
        for c in contacts
    )
    assert has_unicode, "Expected at least one contact with Unicode characters in name"


def test_contacts_file_has_orphan_contact():
    """At least one contact has a company_id not present in any company."""
    contacts = _load_json("fake_contacts.json")
    companies = _load_json("fake_companies.json")
    company_ids = {c["company_id"] for c in companies}
    orphans = [ct for ct in contacts if ct.get("company_id") not in company_ids]
    assert orphans, "Expected at least one orphan contact (company_id not in companies)"


def test_ingestion_deduplicates_contacts_by_email():
    """load_contacts keeps empty-email contacts but skips duplicate non-empty emails."""
    from src.validation.email_validation_mock import load_contacts

    contacts = _load_json("fake_contacts.json")
    empty_email_count = sum(1 for c in contacts if not c.get("email"))
    non_empty_emails = [c["email"] for c in contacts if c.get("email")]
    unique_non_empty = len(set(non_empty_emails))
    # empty-email contacts are included; duplicate non-empty emails are deduplicated
    expected_count = empty_email_count + unique_non_empty

    result = load_contacts(os.path.join(settings.DATA_DIR, "fake_contacts.json"))
    assert len(result) == expected_count


# ── Campaign metrics edge cases ───────────────────────────────────────────────

def test_campaign_metrics_file_has_at_least_6_entries():
    metrics = _load_json("fake_campaign_metrics.json")
    assert len(metrics) >= 6


def test_campaign_metrics_has_zero_emails_sent_entry():
    metrics = _load_json("fake_campaign_metrics.json")
    assert any(m.get("emails_sent") == 0 for m in metrics)


def test_campaign_metrics_has_zero_domain_health_score():
    metrics = _load_json("fake_campaign_metrics.json")
    assert any(m.get("domain_health_score") == 0 for m in metrics)


def test_pipeline_handles_all_edge_case_companies_without_crash(tmp_path, monkeypatch):
    """Full pipeline smoke test with expanded data — must not raise."""
    monkeypatch.setattr(settings, "OUTPUT_DIR", str(tmp_path))
    from src.main import main
    main()
    assert os.path.exists(os.path.join(str(tmp_path), "run_manifest.json"))
