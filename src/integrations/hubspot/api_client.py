from __future__ import annotations

from typing import List

from src.utils.retry import api_retry
from src.utils.logger import get_logger

log = get_logger(__name__)

BASE_URL = "https://api.hubapi.com"


class HubSpotAPIClient:
    """
    HubSpot API client — real integration stub.
    Set MOCK_MODE=false and provide HUBSPOT_PRIVATE_APP_TOKEN to activate.
    """

    def __init__(self, token: str) -> None:
        self.token = token

    @api_retry
    def create_company_records(self, companies: List[dict]) -> List[dict]:
        raise NotImplementedError(
            "HubSpot API client not yet implemented. "
            "Set MOCK_MODE=true or provide HUBSPOT_PRIVATE_APP_TOKEN in .env."
        )

    @api_retry
    def create_contact_records(
        self, contacts: List[dict], companies: List[dict]
    ) -> List[dict]:
        raise NotImplementedError(
            "HubSpot API client not yet implemented. "
            "Set MOCK_MODE=true or provide HUBSPOT_PRIVATE_APP_TOKEN in .env."
        )
