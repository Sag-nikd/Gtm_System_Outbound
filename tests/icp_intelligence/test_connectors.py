"""Story 9: CRM Data Connector Interfaces tests."""
from __future__ import annotations

import inspect
import os

import pytest

from src.config.settings import settings


def _deal_file():
    return os.path.join(settings.DATA_DIR, "icp_intelligence", "mock_deal_history.json")


# ── (a) CSVConnector.connect() with valid file → True ────────────────────────

def test_csv_connector_connect_valid_file():
    from src.icp_intelligence.connectors.csv_connector import CSVConnector
    conn = CSVConnector(deal_file=_deal_file())
    assert conn.connect() is True


# ── (b) CSVConnector.connect() with missing file → False ──────────────────────

def test_csv_connector_connect_missing_file():
    from src.icp_intelligence.connectors.csv_connector import CSVConnector
    conn = CSVConnector(deal_file="/nonexistent/deals.json")
    assert conn.connect() is False


# ── (c) CSVConnector.pull_deals() returns list of dicts ──────────────────────

def test_csv_connector_pull_deals_returns_list():
    from src.icp_intelligence.connectors.csv_connector import CSVConnector
    conn = CSVConnector(deal_file=_deal_file())
    deals = conn.pull_deals()
    assert isinstance(deals, list)
    assert len(deals) > 0
    assert isinstance(deals[0], dict)


# ── (d) HubSpot and Salesforce connectors are ICPDataConnectorBase instances ──

def test_hubspot_connector_is_base_instance():
    from src.icp_intelligence.connectors.base import ICPDataConnectorBase
    from src.icp_intelligence.connectors.hubspot_connector import HubSpotICPConnector
    conn = HubSpotICPConnector()
    assert isinstance(conn, ICPDataConnectorBase)


def test_salesforce_connector_is_base_instance():
    from src.icp_intelligence.connectors.base import ICPDataConnectorBase
    from src.icp_intelligence.connectors.salesforce_connector import SalesforceICPConnector
    conn = SalesforceICPConnector()
    assert isinstance(conn, ICPDataConnectorBase)


# ── (e) HubSpotICPConnector.map_to_deal_record() transforms fields ───────────

def test_hubspot_connector_map_to_deal_record():
    from src.icp_intelligence.connectors.hubspot_connector import HubSpotICPConnector
    conn = HubSpotICPConnector()
    raw = {
        "dealname": "Centene Q4 Deal",
        "amount": "150000",
        "dealstage": "closedwon",
        "closedate": "2025-09-15",
        "pipeline": "default",
        "hs_analytics_source": "DIRECT_TRAFFIC",
        "industry": "Managed Care",
        "employee_count": "3200",
    }
    result = conn.map_to_deal_record(raw)
    assert "company_name" in result
    assert "deal_stage" in result
    assert result["deal_stage"] == "closed_won"
    assert result.get("deal_value") == 150000.0


# ── (f) SalesforceICPConnector.map_to_deal_record() transforms fields ─────────

def test_salesforce_connector_map_to_deal_record():
    from src.icp_intelligence.connectors.salesforce_connector import SalesforceICPConnector
    conn = SalesforceICPConnector()
    raw = {
        "Name": "BluePath Health Plan - Q1 2025",
        "Amount": "200000",
        "StageName": "Closed Won",
        "CloseDate": "2025-10-02",
        "LeadSource": "Cold Email",
        "Industry__c": "Health Plan",
        "NumberOfEmployees": "3200",
    }
    result = conn.map_to_deal_record(raw)
    assert "company_name" in result
    assert "deal_stage" in result
    assert result["deal_stage"] == "closed_won"
    assert result.get("deal_value") == 200000.0


# ── (g) Interface signatures match across connectors ─────────────────────────

def test_connector_interface_signatures_match():
    from src.icp_intelligence.connectors.csv_connector import CSVConnector
    from src.icp_intelligence.connectors.hubspot_connector import HubSpotICPConnector
    from src.icp_intelligence.connectors.salesforce_connector import SalesforceICPConnector

    for method_name in ("connect", "pull_deals", "pull_pipeline", "pull_companies"):
        csv_sig = inspect.signature(getattr(CSVConnector, method_name))
        hs_sig = inspect.signature(getattr(HubSpotICPConnector, method_name))
        sf_sig = inspect.signature(getattr(SalesforceICPConnector, method_name))
        # All should have the same parameter names (at minimum 'self' and optionally 'since')
        csv_params = set(csv_sig.parameters.keys())
        hs_params = set(hs_sig.parameters.keys())
        sf_params = set(sf_sig.parameters.keys())
        assert csv_params == hs_params == sf_params, \
            f"Signature mismatch for {method_name}: {csv_params} vs {hs_params} vs {sf_params}"
