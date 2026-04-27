from __future__ import annotations

from typing import Any, Dict, List, Optional


def build_pipeline_payload(pipeline_config: Dict[str, Any]) -> Dict[str, Any]:
    """Build a HubSpot pipeline creation payload with stages included.
    HubSpot v3 pipelines API requires at least one stage in the creation body."""
    stages = [build_stage_payload(s) for s in pipeline_config.get("stages", [])]
    return {
        "label": pipeline_config["name"],
        "displayOrder": pipeline_config.get("display_order", 0),
        "stages": stages,
    }


def build_stage_payload(stage_config: Dict[str, Any]) -> Dict[str, Any]:
    """Build a HubSpot pipeline stage creation payload.
    Note: isClosed is a read-only derived field — must not be sent in creation payloads."""
    probability = stage_config.get("probability", 0.0)
    # HubSpot expects probability as a plain number string e.g. "0.5" not "0.50"
    prob_str = str(round(float(probability), 4)).rstrip("0").rstrip(".")
    if "." not in prob_str:
        prob_str = prob_str  # integer like "0" or "1" is fine
    return {
        "label": stage_config["label"],
        "displayOrder": stage_config.get("display_order", 0),
        "metadata": {
            "probability": prob_str,
        },
    }


def pipeline_exists(
    pipeline_name: str, existing_pipelines: List[Dict[str, Any]]
) -> Optional[str]:
    """Return pipeline ID if a pipeline with this label exists, else None."""
    for p in existing_pipelines:
        if p.get("label") == pipeline_name:
            return p.get("id")
    return None


def stage_exists(
    stage_label: str, pipeline: Dict[str, Any]
) -> Optional[str]:
    """Return stage ID if a stage with this label exists in the pipeline, else None."""
    for stage in pipeline.get("stages", []):
        if stage.get("label") == stage_label:
            return stage.get("id")
    return None


def stage_has_conflict(
    stage_label: str,
    required_probability: float,
    pipeline: Dict[str, Any],
) -> bool:
    """Return True if stage exists but has a different probability."""
    for stage in pipeline.get("stages", []):
        if stage.get("label") == stage_label:
            existing_prob = float(
                stage.get("metadata", {}).get("probability", -1)
            )
            return existing_prob != required_probability
    return False
