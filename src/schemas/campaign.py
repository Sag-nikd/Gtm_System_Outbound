from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class Campaign(BaseModel):
    """Schema for a campaign record used in health monitoring."""

    campaign_name: str
    emails_sent: int = 0
    open_rate: float = 0.0
    reply_rate: float = 0.0
    bounce_rate: float = 0.0
    spam_rate: float = 0.0
    domain_health_score: float = 100.0

    # Populated after health evaluation
    health_status: Optional[str] = None
    primary_issue: Optional[str] = None
    recommended_action: Optional[str] = None
