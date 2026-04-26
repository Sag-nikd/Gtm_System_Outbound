from __future__ import annotations

from typing import List

from src.hubspot.hubspot_sync_mock import (
    create_hubspot_company_records,
    create_hubspot_contact_records,
)
from src.utils.logger import get_logger

log = get_logger(__name__)


class HubSpotMockClient:
    """
    HubSpot mock client — builds CRM-ready records as CSV-exportable dicts.
    Future: replace with HubSpot Private App API upsert calls.
    """

    def create_company_records(self, companies: List[dict]) -> List[dict]:
        log.info("HubSpot mock: building %d company records", len(companies))
        return create_hubspot_company_records(companies)

    def create_contact_records(
        self, contacts: List[dict], companies: List[dict]
    ) -> List[dict]:
        log.info("HubSpot mock: building contact records for %d contacts", len(contacts))
        return create_hubspot_contact_records(contacts, companies)
