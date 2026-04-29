from __future__ import annotations

import csv
import json
import os
from typing import List, Optional

from src.utils.logger import get_logger

log = get_logger(__name__)

_PIPELINE_CSV_MAP = {
    "04_approved_accounts.csv": ("company_name", "icp_tier", "icp_score", "domain"),
    "06_email_validation_results.csv": ("company_name", "email", "final_validation_status",
                                        "persona_type", "icp_tier"),
    "09_email_sequence_export.csv": ("company_name", "email", "persona_type",
                                     "email_step_1_angle"),
    "11_campaign_health_report.csv": ("campaign_name", "health_status", "open_rate",
                                      "bounce_rate"),
}

_OUTCOMES_CSV = "pipeline_outcomes.csv"


def _read_csv(path: str) -> List[dict]:
    if not os.path.exists(path):
        return []
    try:
        with open(path, newline="", encoding="utf-8") as f:
            return [dict(row) for row in csv.DictReader(f)]
    except Exception as exc:
        log.warning("Could not read %s: %s", path, exc)
        return []


def collect_pipeline_feedback(output_dir: str) -> List[dict]:
    """Read pipeline output CSVs and pipeline_outcomes.csv → unified feedback list."""
    feedback: List[dict] = []

    # Read structured pipeline outputs
    for csv_name, fields in _PIPELINE_CSV_MAP.items():
        path = os.path.join(output_dir, csv_name)
        rows = _read_csv(path)
        if not rows:
            log.warning("Skipping missing or empty pipeline file: %s", csv_name)
            continue
        for row in rows:
            entry = {"_source": csv_name}
            for field in fields:
                if field in row:
                    entry[field] = row[field]
            feedback.append(entry)
        log.info("Read %d records from %s", len(rows), csv_name)

    # Read pipeline outcomes (user-supplied after-the-fact)
    outcomes_path = os.path.join(output_dir, _OUTCOMES_CSV)
    outcomes_rows = _read_csv(outcomes_path)
    for row in outcomes_rows:
        feedback.append({
            "_source": _OUTCOMES_CSV,
            "company_name": row.get("company_name", ""),
            "domain": row.get("domain", ""),
            "email": row.get("email", ""),
            "outcome": row.get("outcome", ""),
            "outcome_date": row.get("outcome_date", ""),
        })
    if outcomes_rows:
        log.info("Read %d outcome records from %s", len(outcomes_rows), _OUTCOMES_CSV)

    log.info("Collected %d total feedback records from %s", len(feedback), output_dir)
    return feedback


def merge_feedback_with_deals(
    feedback: List[dict],
    existing_deals: List[dict],
) -> List[dict]:
    """Merge pipeline feedback with existing deal records. Deduplicates by domain."""
    seen_domains: dict = {}
    merged: List[dict] = []

    for deal in existing_deals:
        domain = (deal.get("domain") or "").strip().lower()
        if domain and domain not in seen_domains:
            seen_domains[domain] = len(merged)
        merged.append(deal)

    # Build new deal records from all feedback sources
    outcome_companies: dict = {}  # key → aggregated record

    for entry in feedback:
        source = entry.get("_source", "")
        company_name = entry.get("company_name", "")
        domain = (entry.get("domain") or "").strip().lower()
        if not company_name:
            continue

        # Determine deal stage from source
        if source == _OUTCOMES_CSV:
            outcome = entry.get("outcome", "")
            stage = _outcome_to_stage(outcome)
        elif source == "04_approved_accounts.csv":
            stage = "contacted"
        elif source == "06_email_validation_results.csv":
            fvs = entry.get("final_validation_status", "")
            stage = "contacted" if fvs == "approved" else "disqualified"
        elif source == "09_email_sequence_export.csv":
            stage = "contacted"
        else:
            continue  # Skip campaign reports — no per-company data

        key = domain if domain else company_name.lower()
        if key not in outcome_companies:
            outcome_companies[key] = {
                "company_name": company_name,
                "domain": domain or None,
                "industry": "Unknown",
                "employee_count": 0,
                "deal_stage": stage,
                "source_channel": "pipeline_feedback",
            }
        else:
            # Upgrade deal stage if this source shows more advancement
            current_stage = outcome_companies[key].get("deal_stage", "contacted")
            if _stage_rank(stage) > _stage_rank(current_stage):
                outcome_companies[key]["deal_stage"] = stage

    for key, record in outcome_companies.items():
        domain = (record.get("domain") or "").strip().lower()
        if domain and domain in seen_domains:
            # Update existing deal's stage if feedback shows progression
            idx = seen_domains[domain]
            existing_stage = merged[idx].get("deal_stage", "contacted")
            new_stage = record.get("deal_stage", "contacted")
            if _stage_rank(new_stage) > _stage_rank(existing_stage):
                merged[idx] = dict(merged[idx])
                merged[idx]["deal_stage"] = new_stage
        else:
            if domain:
                seen_domains[domain] = len(merged)
            merged.append(record)

    log.info("Merged feedback: %d existing + new entries → %d total", len(existing_deals), len(merged))
    return merged


def save_feedback(merged: List[dict], output_path: str) -> None:
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2)
    log.info("Saved merged feedback to %s", output_path)


def _outcome_to_stage(outcome: str) -> str:
    mapping = {
        "replied": "meeting_booked",
        "meeting_booked": "meeting_booked",
        "proposal_sent": "proposal_sent",
        "closed_won": "closed_won",
        "closed_lost": "closed_lost",
        "no_response": "contacted",
    }
    return mapping.get(outcome, "contacted")


def _stage_rank(stage: str) -> int:
    ranks = {
        "prospecting": 0,
        "contacted": 1,
        "meeting_booked": 2,
        "proposal_sent": 3,
        "negotiation": 4,
        "closed_won": 5,
        "closed_lost": 5,
        "disqualified": 5,
    }
    return ranks.get(stage, 0)
