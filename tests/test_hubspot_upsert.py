"""Tests for HubSpot upsert-by-domain/email semantics."""
from __future__ import annotations

from src.integrations.hubspot.mock_client import HubSpotMockClient


def _make_company(domain: str, company_id: str = None) -> dict:
    return {
        "company_id": company_id or f"co_{domain}",
        "company_name": f"Company {domain}",
        "domain": domain,
        "website": f"https://{domain}",
        "industry": "Managed Care",
        "employee_count": 500,
        "icp_tier": "Tier 1",
        "icp_score": 85.0,
        "contact_discovery_approved": True,
    }


def _make_contact(email: str, company_id: str = "co_001") -> dict:
    return {
        "contact_id": f"ct_{email.split('@')[0]}",
        "company_id": company_id,
        "first_name": "Alice",
        "last_name": "Smith",
        "email": email,
        "title": "VP",
        "persona_type": "VP Member Engagement",
        "final_validation_status": "approved",
        "linkedin_url": "",
    }


def test_upsert_companies_deduplicates_by_domain():
    """Two companies sharing a domain produce one record."""
    client = HubSpotMockClient()
    companies = [
        _make_company("acme.com", "co_001"),
        _make_company("beta.com", "co_002"),
        _make_company("acme.com", "co_003"),  # duplicate domain
    ]
    result = client.upsert_companies(companies)
    domains = [r["domain"] for r in result]
    assert len(result) == 2
    assert domains.count("acme.com") == 1
    assert "beta.com" in domains


def test_upsert_contacts_deduplicates_by_email():
    """Two contacts sharing an email produce one record."""
    client = HubSpotMockClient()
    companies = [_make_company("acme.com", "co_001")]
    contacts = [
        _make_contact("alice@acme.com", "co_001"),
        _make_contact("bob@acme.com", "co_001"),
        _make_contact("alice@acme.com", "co_001"),  # duplicate email
    ]
    result = client.upsert_contacts(contacts, companies)
    emails = [r["email"] for r in result]
    assert len(result) == 2
    assert emails.count("alice@acme.com") == 1
    assert "bob@acme.com" in emails


def test_upsert_companies_no_duplicates_unchanged():
    """No duplicates — all companies returned."""
    client = HubSpotMockClient()
    companies = [_make_company("acme.com"), _make_company("beta.com")]
    result = client.upsert_companies(companies)
    assert len(result) == 2


def test_upsert_contacts_no_duplicates_unchanged():
    """No duplicate emails — all contacts returned."""
    client = HubSpotMockClient()
    companies = [_make_company("acme.com", "co_001")]
    contacts = [_make_contact("alice@acme.com"), _make_contact("bob@acme.com")]
    result = client.upsert_contacts(contacts, companies)
    assert len(result) == 2
