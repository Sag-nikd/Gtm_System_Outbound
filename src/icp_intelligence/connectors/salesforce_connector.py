from __future__ import annotations

from typing import List, Optional

from src.icp_intelligence.connectors.base import ICPDataConnectorBase
from src.utils.logger import get_logger

log = get_logger(__name__)

_SF_STAGE_MAP = {
    "prospecting": "prospecting",
    "qualification": "contacted",
    "needs analysis": "contacted",
    "value proposition": "meeting_booked",
    "id. decision makers": "meeting_booked",
    "perception analysis": "proposal_sent",
    "proposal/price quote": "proposal_sent",
    "negotiation/review": "negotiation",
    "closed won": "closed_won",
    "closed lost": "closed_lost",
}


class SalesforceICPConnector(ICPDataConnectorBase):
    """Salesforce CRM connector stub. API methods raise NotImplementedError."""

    def connect(self) -> bool:
        raise NotImplementedError(
            "SalesforceICPConnector.connect() requires ICP_DATA_SOURCE=salesforce "
            "and valid Salesforce credentials."
        )

    def pull_deals(self, since: Optional[str] = None) -> List[dict]:
        raise NotImplementedError(
            "SalesforceICPConnector.pull_deals() not yet implemented. "
            "Export Opportunities from Salesforce Reports and use CSVConnector."
        )

    def pull_pipeline(self, since: Optional[str] = None) -> List[dict]:
        raise NotImplementedError("SalesforceICPConnector.pull_pipeline() not yet implemented.")

    def pull_companies(self) -> List[dict]:
        raise NotImplementedError("SalesforceICPConnector.pull_companies() not yet implemented.")

    def map_to_deal_record(self, raw: dict) -> dict:
        """Map Salesforce opportunity fields to DealRecord schema."""
        raw_amount = raw.get("Amount", "")
        try:
            deal_value = float(raw_amount) if raw_amount else None
        except (TypeError, ValueError):
            deal_value = None

        sf_stage = (raw.get("StageName") or "").lower()
        deal_stage = _SF_STAGE_MAP.get(sf_stage, "contacted")

        raw_emp = raw.get("NumberOfEmployees", "")
        try:
            employee_count = int(raw_emp) if raw_emp else 0
        except (TypeError, ValueError):
            employee_count = 0

        lead_source_map = {
            "Cold Email": "outbound_email",
            "Web": "inbound",
            "Referral": "inbound_referral",
            "LinkedIn": "outbound_linkedin",
            "Conference": "conference",
        }
        source = lead_source_map.get(raw.get("LeadSource", ""), "unknown")

        # Salesforce Name is usually "Company - Deal description"
        name = raw.get("Name", "")
        company_name = name.split(" - ")[0].strip() if " - " in name else name

        return {
            "company_name": company_name,
            "domain": raw.get("Website__c", ""),
            "industry": raw.get("Industry__c", raw.get("Industry", "Unknown")),
            "employee_count": employee_count,
            "deal_stage": deal_stage,
            "deal_value": deal_value,
            "closed_date": raw.get("CloseDate", ""),
            "source_channel": source,
            "tech_stack": raw.get("Tech_Stack__c", ""),
        }
