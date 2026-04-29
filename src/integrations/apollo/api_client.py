from __future__ import annotations

from typing import List

import requests

from src.integrations.apollo.base import ApolloBase
from src.utils.retry import api_retry
from src.utils.logger import get_logger

log = get_logger(__name__)

_BASE_URL = "https://api.apollo.io/v1"
_PER_PAGE = 100


class ApolloAPIClient(ApolloBase):
    """
    Apollo API client — calls Apollo.io v1 REST API.
    Requires APOLLO_API_KEY. Set APOLLO_MODE=live (or MOCK_MODE=false) to activate.
    """

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    @api_retry
    def get_companies(self, file_path: str) -> List[dict]:
        """Search Apollo for organizations and return as internal company dicts."""
        payload = {"api_key": self.api_key, "per_page": _PER_PAGE, "page": 1}
        resp = requests.post(
            f"{_BASE_URL}/mixed_companies/search", json=payload, timeout=30
        )
        resp.raise_for_status()
        data = resp.json()
        orgs = data.get("accounts", data.get("organizations", []))
        log.info("Apollo API: fetched %d companies", len(orgs))
        return [self._map_company(o) for o in orgs]

    @api_retry
    def get_contacts(self, file_path: str) -> List[dict]:
        """Search Apollo for people and return as internal contact dicts."""
        payload = {"api_key": self.api_key, "per_page": _PER_PAGE, "page": 1}
        resp = requests.post(
            f"{_BASE_URL}/mixed_people/search", json=payload, timeout=30
        )
        resp.raise_for_status()
        data = resp.json()
        people = data.get("people", [])
        log.info("Apollo API: fetched %d contacts", len(people))
        return [self._map_contact(p) for p in people]

    def _map_company(self, org: dict) -> dict:
        tech = org.get("technology_names") or []
        return {
            "company_id": org.get("id", ""),
            "company_name": org.get("name", ""),
            "website": org.get("website_url", ""),
            "industry": org.get("industry", ""),
            "employee_count": int(org.get("estimated_num_employees") or 0),
            "revenue_range": org.get("annual_revenue_printed", ""),
            "state": (org.get("hq_location") or {}).get("state", ""),
            "primary_volume_metric": 0,
            "secondary_volume_metric": 0,
            "growth_signal": bool(org.get("organization_job_10_day_growth_rate")),
            "hiring_signal": bool(org.get("organization_latest_funding_stage")),
            "tech_stack_signal": tech[0] if tech else "Unknown",
        }

    def _map_contact(self, person: dict) -> dict:
        org = person.get("organization") or {}
        return {
            "contact_id": person.get("id", ""),
            "company_id": org.get("id", ""),
            "first_name": person.get("first_name", ""),
            "last_name": person.get("last_name", ""),
            "title": person.get("title", ""),
            "email": person.get("email", ""),
            "linkedin_url": person.get("linkedin_url", ""),
            "persona_type": person.get("title", ""),
        }
