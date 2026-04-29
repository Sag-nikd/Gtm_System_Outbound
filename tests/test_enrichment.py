import pytest
from src.enrichment.clay_mock_enrichment import enrich_accounts, _get_enriched_signal_summary, PERSONA_MAP, DEFAULT_PERSONAS


def _company(industry="B2B Technology", tier="Tier 1", **kwargs):
    base = {
        "company_id": "C001",
        "industry": industry,
        "icp_tier": tier,
        "growth_signal": False,
        "hiring_signal": False,
        "tech_stack_signal": "Unknown",
    }
    base.update(kwargs)
    return base


# ── Persona mapping ───────────────────────────────────────────────────────────

def test_b2b_technology_gets_vp_sales():
    result = enrich_accounts([_company("B2B Technology")])
    assert "VP Sales" in result[0]["recommended_personas"]


def test_ecommerce_gets_vp_marketing():
    result = enrich_accounts([_company("E-commerce")])
    assert "VP Marketing" in result[0]["recommended_personas"]


def test_logistics_gets_revops_persona():
    result = enrich_accounts([_company("Logistics")])
    assert "Revenue Operations Manager" in result[0]["recommended_personas"]


def test_unknown_industry_gets_default_personas():
    result = enrich_accounts([_company("Aerospace")])
    assert result[0]["recommended_personas"] != ""


def test_default_personas_used_for_unmapped_industry():
    result = enrich_accounts([_company("Aerospace")])
    for persona in DEFAULT_PERSONAS:
        assert persona in result[0]["recommended_personas"]


# ── Contact discovery approval gate ──────────────────────────────────────────

def test_tier1_approved_for_contact_discovery():
    result = enrich_accounts([_company(tier="Tier 1")])
    assert result[0]["contact_discovery_approved"] is True


def test_tier2_approved_for_contact_discovery():
    result = enrich_accounts([_company(tier="Tier 2")])
    assert result[0]["contact_discovery_approved"] is True


def test_tier3_not_approved():
    result = enrich_accounts([_company(tier="Tier 3")])
    assert result[0]["contact_discovery_approved"] is False


def test_disqualified_not_approved():
    result = enrich_accounts([_company(tier="Disqualified")])
    assert result[0]["contact_discovery_approved"] is False


# ── Enrichment metadata ───────────────────────────────────────────────────────

def test_enrichment_status_set():
    result = enrich_accounts([_company()])
    assert result[0]["enrichment_status"] == "enriched"


def test_enrichment_source_set():
    result = enrich_accounts([_company()])
    assert result[0]["enrichment_source"] == "clay_mock"


def test_enrichment_returns_all_companies():
    companies = [_company(tier="Tier 1"), _company(tier="Disqualified")]
    result = enrich_accounts(companies)
    assert len(result) == 2


# ── Signal summary ────────────────────────────────────────────────────────────

def test_signal_summary_with_all_signals():
    company = {"growth_signal": True, "hiring_signal": True, "tech_stack_signal": "Salesforce"}
    summary = _get_enriched_signal_summary(company)
    assert "growth hiring detected" in summary
    assert "active hiring" in summary
    assert "Salesforce" in summary


def test_signal_summary_no_signals():
    company = {"growth_signal": False, "hiring_signal": False, "tech_stack_signal": "Unknown"}
    summary = _get_enriched_signal_summary(company)
    assert summary == "no strong signals"


def test_signal_summary_growth_only():
    company = {"growth_signal": True, "hiring_signal": False, "tech_stack_signal": "Unknown"}
    summary = _get_enriched_signal_summary(company)
    assert "growth hiring detected" in summary
    assert "active hiring" not in summary
