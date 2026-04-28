from __future__ import annotations

from typing import List

from src.hubspot.hubspot_sync_mock import (
    create_hubspot_company_records,
    create_hubspot_contact_records,
)
from src.integrations.hubspot.base import HubSpotBase
from src.utils.logger import get_logger

log = get_logger(__name__)


class HubSpotMockClient(HubSpotBase):
    """
    HubSpot mock client — builds CRM-ready records as CSV-exportable dicts.
    Future: replace with HubSpot Private App API upsert calls.
    """

    def upsert_companies(self, companies: List[dict]) -> List[dict]:
        seen_domains: set = set()
        deduped = []
        for co in companies:
            domain = co.get("domain", "")
            if domain and domain in seen_domains:
                log.warning("HubSpot mock: duplicate domain '%s' — skipping", domain)
                continue
            if domain:
                seen_domains.add(domain)
            deduped.append(co)
        log.info(
            "HubSpot mock: building %d company records (%d duplicates removed)",
            len(deduped), len(companies) - len(deduped),
        )
        return create_hubspot_company_records(deduped)

    def upsert_contacts(self, contacts: List[dict], companies: List[dict]) -> List[dict]:
        seen_emails: set = set()
        deduped = []
        for ct in contacts:
            email = ct.get("email", "")
            if email and email in seen_emails:
                log.warning("HubSpot mock: duplicate email '%s' — skipping", email)
                continue
            if email:
                seen_emails.add(email)
            deduped.append(ct)
        log.info(
            "HubSpot mock: building contact records for %d contacts (%d duplicates removed)",
            len(deduped), len(contacts) - len(deduped),
        )
        return create_hubspot_contact_records(deduped, companies)
