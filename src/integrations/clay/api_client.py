from __future__ import annotations

from typing import List

import requests

from src.integrations.clay.base import ClayBase
from src.utils.logger import get_logger

log = get_logger(__name__)

_BASE_URL = "https://api.clay.com/v1"


class ClayAPIClient(ClayBase):
    """
    Clay API client — calls Clay enrichment API for waterfall persona/signal data.
    Requires CLAY_API_KEY. Set CLAY_MODE=live to activate.
    """

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    def enrich_accounts(self, companies: List[dict]) -> List[dict]:
        """Enrich companies via Clay API; falls back to local persona mapping on error."""
        from src.enrichment.clay_mock_enrichment import (
            PERSONA_MAP, DEFAULT_PERSONAS, _get_enriched_signal_summary, APPROVED_TIERS
        )
        enriched = []
        api_failures = 0

        for company in companies:
            try:
                result = self._enrich_single(company)
                enriched.append(result)
            except (requests.HTTPError, requests.RequestException) as exc:
                api_failures += 1
                log.warning(
                    "Clay API: enrichment failed for %s, using local fallback: %s",
                    company.get("company_id", "?"), exc,
                )
                enriched.append(self._local_fallback(company, PERSONA_MAP, DEFAULT_PERSONAS,
                                                      _get_enriched_signal_summary, APPROVED_TIERS))

        if api_failures:
            log.warning("Clay API: %d/%d enrichments used local fallback", api_failures, len(companies))
        return enriched

    def _enrich_single(self, company: dict) -> dict:
        """Call Clay API to enrich one company. Raises on HTTP error."""
        payload = {
            "domain": company.get("domain", company.get("website", "")),
            "company_name": company.get("company_name", ""),
            "industry": company.get("industry", ""),
        }
        resp = requests.post(
            f"{_BASE_URL}/enrichment/company",
            headers=self._headers,
            json=payload,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return self._apply_clay_response(company, data)

    def _apply_clay_response(self, company: dict, data: dict) -> dict:
        personas = data.get("recommended_personas", [])
        if not personas:
            from src.enrichment.clay_mock_enrichment import PERSONA_MAP, DEFAULT_PERSONAS
            personas = PERSONA_MAP.get(company.get("industry", ""), DEFAULT_PERSONAS)

        company["enrichment_status"] = "enriched"
        company["enrichment_source"] = "clay_api"
        company["recommended_personas"] = ", ".join(personas) if isinstance(personas, list) else personas
        company["enriched_signal_summary"] = data.get("signal_summary", "")
        company["contact_discovery_approved"] = company.get("icp_tier", "") in {"Tier 1", "Tier 2"}
        return company

    def _local_fallback(self, company: dict, persona_map, default_personas,
                        signal_summary_fn, approved_tiers) -> dict:
        industry = company.get("industry", "")
        tier = company.get("icp_tier", "Disqualified")
        personas = persona_map.get(industry, default_personas)
        company["enrichment_status"] = "enriched"
        company["enrichment_source"] = "clay_api_fallback"
        company["recommended_personas"] = ", ".join(personas)
        company["enriched_signal_summary"] = signal_summary_fn(company)
        company["contact_discovery_approved"] = tier in approved_tiers
        return company
