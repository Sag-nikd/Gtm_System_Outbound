from __future__ import annotations

import os
import pytest

from src.integrations.apollo import ApolloMockClient
from src.integrations.clay import ClayMockClient
from src.integrations.hubspot import HubSpotMockClient
from src.integrations.zerobounce import ZeroBounceMockClient
from src.integrations.neverbounce import NeverBounceMockClient
from src.integrations.validity import ValidityMockClient

from src.main import (
    run_company_pipeline,
    run_contact_pipeline,
    run_activation_pipeline,
    run_campaign_monitoring,
    main,
)


@pytest.fixture
def mock_clients():
    return (
        ApolloMockClient(),
        ClayMockClient(),
        HubSpotMockClient(),
        ZeroBounceMockClient(),
        NeverBounceMockClient(),
        ValidityMockClient(),
    )


@pytest.fixture
def enriched(mock_clients, tmp_path, monkeypatch):
    from src.config import settings
    monkeypatch.setattr(settings, "OUTPUT_DIR", str(tmp_path))
    apollo, clay, *_ = mock_clients
    return run_company_pipeline(apollo, clay)


@pytest.fixture
def validated(enriched, mock_clients, tmp_path, monkeypatch):
    from src.config import settings
    monkeypatch.setattr(settings, "OUTPUT_DIR", str(tmp_path))
    apollo, _, _, zerobounce, neverbounce, _ = mock_clients
    return run_contact_pipeline(enriched, apollo, zerobounce, neverbounce)


# ── Stage smoke tests ─────────────────────────────────────────────────────────

def test_company_pipeline_returns_enriched_list(mock_clients, tmp_path, monkeypatch):
    from src.config import settings
    monkeypatch.setattr(settings, "OUTPUT_DIR", str(tmp_path))
    apollo, clay, *_ = mock_clients
    result = run_company_pipeline(apollo, clay)
    assert isinstance(result, list)
    assert len(result) > 0
    assert "icp_tier" in result[0]
    assert "contact_discovery_approved" in result[0]


def test_company_pipeline_writes_four_csvs(mock_clients, tmp_path, monkeypatch):
    from src.config import settings
    monkeypatch.setattr(settings, "OUTPUT_DIR", str(tmp_path))
    apollo, clay, *_ = mock_clients
    run_company_pipeline(apollo, clay)
    expected = [
        "01_company_ingestion.csv",
        "02_company_enrichment.csv",
        "03_icp_scored_accounts.csv",
        "04_approved_accounts.csv",
    ]
    for fname in expected:
        assert os.path.exists(os.path.join(str(tmp_path), fname)), f"Missing: {fname}"


def test_contact_pipeline_returns_validated_contacts(
    enriched, mock_clients, tmp_path, monkeypatch
):
    from src.config import settings
    monkeypatch.setattr(settings, "OUTPUT_DIR", str(tmp_path))
    apollo, _, _, zerobounce, neverbounce, _ = mock_clients
    result = run_contact_pipeline(enriched, apollo, zerobounce, neverbounce)
    assert isinstance(result, list)
    assert len(result) > 0
    assert "final_validation_status" in result[0]


def test_contact_pipeline_writes_two_csvs(
    enriched, mock_clients, tmp_path, monkeypatch
):
    from src.config import settings
    monkeypatch.setattr(settings, "OUTPUT_DIR", str(tmp_path))
    apollo, _, _, zerobounce, neverbounce, _ = mock_clients
    run_contact_pipeline(enriched, apollo, zerobounce, neverbounce)
    for fname in ("05_discovered_contacts.csv", "06_email_validation_results.csv"):
        assert os.path.exists(os.path.join(str(tmp_path), fname)), f"Missing: {fname}"


def test_activation_pipeline_writes_four_csvs(
    validated, enriched, mock_clients, tmp_path, monkeypatch
):
    from src.config import settings
    monkeypatch.setattr(settings, "OUTPUT_DIR", str(tmp_path))
    _, _, hubspot, *_ = mock_clients
    run_activation_pipeline(validated, enriched, hubspot)
    for fname in (
        "07_hubspot_company_export.csv",
        "08_hubspot_contact_export.csv",
        "09_email_sequence_export.csv",
        "10_linkedin_outreach_export.csv",
    ):
        assert os.path.exists(os.path.join(str(tmp_path), fname)), f"Missing: {fname}"


def test_campaign_monitoring_writes_health_report(mock_clients, tmp_path, monkeypatch):
    from src.config import settings
    monkeypatch.setattr(settings, "OUTPUT_DIR", str(tmp_path))
    *_, validity = mock_clients
    run_campaign_monitoring(validity)
    assert os.path.exists(os.path.join(str(tmp_path), "11_campaign_health_report.csv"))


# ── Full pipeline smoke test ──────────────────────────────────────────────────

def test_full_pipeline_all_11_csvs_created(tmp_path, monkeypatch):
    from src.config import settings
    monkeypatch.setattr(settings, "OUTPUT_DIR", str(tmp_path))
    main()
    expected_files = [
        "01_company_ingestion.csv",
        "02_company_enrichment.csv",
        "03_icp_scored_accounts.csv",
        "04_approved_accounts.csv",
        "05_discovered_contacts.csv",
        "06_email_validation_results.csv",
        "07_hubspot_company_export.csv",
        "08_hubspot_contact_export.csv",
        "09_email_sequence_export.csv",
        "10_linkedin_outreach_export.csv",
        "11_campaign_health_report.csv",
    ]
    for fname in expected_files:
        path = os.path.join(str(tmp_path), fname)
        assert os.path.exists(path), f"Missing output: {fname}"
        assert os.path.getsize(path) > 0, f"Empty output: {fname}"
