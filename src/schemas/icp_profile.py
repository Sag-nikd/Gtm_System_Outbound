from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel


class IndustrySegment(BaseModel):
    name: str
    deal_count: int
    win_count: int
    loss_count: int
    conversion_rate: float
    avg_deal_value: float
    index: float  # conversion_rate / overall_conversion_rate


class SizeSegment(BaseModel):
    name: str
    deal_count: int
    win_count: int
    loss_count: int
    conversion_rate: float
    avg_deal_value: float
    index: float


class GeoSegment(BaseModel):
    name: str
    deal_count: int
    win_count: int
    loss_count: int
    conversion_rate: float
    avg_deal_value: float
    index: float


class VolumeSegment(BaseModel):
    name: str
    deal_count: int
    win_count: int
    loss_count: int
    conversion_rate: float
    avg_deal_value: float
    index: float


class TechSegment(BaseModel):
    name: str
    deal_count: int
    win_count: int
    loss_count: int
    conversion_rate: float
    avg_deal_value: float
    index: float


class LossReason(BaseModel):
    reason: str
    count: int
    percentage: float


class ICPProfile(BaseModel):
    total_deals_analyzed: int
    conversion_rate: float
    avg_deal_value: float
    avg_deal_cycle_days: float
    industry_breakdown: List[IndustrySegment]
    employee_size_breakdown: List[SizeSegment]
    geo_breakdown: List[GeoSegment]
    member_volume_breakdown: List[VolumeSegment]
    tech_stack_breakdown: List[TechSegment]
    top_converting_persona: str
    best_source_channel: str
    loss_reasons: List[LossReason]
    icp_summary: str
    confidence_level: str
    generated_at: str
