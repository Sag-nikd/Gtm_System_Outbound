from __future__ import annotations

from typing import List

from src.enrichment.clay_mock_enrichment import enrich_accounts
from src.utils.logger import get_logger

log = get_logger(__name__)


class ClayMockClient:
    """
    Clay mock client — applies persona mapping and signal enrichment locally.
    Future: replace with Clay enrichment workflows and waterfall enrichment API.
    """

    def enrich_accounts(self, companies: List[dict]) -> List[dict]:
        log.info("Clay mock: enriching %d accounts", len(companies))
        enriched = enrich_accounts(companies)
        approved = sum(1 for c in enriched if c.get("contact_discovery_approved"))
        log.info("Clay mock: %d accounts enriched, %d approved for contact discovery",
                 len(enriched), approved)
        return enriched
