"""Story 8: Wire Stage 0 into main.py — integration tests."""
from __future__ import annotations

import json
import os

import pytest

from src.config.settings import settings


# ── (a) ICP_INTELLIGENCE_ENABLED=false → pipeline runs as before ──────────────

def test_pipeline_unchanged_when_icp_disabled(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "ICP_INTELLIGENCE_ENABLED", False)
    from src.main import main
    main()
    expected = [
        "01_company_ingestion.csv", "02_company_enrichment.csv",
        "03_icp_scored_accounts.csv", "04_approved_accounts.csv",
        "05_discovered_contacts.csv", "06_email_validation_results.csv",
        "07_hubspot_company_export.csv", "08_hubspot_contact_export.csv",
        "09_email_sequence_export.csv", "10_linkedin_outreach_export.csv",
        "11_campaign_health_report.csv",
    ]
    for fname in expected:
        assert os.path.exists(str(tmp_path / fname)), f"Missing: {fname}"
    # No Stage 0 output expected
    assert not os.path.exists(str(tmp_path / "00_icp_intelligence_report.json"))


# ── (b) ICP_INTELLIGENCE_ENABLED=true → Stage 0 + 11 original CSVs ───────────

def test_pipeline_with_icp_intelligence_enabled(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "ICP_INTELLIGENCE_ENABLED", True)
    monkeypatch.setattr(
        settings, "ICP_DEAL_DATA_PATH",
        os.path.join(settings.DATA_DIR, "icp_intelligence", "mock_deal_history.json")
    )
    from src.main import main
    main()
    assert os.path.exists(str(tmp_path / "00_icp_intelligence_report.json"))
    assert os.path.exists(str(tmp_path / "01_company_ingestion.csv"))
    assert os.path.exists(str(tmp_path / "11_campaign_health_report.csv"))


# ── (c) run_manifest includes icp_intelligence stage when enabled ─────────────

def test_manifest_includes_icp_stage_when_enabled(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "ICP_INTELLIGENCE_ENABLED", True)
    monkeypatch.setattr(
        settings, "ICP_DEAL_DATA_PATH",
        os.path.join(settings.DATA_DIR, "icp_intelligence", "mock_deal_history.json")
    )
    from src.main import main
    main()
    manifest_path = str(tmp_path / "run_manifest.json")
    with open(manifest_path) as f:
        manifest = json.load(f)
    stage_names = [s["name"] for s in manifest["stages"]]
    assert "icp_intelligence" in stage_names


# ── (d) ICP enabled but deal data path missing → clear error ─────────────────

def test_icp_enabled_missing_deal_path_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "OUTPUT_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "ICP_INTELLIGENCE_ENABLED", True)
    monkeypatch.setattr(settings, "ICP_DEAL_DATA_PATH", "")
    from src.main import main
    with pytest.raises((ValueError, FileNotFoundError)):
        main()
