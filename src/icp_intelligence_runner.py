"""
ICP Intelligence Runner — Stage 0 orchestrator.
Runs the full ICP intelligence pipeline: ingest → analyze → generate rules
→ detect drift → generate Apollo config → write reports.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
from typing import Optional

from src.icp_intelligence.data_ingestion import load_deal_data, load_pipeline_data, load_tam_data
from src.icp_intelligence.profile_analyzer import analyze_icp
from src.icp_intelligence.rules_generator import (
    generate_icp_rules, save_icp_rules, save_icp_rules_with_history,
)
from src.icp_intelligence.drift_detector import detect_drift
from src.icp_intelligence.apollo_query_builder import build_apollo_query, save_apollo_config
from src.icp_intelligence.feedback_ingestor import (
    collect_pipeline_feedback, merge_feedback_with_deals,
)
from src.scoring.icp_scoring import load_icp_rules
from src.utils.logger import get_logger

log = get_logger(__name__)


def run_icp_intelligence(
    deal_data_path: str,
    pipeline_data_path: Optional[str] = None,
    tam_data_path: Optional[str] = None,
    feedback_dir: Optional[str] = None,
    config_dir: Optional[str] = None,
    output_dir: Optional[str] = None,
) -> dict:
    from src.config.settings import settings
    if config_dir is None:
        config_dir = settings.CONFIG_DIR
    if output_dir is None:
        output_dir = settings.OUTPUT_DIR

    os.makedirs(output_dir, exist_ok=True)
    os.makedirs(config_dir, exist_ok=True)

    log.info("Stage 0: ICP Intelligence starting — deals=%s", deal_data_path)

    # 1. Load data
    deals = load_deal_data(deal_data_path)
    pipeline = load_pipeline_data(pipeline_data_path) if pipeline_data_path else []
    tam = load_tam_data(tam_data_path) if tam_data_path else []

    # 2. Optionally merge pipeline feedback
    if feedback_dir:
        feedback = collect_pipeline_feedback(feedback_dir)
        deals = merge_feedback_with_deals(feedback, deals)
        log.info("After feedback merge: %d deal records", len(deals))

    # 3. Analyze ICP
    profile = analyze_icp(deals, pipeline=pipeline, tam=tam)
    log.info("ICP profile: confidence=%s, conversion=%.0f%%",
             profile.confidence_level, profile.conversion_rate * 100)

    # 4. Generate rules
    recommended_rules = generate_icp_rules(profile)

    # 5. Detect drift against current config/icp_rules.json
    current_rules_path = os.path.join(config_dir, "icp_rules.json")
    actions_taken = []
    try:
        current_rules = load_icp_rules(current_rules_path)
        drift_report = detect_drift(current_rules, recommended_rules, profile)
        log.info("Drift: severity=%s, should_auto_update=%s",
                 drift_report.drift_severity, drift_report.should_auto_update)

        if drift_report.should_auto_update:
            save_icp_rules_with_history(recommended_rules, config_dir)
            actions_taken.append("auto_updated_icp_rules")
            log.info("Auto-updated config/icp_rules.json (minor drift + high confidence)")
        else:
            # Save as recommended for human review
            rec_path = os.path.join(config_dir, "icp_rules_recommended.json")
            save_icp_rules(recommended_rules, rec_path)
            save_icp_rules_with_history(recommended_rules, config_dir)
            actions_taken.append("saved_recommended_rules_for_review")
            log.info("Saved icp_rules_recommended.json for human review (drift=%s)",
                     drift_report.drift_severity)

    except FileNotFoundError:
        # No existing rules — save directly and create history
        save_icp_rules_with_history(recommended_rules, config_dir)
        drift_report = None
        actions_taken.append("created_initial_icp_rules")
        log.info("No existing icp_rules.json — created initial rules")

    # 6. Build Apollo query config
    apollo_config = build_apollo_query(profile, recommended_rules, deals=deals, tam=tam or None)
    apollo_config_path = os.path.join(config_dir, "apollo_query_config.json")
    save_apollo_config(apollo_config, apollo_config_path)

    # 7. Write 00_icp_intelligence_report.json
    def _drift_dict(dr):
        if dr is None:
            return None
        d = dr.model_dump()
        return d

    report = {
        "profile": profile.model_dump(),
        "drift_report": _drift_dict(drift_report),
        "apollo_config": apollo_config.model_dump(),
        "actions_taken": actions_taken,
    }
    report_path = os.path.join(output_dir, "00_icp_intelligence_report.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    log.info("Wrote %s", report_path)

    # 8. Write 00_icp_summary.csv (one row per industry)
    summary_path = os.path.join(output_dir, "00_icp_summary.csv")
    with open(summary_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "industry", "deal_count", "win_count", "loss_count",
            "conversion_rate", "avg_deal_value", "index",
        ])
        writer.writeheader()
        for seg in profile.industry_breakdown:
            writer.writerow({
                "industry": seg.name,
                "deal_count": seg.deal_count,
                "win_count": seg.win_count,
                "loss_count": seg.loss_count,
                "conversion_rate": round(seg.conversion_rate, 4),
                "avg_deal_value": round(seg.avg_deal_value, 2),
                "index": round(seg.index, 4),
            })
    log.info("Wrote %s", summary_path)

    log.info("Stage 0 complete — ICP summary: %s", profile.icp_summary)

    return {
        "profile": profile,
        "rules": recommended_rules,
        "drift_report": drift_report,
        "apollo_config": apollo_config,
        "actions_taken": actions_taken,
    }


def _cli():
    parser = argparse.ArgumentParser(description="Run ICP Intelligence Engine (Stage 0)")
    parser.add_argument("--deals", required=True, help="Path to deal history JSON/CSV")
    parser.add_argument("--pipeline", default=None, help="Path to pipeline data JSON/CSV")
    parser.add_argument("--tam", default=None, help="Path to TAM universe JSON/CSV")
    parser.add_argument("--feedback-dir", default=None, help="Output dir from previous pipeline run")
    args = parser.parse_args()

    result = run_icp_intelligence(
        deal_data_path=args.deals,
        pipeline_data_path=args.pipeline,
        tam_data_path=args.tam,
        feedback_dir=args.feedback_dir,
    )
    print("ICP Intelligence complete.")
    print("  Confidence: {}".format(result["profile"].confidence_level))
    print("  Summary: {}".format(result["profile"].icp_summary))
    print("  Actions: {}".format(", ".join(result["actions_taken"])))


if __name__ == "__main__":
    _cli()
