from __future__ import annotations

from typing import List

from pydantic import BaseModel


class DimensionDrift(BaseModel):
    dimension: str
    current_weight: float
    recommended_weight: float
    weight_delta: float
    drift_direction: str
    explanation: str


class ICPDriftReport(BaseModel):
    drift_detected: bool
    drift_severity: str
    dimension_drifts: List[DimensionDrift]
    industry_changes: List[dict]
    threshold_changes: List[dict]
    action_items: List[str]
    should_auto_update: bool
    generated_at: str
