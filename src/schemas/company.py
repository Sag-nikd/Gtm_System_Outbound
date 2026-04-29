from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class Company(BaseModel):
    """Schema for a company record as it flows through the GTM pipeline."""

    # Core firmographic fields — required at ingestion
    company_id: str
    company_name: str
    website: str
    domain: str
    industry: str
    employee_count: int
    revenue_range: str
    state: str
    primary_volume_metric: int
    secondary_volume_metric: int
    growth_signal: bool
    hiring_signal: bool
    tech_stack_signal: str
    ingestion_source: str
    ingestion_status: str

    # Populated after ICP scoring
    icp_score: Optional[float] = None
    icp_tier: Optional[str] = None
    total_volume: Optional[int] = None
    industry_score: Optional[float] = None
    volume_score: Optional[float] = None
    employee_count_score: Optional[float] = None
    growth_signal_score: Optional[float] = None
    hiring_signal_score: Optional[float] = None
    tech_stack_score: Optional[float] = None
    score_reason: Optional[str] = None
    tier_reason: Optional[str] = None

    # Populated after Clay enrichment
    enrichment_status: Optional[str] = None
    enrichment_source: Optional[str] = None
    recommended_personas: Optional[str] = None
    enriched_signal_summary: Optional[str] = None
    contact_discovery_approved: Optional[bool] = None
