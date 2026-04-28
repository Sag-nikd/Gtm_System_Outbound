"""Tests for pipeline run_manifest.json audit trail."""
from __future__ import annotations

import json
import os

import pytest


def test_run_manifest_exists_after_pipeline(tmp_path, monkeypatch):
    """run_manifest.json is written after a full pipeline run."""
    import src.main as main_mod
    from src.config.settings import settings

    monkeypatch.setattr(settings, "OUTPUT_DIR", str(tmp_path))

    main_mod.main()

    assert os.path.exists(os.path.join(str(tmp_path), "run_manifest.json")), \
        "run_manifest.json must exist after pipeline completes"


def test_run_manifest_is_valid_json(tmp_path, monkeypatch):
    """run_manifest.json is parseable as JSON."""
    import src.main as main_mod
    from src.config.settings import settings

    monkeypatch.setattr(settings, "OUTPUT_DIR", str(tmp_path))
    main_mod.main()

    path = os.path.join(str(tmp_path), "run_manifest.json")
    with open(path) as f:
        data = json.load(f)
    assert isinstance(data, dict)


def test_run_manifest_has_required_keys(tmp_path, monkeypatch):
    """run_manifest.json contains all required top-level keys."""
    import src.main as main_mod
    from src.config.settings import settings

    monkeypatch.setattr(settings, "OUTPUT_DIR", str(tmp_path))
    main_mod.main()

    path = os.path.join(str(tmp_path), "run_manifest.json")
    with open(path) as f:
        data = json.load(f)

    for key in ("run_id", "started_at", "completed_at", "mock_mode", "stages", "config_hash"):
        assert key in data, f"Missing required key: {key}"


def test_run_manifest_stages_list_has_entries(tmp_path, monkeypatch):
    """stages list contains at least the company pipeline entry."""
    import src.main as main_mod
    from src.config.settings import settings

    monkeypatch.setattr(settings, "OUTPUT_DIR", str(tmp_path))
    main_mod.main()

    path = os.path.join(str(tmp_path), "run_manifest.json")
    with open(path) as f:
        data = json.load(f)

    stages = data["stages"]
    assert isinstance(stages, list)
    assert len(stages) >= 1

    stage_names = [s["name"] for s in stages]
    assert "company_pipeline" in stage_names


def test_run_manifest_record_counts_positive_in_mock_mode(tmp_path, monkeypatch):
    """Record counts for completed stages are > 0 in mock mode."""
    import src.main as main_mod
    from src.config.settings import settings

    monkeypatch.setattr(settings, "OUTPUT_DIR", str(tmp_path))
    main_mod.main()

    path = os.path.join(str(tmp_path), "run_manifest.json")
    with open(path) as f:
        data = json.load(f)

    company_stage = next(
        (s for s in data["stages"] if s["name"] == "company_pipeline"), None
    )
    assert company_stage is not None
    assert company_stage["record_count"] > 0
