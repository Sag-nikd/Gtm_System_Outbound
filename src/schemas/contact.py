from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class Contact(BaseModel):
    """Schema for a contact record as it flows through the GTM pipeline."""

    # Core fields — required at discovery
    contact_id: str
    company_id: str
    first_name: str
    last_name: str
    title: str
    email: str
    linkedin_url: str
    persona_type: str

    # Populated after contact discovery
    company_name: Optional[str] = None
    icp_tier: Optional[str] = None
    contact_source: Optional[str] = None
    contact_discovery_status: Optional[str] = None

    # Populated after ZeroBounce validation
    zerobounce_status: Optional[str] = None
    zerobounce_reason: Optional[str] = None

    # Populated after NeverBounce validation
    neverbounce_status: Optional[str] = None
    neverbounce_reason: Optional[str] = None

    # Populated after final validation decision
    final_validation_status: Optional[str] = None
    final_validation_reason: Optional[str] = None
