from __future__ import annotations

from typing import List, Optional

from src.icp_intelligence.connectors.base import ICPDataConnectorBase
from src.utils.logger import get_logger

log = get_logger(__name__)

_STAGE_MAP = {
    "appointmentscheduled": "meeting_booked",
    "qualifiedtobuy": "proposal_sent",
    "presentationscheduled": "meeting_booked",
    "decisionmakerboughtin": "negotiation",
    "contractsent": "negotiation",
    "closedwon": "closed_won",
    "closedlost": "closed_lost",
}


class HubSpotICPConnector(ICPDataConnectorBase):
    """HubSpot CRM connector stub. API methods raise NotImplementedError."""

    def connect(self) -> bool:
        raise NotImplementedError(
            "HubSpotICPConnector.connect() requires ICP_DATA_SOURCE=hubspot "
            "and HUBSPOT_PRIVATE_APP_TOKEN to be set."
        )

    def pull_deals(self, since: Optional[str] = None) -> List[dict]:
        raise NotImplementedError(
            "HubSpotICPConnector.pull_deals() not yet implemented. "
            "Use CSVConnector or export deals from HubSpot manually."
        )

    def pull_pipeline(self, since: Optional[str] = None) -> List[dict]:
        raise NotImplementedError("HubSpotICPConnector.pull_pipeline() not yet implemented.")

    def pull_companies(self) -> List[dict]:
        raise NotImplementedError("HubSpotICPConnector.pull_companies() not yet implemented.")

    def map_to_deal_record(self, raw: dict) -> dict:
        """Map HubSpot deal properties to DealRecord schema."""
        raw_amount = raw.get("amount", "")
        try:
            deal_value = float(raw_amount) if raw_amount else None
        except (TypeError, ValueError):
            deal_value = None

        hs_stage = (raw.get("dealstage") or "").lower().replace(" ", "")
        deal_stage = _STAGE_MAP.get(hs_stage, "contacted")

        raw_emp = raw.get("employee_count", "")
        try:
            employee_count = int(raw_emp) if raw_emp else 0
        except (TypeError, ValueError):
            employee_count = 0

        source_map = {
            "DIRECT_TRAFFIC": "inbound",
            "ORGANIC_SEARCH": "inbound",
            "PAID_SEARCH": "paid",
            "EMAIL_MARKETING": "outbound_email",
            "SOCIAL_MEDIA": "outbound_linkedin",
        }
        source = source_map.get(raw.get("hs_analytics_source", ""), "unknown")

        return {
            "company_name": raw.get("dealname", ""),
            "domain": raw.get("domain", ""),
            "industry": raw.get("industry", "Unknown"),
            "employee_count": employee_count,
            "deal_stage": deal_stage,
            "deal_value": deal_value,
            "closed_date": raw.get("closedate", ""),
            "source_channel": source,
            "tech_stack": raw.get("tech_stack", ""),
        }
