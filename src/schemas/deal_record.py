from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class DealRecord(BaseModel):
    company_name: str
    industry: str
    employee_count: int
    deal_stage: str

    domain: Optional[str] = None
    sub_industry: Optional[str] = None
    revenue_range: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = "US"
    medicaid_members: Optional[int] = None
    medicare_members: Optional[int] = None
    tech_stack: Optional[str] = None
    deal_value: Optional[float] = None
    deal_cycle_days: Optional[int] = None
    source_channel: Optional[str] = None
    contact_title: Optional[str] = None
    contact_persona: Optional[str] = None
    meeting_booked: Optional[bool] = None
    proposal_sent: Optional[bool] = None
    closed_date: Optional[str] = None
    loss_reason: Optional[str] = None


class PipelineRecord(BaseModel):
    company_name: str
    deal_stage: str

    domain: Optional[str] = None
    deal_value: Optional[float] = None
    days_in_stage: Optional[int] = None
    last_activity_date: Optional[str] = None
    assigned_rep: Optional[str] = None
    engagement_score: Optional[float] = None


class TAMRecord(BaseModel):
    company_name: str
    industry: str

    domain: Optional[str] = None
    sub_industry: Optional[str] = None
    employee_count: Optional[int] = None
    state: Optional[str] = None
    country: Optional[str] = "US"
    medicaid_members: Optional[int] = None
    medicare_members: Optional[int] = None
    tech_stack: Optional[str] = None
    is_current_customer: Optional[bool] = False
