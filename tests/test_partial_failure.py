"""Tests that scoring and enrichment continue when individual records fail."""
from __future__ import annotations

import os
import pytest


_BASE = {
    "company_id": "co_001",
    "company_name": "Acme Health",
    "website": "https://acme.com",
    "domain": "acme.com",
    "industry": "Managed Care",
    "employee_count": 500,
    "revenue_range": "$50M+",
    "state": "Texas",
    "primary_volume_metric": 300000,
    "secondary_volume_metric": 100000,
    "growth_signal": True,
    "hiring_signal": True,
    "tech_stack_signal": "Salesforce",
    "ingestion_source": "fake_data",
    "ingestion_status": "ingested",
}


@pytest.fixture
def icp_rules():
    from src.config.settings import settings
    from src.scoring.icp_scoring import load_icp_rules
    return load_icp_rules(os.path.join(settings.CONFIG_DIR, "icp_rules.json"))


def test_score_companies_continues_past_one_failure(icp_rules):
    """score_companies() skips a record that causes an error and processes the rest."""
    from src.scoring.icp_scoring import score_companies

    companies = [
        {**_BASE, "company_id": "co_001"},
        None,  # will trigger AttributeError in score_company
        {**_BASE, "company_id": "co_003"},
    ]

    result = score_companies(companies, icp_rules)
    ids = [r["company_id"] for r in result]
    assert "co_001" in ids
    assert "co_003" in ids
    assert len(result) == 2


def test_score_companies_returns_all_on_no_failures(icp_rules):
    """score_companies() returns all records when no record fails."""
    from src.scoring.icp_scoring import score_companies

    companies = [
        {**_BASE, "company_id": "co_001"},
        {**_BASE, "company_id": "co_002"},
    ]
    result = score_companies(companies, icp_rules)
    assert len(result) == 2


def test_enrich_accounts_continues_past_one_failure():
    """enrich_accounts() skips a record that causes an error and processes the rest."""
    from src.enrichment.clay_mock_enrichment import enrich_accounts

    companies = [
        {**_BASE, "company_id": "co_001", "icp_tier": "Tier 1"},
        None,  # triggers AttributeError in enrich_accounts
        {**_BASE, "company_id": "co_003", "icp_tier": "Tier 2"},
    ]

    result = enrich_accounts(companies)
    ids = [r.get("company_id") for r in result]
    assert "co_001" in ids
    assert "co_003" in ids
    assert len(result) == 2


def test_enrich_accounts_returns_all_on_no_failures():
    """enrich_accounts() returns all records when no record fails."""
    from src.enrichment.clay_mock_enrichment import enrich_accounts

    companies = [
        {**_BASE, "company_id": "co_001", "icp_tier": "Tier 1"},
        {**_BASE, "company_id": "co_002", "icp_tier": "Tier 2"},
    ]
    result = enrich_accounts(companies)
    assert len(result) == 2
