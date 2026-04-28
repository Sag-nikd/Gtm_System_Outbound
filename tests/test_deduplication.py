"""Tests that duplicate companies and contacts are removed at ingestion."""
from __future__ import annotations

import json
import pytest


_BASE_COMPANY = {
    "company_id": "co_001",
    "company_name": "Acme Health",
    "website": "https://acmehealth.com",
    "industry": "Managed Care",
    "employee_count": 500,
    "revenue_range": "$50M-$100M",
    "state": "Texas",
    "medicaid_members": 100000,
    "medicare_members": 50000,
    "growth_signal": True,
    "hiring_signal": False,
    "tech_stack_signal": "Salesforce",
}

_BASE_CONTACT = {
    "contact_id": "ct_001",
    "company_id": "co_001",
    "first_name": "Alice",
    "last_name": "Smith",
    "title": "VP Member Engagement",
    "email": "alice@acme.com",
    "linkedin_url": "https://linkedin.com/in/alice",
    "persona_type": "VP Member Engagement",
}


def test_load_companies_deduplicates_by_company_id(tmp_path):
    """Two companies with the same company_id → only the first is kept."""
    from src.ingestion.company_ingestion import load_companies

    data = [
        {**_BASE_COMPANY, "company_id": "co_001"},
        {**_BASE_COMPANY, "company_id": "co_002"},
        {**_BASE_COMPANY, "company_id": "co_001", "company_name": "Duplicate"},  # dup
    ]
    f = tmp_path / "cos.json"
    f.write_text(json.dumps(data))

    result = load_companies(str(f))
    ids = [r["company_id"] for r in result]
    assert len(result) == 2
    assert ids.count("co_001") == 1
    assert "co_002" in ids


def test_load_companies_no_duplicates_unchanged(tmp_path):
    """No duplicates → all companies returned."""
    from src.ingestion.company_ingestion import load_companies

    data = [
        {**_BASE_COMPANY, "company_id": "co_001"},
        {**_BASE_COMPANY, "company_id": "co_002"},
    ]
    f = tmp_path / "cos2.json"
    f.write_text(json.dumps(data))

    result = load_companies(str(f))
    assert len(result) == 2


def test_load_contacts_deduplicates_by_email(tmp_path):
    """Two contacts sharing the same email → only the first is kept."""
    from src.validation.email_validation_mock import load_contacts

    data = [
        {**_BASE_CONTACT, "contact_id": "ct_001", "email": "alice@acme.com"},
        {**_BASE_CONTACT, "contact_id": "ct_002", "email": "bob@acme.com"},
        {**_BASE_CONTACT, "contact_id": "ct_003", "email": "alice@acme.com"},  # dup email
        {**_BASE_CONTACT, "contact_id": "ct_004", "email": "carol@acme.com"},
    ]
    f = tmp_path / "cts.json"
    f.write_text(json.dumps(data))

    result = load_contacts(str(f))
    emails = [r["email"] for r in result]
    assert len(result) == 3
    assert emails.count("alice@acme.com") == 1
    assert "bob@acme.com" in emails
    assert "carol@acme.com" in emails


def test_load_contacts_no_duplicates_unchanged(tmp_path):
    """No duplicates → all contacts returned."""
    from src.validation.email_validation_mock import load_contacts

    data = [
        {**_BASE_CONTACT, "contact_id": "ct_001", "email": "alice@acme.com"},
        {**_BASE_CONTACT, "contact_id": "ct_002", "email": "bob@acme.com"},
    ]
    f = tmp_path / "cts2.json"
    f.write_text(json.dumps(data))

    result = load_contacts(str(f))
    assert len(result) == 2
