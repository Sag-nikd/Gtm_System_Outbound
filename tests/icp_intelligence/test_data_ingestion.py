"""Story 1: ICP Data Ingestion Layer tests."""
from __future__ import annotations

import csv
import json
import os

import pytest


# ── Fixtures ──────────────────────────────────────────────────────────────────

_VALID_DEAL = {
    "company_name": "Centene Health Partners",
    "domain": "centene.com",
    "industry": "Managed Care",
    "employee_count": 3200,
    "deal_stage": "closed_won",
    "deal_value": 150000,
    "deal_cycle_days": 62,
    "state": "Missouri",
    "primary_volume_metric": 850000,
    "secondary_volume_metric": 120000,
    "tech_stack": "Salesforce",
    "contact_persona": "VP Member Engagement",
    "source_channel": "outbound_email",
    "closed_date": "2025-09-15",
}

_VALID_PIPELINE = {
    "company_name": "BCBS Illinois",
    "domain": "bcbsil.com",
    "deal_stage": "proposal_sent",
    "deal_value": 200000,
    "days_in_stage": 14,
}

_VALID_TAM = {
    "company_name": "Mercy Care Arizona",
    "domain": "mercycareaz.org",
    "industry": "Managed Care",
    "employee_count": 1800,
    "state": "Arizona",
}


# ── (a) Load valid JSON deal data ─────────────────────────────────────────────

def test_load_deal_data_json_returns_list(tmp_path):
    from src.icp_intelligence.data_ingestion import load_deal_data

    data = [_VALID_DEAL, {**_VALID_DEAL, "domain": "other.com", "company_name": "Other Co"}]
    f = tmp_path / "deals.json"
    f.write_text(json.dumps(data))

    result = load_deal_data(str(f))
    assert isinstance(result, list)
    assert len(result) == 2


# ── (b) Load CSV deal data ────────────────────────────────────────────────────

def test_load_deal_data_csv_returns_list(tmp_path):
    from src.icp_intelligence.data_ingestion import load_deal_data

    f = tmp_path / "deals.csv"
    with open(str(f), "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(_VALID_DEAL.keys()))
        writer.writeheader()
        writer.writerow(_VALID_DEAL)

    result = load_deal_data(str(f))
    assert isinstance(result, list)
    assert len(result) == 1
    assert result[0]["company_name"] == "Centene Health Partners"


# ── (c) Record missing company_name → skipped ─────────────────────────────────

def test_load_deal_data_skips_invalid_record(tmp_path):
    from src.icp_intelligence.data_ingestion import load_deal_data

    data = [
        _VALID_DEAL,
        {"industry": "Managed Care", "employee_count": 100, "deal_stage": "closed_won"},  # missing company_name
    ]
    f = tmp_path / "deals.json"
    f.write_text(json.dumps(data))

    result = load_deal_data(str(f))
    assert len(result) == 1
    assert result[0]["company_name"] == "Centene Health Partners"


# ── (d) Duplicate domains → most recent kept ──────────────────────────────────

def test_load_deal_data_deduplicates_by_domain_keeps_most_recent(tmp_path):
    from src.icp_intelligence.data_ingestion import load_deal_data

    older = {**_VALID_DEAL, "domain": "same.com", "closed_date": "2024-01-01", "company_name": "Old Co"}
    newer = {**_VALID_DEAL, "domain": "same.com", "closed_date": "2025-06-01", "company_name": "New Co"}
    data = [older, newer]
    f = tmp_path / "deals.json"
    f.write_text(json.dumps(data))

    result = load_deal_data(str(f))
    assert len(result) == 1
    assert result[0]["company_name"] == "New Co"


# ── (e) Load pipeline data ────────────────────────────────────────────────────

def test_load_pipeline_data_validates_correctly(tmp_path):
    from src.icp_intelligence.data_ingestion import load_pipeline_data

    data = [_VALID_PIPELINE, {**_VALID_PIPELINE, "company_name": "Other Co", "domain": "other.com"}]
    f = tmp_path / "pipeline.json"
    f.write_text(json.dumps(data))

    result = load_pipeline_data(str(f))
    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0]["company_name"] == "BCBS Illinois"


# ── (f) Load TAM data ─────────────────────────────────────────────────────────

def test_load_tam_data_validates_correctly(tmp_path):
    from src.icp_intelligence.data_ingestion import load_tam_data

    data = [_VALID_TAM, {**_VALID_TAM, "company_name": "Other Org", "domain": "other.org"}]
    f = tmp_path / "tam.json"
    f.write_text(json.dumps(data))

    result = load_tam_data(str(f))
    assert isinstance(result, list)
    assert len(result) == 2


# ── (g) Empty file → empty list ───────────────────────────────────────────────

def test_load_deal_data_empty_file_returns_empty_list(tmp_path):
    from src.icp_intelligence.data_ingestion import load_deal_data

    f = tmp_path / "empty.json"
    f.write_text("[]")

    result = load_deal_data(str(f))
    assert result == []


# ── (h) File not found → FileNotFoundError ───────────────────────────────────

def test_load_deal_data_missing_file_raises(tmp_path):
    from src.icp_intelligence.data_ingestion import load_deal_data

    with pytest.raises(FileNotFoundError):
        load_deal_data(str(tmp_path / "nonexistent.json"))
