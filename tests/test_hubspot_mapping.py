from __future__ import annotations

from src.hubspot.hubspot_sync_mock import (
    create_hubspot_company_records,
    create_hubspot_contact_records,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

def _company(tier: str, approved: bool = True, **kwargs) -> dict:
    base = {
        "company_id": "C001",
        "company_name": "Test Health Plan",
        "domain": "testhealthplan.com",
        "website": "https://testhealthplan.com",
        "industry": "Managed Care",
        "employee_count": 2000,
        "state": "Texas",
        "icp_score": 85.0,
        "icp_tier": tier,
        "recommended_personas": "VP Member Engagement",
        "contact_discovery_approved": approved,
    }
    base.update(kwargs)
    return base


def _contact(status: str, company_id: str = "C001", **kwargs) -> dict:
    base = {
        "contact_id": "K001",
        "company_id": company_id,
        "first_name": "Angela",
        "last_name": "Morrison",
        "email": "angela@test.com",
        "title": "VP Member Engagement",
        "linkedin_url": "https://linkedin.com/in/angela",
        "persona_type": "VP Member Engagement",
        "final_validation_status": status,
    }
    base.update(kwargs)
    return base


# ── Company lifecycle stage mapping ──────────────────────────────────────────

def test_tier1_approved_gets_contact_discovery_approved_stage():
    records = create_hubspot_company_records([_company("Tier 1", approved=True)])
    assert records[0]["lifecycle_stage"] == "Contact Discovery Approved"


def test_tier2_approved_gets_contact_discovery_approved_stage():
    records = create_hubspot_company_records([_company("Tier 2", approved=True)])
    assert records[0]["lifecycle_stage"] == "Contact Discovery Approved"


def test_tier3_gets_enriched_account_stage():
    records = create_hubspot_company_records([_company("Tier 3", approved=False)])
    assert records[0]["lifecycle_stage"] == "Enriched Account"


def test_disqualified_gets_suppressed_stage():
    records = create_hubspot_company_records([_company("Disqualified", approved=False)])
    assert records[0]["lifecycle_stage"] == "Suppressed"


# ── Contact lifecycle stage mapping ──────────────────────────────────────────

def test_approved_contact_gets_contact_validated_stage():
    companies = [_company("Tier 1")]
    contacts = [_contact("approved")]
    records = create_hubspot_contact_records(contacts, companies)
    assert records[0]["lifecycle_stage"] == "Contact Validated"


def test_review_contact_gets_nurture_stage():
    companies = [_company("Tier 1")]
    contacts = [_contact("review")]
    records = create_hubspot_contact_records(contacts, companies)
    assert records[0]["lifecycle_stage"] == "Nurture"


def test_suppressed_contact_gets_suppressed_stage():
    companies = [_company("Tier 1")]
    contacts = [_contact("suppressed")]
    records = create_hubspot_contact_records(contacts, companies)
    assert records[0]["lifecycle_stage"] == "Suppressed"


# ── Company record structure ──────────────────────────────────────────────────

def test_company_record_contains_required_fields():
    records = create_hubspot_company_records([_company("Tier 1")])
    required = {
        "company_id", "company_name", "domain", "icp_score",
        "icp_tier", "lifecycle_stage", "hubspot_sync_status",
    }
    assert required.issubset(records[0].keys())


def test_company_record_sync_status_is_ready():
    records = create_hubspot_company_records([_company("Tier 1")])
    assert records[0]["hubspot_sync_status"] == "ready_for_sync"


def test_company_records_count_matches_input():
    records = create_hubspot_company_records([
        _company("Tier 1", company_id="C001"),
        _company("Disqualified", company_id="C002", approved=False),
    ])
    assert len(records) == 2


# ── Contact record structure ──────────────────────────────────────────────────

def test_contact_record_contains_required_fields():
    companies = [_company("Tier 1")]
    records = create_hubspot_contact_records([_contact("approved")], companies)
    required = {
        "contact_id", "company_id", "email",
        "lifecycle_stage", "hubspot_sync_status",
    }
    assert required.issubset(records[0].keys())


def test_contact_inherits_company_name_from_companies_list():
    companies = [_company("Tier 1", company_id="C001", company_name="Centene Health")]
    contact = _contact("approved", company_id="C001")
    contact.pop("company_name", None)
    records = create_hubspot_contact_records([contact], companies)
    assert records[0]["company_name"] == "Centene Health"


def test_contact_icp_tier_inherited_from_company():
    companies = [_company("Tier 2", company_id="C001")]
    records = create_hubspot_contact_records([_contact("approved")], companies)
    assert records[0]["icp_tier"] == "Tier 2"
