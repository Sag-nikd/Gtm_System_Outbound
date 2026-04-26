from __future__ import annotations

from typing import Any, Dict, List, Optional


def build_stage_metadata(stage_config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build Salesforce OpportunityStage metadata for Metadata API or dry-run output.
    In live mode, stages are added to the OpportunityStage picklist via Metadata API.
    Safer to add manually in Setup → Opportunity Stages.
    """
    probability = stage_config.get("probability", 0)
    if isinstance(probability, float) and probability <= 1.0:
        probability = int(probability * 100)

    return {
        "fullName": stage_config["name"],
        "label": stage_config.get("label", stage_config["name"]),
        "probability": probability,
        "forecastCategoryName": stage_config.get("forecast_category", "Pipeline"),
        "isActive": True,
        "isClosed": stage_config.get("name") in ("Closed Won", "Closed Lost"),
        "isWon": stage_config.get("name") == "Closed Won",
    }


def stage_exists(
    stage_name: str, existing_stages: List[Dict[str, Any]]
) -> bool:
    return any(
        s.get("MasterLabel") == stage_name or s.get("fullName") == stage_name
        for s in existing_stages
    )


def stage_has_conflict(
    stage_name: str,
    required_probability: float,
    existing_stages: List[Dict[str, Any]],
) -> bool:
    if isinstance(required_probability, float) and required_probability <= 1.0:
        required_pct = int(required_probability * 100)
    else:
        required_pct = int(required_probability)

    for s in existing_stages:
        name = s.get("MasterLabel") or s.get("fullName", "")
        if name == stage_name:
            existing_pct = int(s.get("Probability", s.get("probability", -1)))
            return existing_pct != required_pct
    return False
