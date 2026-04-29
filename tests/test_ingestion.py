import json
import pytest
from src.ingestion.company_ingestion import load_companies, _extract_domain, _normalize_company

VALID_COMPANY = {
    "company_id": "C001",
    "company_name": "test health plan",
    "website": "https://www.testhealth.com",
    "industry": "managed care",
    "employee_count": 1000,
    "revenue_range": "$50M-$100M",
    "state": "texas",
    "primary_volume_metric": 300_000,
    "secondary_volume_metric": 50_000,
    "growth_signal": True,
    "hiring_signal": True,
    "tech_stack_signal": "Salesforce",
}


# ── Domain extraction ─────────────────────────────────────────────────────────

def test_extract_domain_strips_www():
    assert _extract_domain("https://www.healthplan.com") == "healthplan.com"


def test_extract_domain_without_protocol():
    assert _extract_domain("example.com") == "example.com"


def test_extract_domain_with_path():
    assert _extract_domain("https://www.test.com/about") == "test.com"


def test_extract_domain_already_bare():
    assert _extract_domain("https://healthplan.com") == "healthplan.com"


# ── Field normalization ───────────────────────────────────────────────────────

def test_normalize_title_cases_company_name():
    result = _normalize_company({**VALID_COMPANY})
    assert result["company_name"] == "Test Health Plan"


def test_normalize_title_cases_industry():
    result = _normalize_company({**VALID_COMPANY})
    assert result["industry"] == "Managed Care"


def test_normalize_title_cases_state():
    result = _normalize_company({**VALID_COMPANY})
    assert result["state"] == "Texas"


def test_normalize_sets_ingestion_status():
    result = _normalize_company({**VALID_COMPANY})
    assert result["ingestion_status"] == "ingested"


def test_normalize_sets_ingestion_source():
    result = _normalize_company({**VALID_COMPANY})
    assert result["ingestion_source"] == "fake_data"


def test_normalize_extracts_domain():
    result = _normalize_company({**VALID_COMPANY})
    assert result["domain"] == "testhealth.com"


# ── load_companies ────────────────────────────────────────────────────────────

def test_load_companies_returns_list(tmp_path):
    f = tmp_path / "companies.json"
    f.write_text(json.dumps([VALID_COMPANY]))
    result = load_companies(str(f))
    assert isinstance(result, list)
    assert len(result) == 1


def test_load_companies_normalizes_fields(tmp_path):
    f = tmp_path / "companies.json"
    f.write_text(json.dumps([VALID_COMPANY]))
    result = load_companies(str(f))
    assert result[0]["company_name"] == "Test Health Plan"
    assert result[0]["ingestion_status"] == "ingested"


def test_load_companies_skips_missing_fields(tmp_path):
    incomplete = {"company_id": "C001", "company_name": "Incomplete"}
    f = tmp_path / "companies.json"
    f.write_text(json.dumps([incomplete]))
    result = load_companies(str(f))
    assert len(result) == 0


def test_load_companies_skips_invalid_keeps_valid(tmp_path):
    incomplete = {"company_id": "C002", "company_name": "Bad Record"}
    f = tmp_path / "companies.json"
    f.write_text(json.dumps([VALID_COMPANY, incomplete]))
    result = load_companies(str(f))
    assert len(result) == 1
    assert result[0]["company_id"] == "C001"


def test_load_companies_empty_file(tmp_path):
    f = tmp_path / "companies.json"
    f.write_text("[]")
    result = load_companies(str(f))
    assert result == []
