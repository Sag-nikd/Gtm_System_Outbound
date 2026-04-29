"""Story 7: ICP Intelligence Orchestrator tests."""
from __future__ import annotations

import json
import os
import glob as glob_mod

import pytest

from src.config.settings import settings


def _deal_path():
    return os.path.join(settings.DATA_DIR, "icp_intelligence", "mock_deal_history.json")


# ── (a) Run → 00_icp_intelligence_report.json written ────────────────────────

def test_orchestrator_writes_intelligence_report(tmp_path, monkeypatch):
    from src.icp_intelligence_runner import run_icp_intelligence
    monkeypatch.setattr(settings, "OUTPUT_DIR", str(tmp_path))
    run_icp_intelligence(deal_data_path=_deal_path(), config_dir=str(tmp_path))
    assert os.path.exists(str(tmp_path / "00_icp_intelligence_report.json"))


# ── (b) Run → 00_icp_summary.csv written ─────────────────────────────────────

def test_orchestrator_writes_summary_csv(tmp_path, monkeypatch):
    from src.icp_intelligence_runner import run_icp_intelligence
    monkeypatch.setattr(settings, "OUTPUT_DIR", str(tmp_path))
    run_icp_intelligence(deal_data_path=_deal_path(), config_dir=str(tmp_path))
    assert os.path.exists(str(tmp_path / "00_icp_summary.csv"))


# ── (c) Run → config/apollo_query_config.json written ────────────────────────

def test_orchestrator_writes_apollo_config(tmp_path, monkeypatch):
    from src.icp_intelligence_runner import run_icp_intelligence
    monkeypatch.setattr(settings, "OUTPUT_DIR", str(tmp_path))
    run_icp_intelligence(deal_data_path=_deal_path(), config_dir=str(tmp_path))
    assert os.path.exists(str(tmp_path / "apollo_query_config.json"))


# ── (d) Return dict has all expected keys ─────────────────────────────────────

def test_orchestrator_return_dict_has_expected_keys(tmp_path, monkeypatch):
    from src.icp_intelligence_runner import run_icp_intelligence
    monkeypatch.setattr(settings, "OUTPUT_DIR", str(tmp_path))
    result = run_icp_intelligence(deal_data_path=_deal_path(), config_dir=str(tmp_path))
    for key in ("profile", "rules", "drift_report", "apollo_config", "actions_taken"):
        assert key in result, f"Missing key: {key}"


# ── (e) Run with feedback_dir → merges without crash ─────────────────────────

def test_orchestrator_with_feedback_dir(tmp_path, monkeypatch):
    from src.icp_intelligence_runner import run_icp_intelligence
    from src.main import main
    monkeypatch.setattr(settings, "OUTPUT_DIR", str(tmp_path))
    main()  # generate pipeline outputs first
    result = run_icp_intelligence(
        deal_data_path=_deal_path(),
        config_dir=str(tmp_path),
        feedback_dir=str(tmp_path),
    )
    assert result.get("profile") is not None


# ── (f) Run twice → icp_history has timestamped backup ───────────────────────

def test_orchestrator_run_twice_creates_history(tmp_path, monkeypatch):
    from src.icp_intelligence_runner import run_icp_intelligence
    monkeypatch.setattr(settings, "OUTPUT_DIR", str(tmp_path))
    run_icp_intelligence(deal_data_path=_deal_path(), config_dir=str(tmp_path))
    run_icp_intelligence(deal_data_path=_deal_path(), config_dir=str(tmp_path))
    history_dir = tmp_path / "icp_history"
    history_files = list(history_dir.glob("icp_rules_*.json")) if history_dir.exists() else []
    assert len(history_files) >= 1
