"""Tests that ingestion, contact-load, and campaign-load enforce Pydantic schemas."""
from __future__ import annotations

import json
import os
import tempfile

import pytest
from pydantic import ValidationError

from src.schemas.company import Company
from src.schemas.contact import Contact
from src.schemas.campaign import Campaign


# ── Schema unit tests ─────────────────────────────────────────────────────────

_VALID_COMPANY = {
    "company_id": "co_001",
    "company_name": "Acme Health",
    "website": "https://acmehealth.com",
    "domain": "acmehealth.com",
    "industry": "Managed Care",
    "employee_count": 500,
    "revenue_range": "$50M-$100M",
    "state": "Texas",
    "primary_volume_metric": 100000,
    "secondary_volume_metric": 50000,
    "growth_signal": True,
    "hiring_signal": False,
    "tech_stack_signal": "Salesforce",
    "ingestion_source": "fake_data",
    "ingestion_status": "ingested",
}

_VALID_CONTACT = {
    "contact_id": "ct_001",
    "company_id": "co_001",
    "first_name": "Alice",
    "last_name": "Smith",
    "title": "VP Member Engagement",
    "email": "alice@acmehealth.com",
    "linkedin_url": "https://linkedin.com/in/alicesmith",
    "persona_type": "VP Member Engagement",
}

_VALID_CAMPAIGN = {
    "campaign_name": "Q1 Outbound",
    "emails_sent": 500,
    "open_rate": 0.35,
    "reply_rate": 0.04,
    "bounce_rate": 0.01,
    "spam_rate": 0.001,
    "domain_health_score": 85.0,
}


def test_valid_company_passes():
    co = Company(**_VALID_COMPANY)
    assert co.company_id == "co_001"


def test_company_missing_company_id_raises():
    bad = {k: v for k, v in _VALID_COMPANY.items() if k != "company_id"}
    with pytest.raises(ValidationError):
        Company(**bad)


def test_company_employee_count_wrong_type_raises():
    bad = {**_VALID_COMPANY, "employee_count": "not_a_number"}
    with pytest.raises(ValidationError):
        Company(**bad)


def test_valid_contact_passes():
    ct = Contact(**_VALID_CONTACT)
    assert ct.contact_id == "ct_001"


def test_contact_missing_email_raises():
    bad = {k: v for k, v in _VALID_CONTACT.items() if k != "email"}
    with pytest.raises(ValidationError):
        Contact(**bad)


def test_contact_missing_contact_id_raises():
    bad = {k: v for k, v in _VALID_CONTACT.items() if k != "contact_id"}
    with pytest.raises(ValidationError):
        Contact(**bad)


def test_valid_campaign_passes():
    c = Campaign(**_VALID_CAMPAIGN)
    assert c.campaign_name == "Q1 Outbound"


def test_campaign_missing_campaign_name_raises():
    bad = {k: v for k, v in _VALID_CAMPAIGN.items() if k != "campaign_name"}
    with pytest.raises(ValidationError):
        Campaign(**bad)


# ── Ingestion boundary validation ─────────────────────────────────────────────

def test_load_companies_skips_invalid_records(tmp_path):
    """Records missing required fields are skipped at ingestion."""
    from src.ingestion.company_ingestion import load_companies

    data = [
        _VALID_COMPANY,
        {"company_id": "bad_001", "company_name": "Missing Fields"},  # missing required fields
    ]
    f = tmp_path / "cos.json"
    f.write_text(json.dumps(data))
    result = load_companies(str(f))
    assert len(result) == 1
    assert result[0]["company_id"] == "co_001"


def test_load_companies_skips_type_invalid_records(tmp_path):
    """Records with wrong types are skipped at ingestion."""
    from src.ingestion.company_ingestion import load_companies

    bad = {**_VALID_COMPANY, "employee_count": "not_a_number", "company_id": "bad_002"}
    data = [_VALID_COMPANY, bad]
    f = tmp_path / "cos2.json"
    f.write_text(json.dumps(data))
    result = load_companies(str(f))
    assert len(result) == 1
    assert result[0]["company_id"] == "co_001"


def test_load_contacts_skips_invalid_records(tmp_path):
    """Contact records missing required fields are skipped."""
    from src.validation.email_validation_mock import load_contacts

    bad = {"contact_id": "bad_ct", "first_name": "Nobody"}  # missing required fields
    data = [_VALID_CONTACT, bad]
    f = tmp_path / "cts.json"
    f.write_text(json.dumps(data))
    result = load_contacts(str(f))
    assert len(result) == 1
    assert result[0]["contact_id"] == "ct_001"
