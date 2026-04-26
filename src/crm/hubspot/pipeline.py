from __future__ import annotations

from typing import Any, Dict, List, Optional


def build_pipeline_payload(pipeline_config: Dict[str, Any]) -> Dict[str, Any]:
    """Build a HubSpot pipeline creation payload (without stages — added separately)."""
    return {
        "label": pipeline_config["name"],
        "displayOrder": pipeline_config.get("display_order", 0),
    }


def build_stage_payload(stage_config: Dict[str, Any]) -> Dict[str, Any]:
    """Build a HubSpot pipeline stage creation payload."""
    probability = stage_config.get("probability", 0.0)
    return {
        "label": stage_config["label"],
        "displayOrder": stage_config.get("display_order", 0),
        "metadata": {
            "probability": str(probability),
            "isClosed": str(probability in (0.0, 1.0)).lower(),
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
