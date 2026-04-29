"""Story 6: Feedback Ingestor tests."""
from __future__ import annotations

import csv
import json
import os

import pytest

from src.config.settings import settings


def _outputs_dir(tmp_path, monkeypatch):
    """Run pipeline to create output CSVs in tmp_path."""
    monkeypatch.setattr(settings, "OUTPUT_DIR", str(tmp_path))
    from src.main import main
    main()
    return str(tmp_path)


# ── (a) Read pipeline CSVs from outputs → non-empty list ─────────────────────

def test_collect_pipeline_feedback_returns_non_empty(tmp_path, monkeypatch):
    from src.icp_intelligence.feedback_ingestor import collect_pipeline_feedback
    output_dir = _outputs_dir(tmp_path, monkeypatch)
    result = collect_pipeline_feedback(output_dir)
    assert isinstance(result, list)
    assert len(result) > 0


# ── (b) Feed pipeline_outcomes.csv → outcomes parsed correctly ────────────────

def test_pipeline_outcomes_parsed_correctly(tmp_path):
    from src.icp_intelligence.feedback_ingestor import collect_pipeline_feedback
    outcomes_path = os.path.join(str(tmp_path), "pipeline_outcomes.csv")
    with open(outcomes_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["email", "company_name", "outcome", "outcome_date"])
        writer.writeheader()
        writer.writerow({"email": "test@co.com", "company_name": "Test Co",
                         "outcome": "replied", "outcome_date": "2026-03-10"})
        writer.writerow({"email": "test2@co.com", "company_name": "Test Co 2",
                         "outcome": "meeting_booked", "outcome_date": "2026-03-15"})
    result = collect_pipeline_feedback(str(tmp_path))
    outcomes = [r["outcome"] for r in result if r.get("outcome")]
    assert "replied" in outcomes
    assert "meeting_booked" in outcomes


# ── (c) Merge feedback with deals → no domain duplicates ─────────────────────

def test_merge_feedback_no_domain_duplicates(tmp_path, monkeypatch):
    from src.icp_intelligence.feedback_ingestor import collect_pipeline_feedback, merge_feedback_with_deals
    output_dir = _outputs_dir(tmp_path, monkeypatch)
    feedback = collect_pipeline_feedback(output_dir)
    existing_deals = [
        {"company_name": "Centene Health Partners", "domain": "centene.com",
         "industry": "Managed Care", "employee_count": 3200, "deal_stage": "closed_won"}
    ]
    merged = merge_feedback_with_deals(feedback, existing_deals)
    domains = [d.get("domain") for d in merged if d.get("domain")]
    assert len(domains) == len(set(domains)), "Duplicate domains found after merge"


# ── (d) New companies from pipeline added as new records ─────────────────────

def test_merge_feedback_adds_new_companies(tmp_path, monkeypatch):
    from src.icp_intelligence.feedback_ingestor import collect_pipeline_feedback, merge_feedback_with_deals
    output_dir = _outputs_dir(tmp_path, monkeypatch)
    feedback = collect_pipeline_feedback(output_dir)
    # Start with empty deal history
    merged = merge_feedback_with_deals(feedback, [])
    assert len(merged) > 0


# ── (e) Missing CSVs → skipped gracefully, no crash ──────────────────────────

def test_collect_feedback_missing_csvs_no_crash(tmp_path):
    from src.icp_intelligence.feedback_ingestor import collect_pipeline_feedback
    # tmp_path has no pipeline CSVs
    result = collect_pipeline_feedback(str(tmp_path))
    assert isinstance(result, list)


# ── (f) Empty outcomes file → existing deals unchanged ────────────────────────

def test_empty_outcomes_file_deals_unchanged(tmp_path):
    from src.icp_intelligence.feedback_ingestor import collect_pipeline_feedback, merge_feedback_with_deals
    # Create empty outcomes CSV
    outcomes_path = os.path.join(str(tmp_path), "pipeline_outcomes.csv")
    with open(outcomes_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["email", "company_name", "outcome", "outcome_date"])
        writer.writeheader()
    existing = [{"company_name": "A", "domain": "a.com", "industry": "Managed Care",
                 "employee_count": 1000, "deal_stage": "closed_won"}]
    feedback = collect_pipeline_feedback(str(tmp_path))
    merged = merge_feedback_with_deals(feedback, existing)
    assert any(d.get("domain") == "a.com" for d in merged)
