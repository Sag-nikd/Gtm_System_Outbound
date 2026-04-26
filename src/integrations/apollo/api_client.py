from __future__ import annotations

from typing import List

from src.utils.retry import api_retry
from src.utils.logger import get_logger

log = get_logger(__name__)

BASE_URL = "https://api.apollo.io/v1"


class ApolloAPIClient:
    """
    Apollo API client — real integration stub.
    Set MOCK_MODE=false and provide APOLLO_API_KEY to activate.
    """

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    @api_retry
    def get_companies(self, **filters) -> List[dict]:
        raise NotImplementedError(
            "Apollo API client not yet implemented. "
            "Set MOCK_MODE=true or provide APOLLO_API_KEY in .env."
        )

    @api_retry
    def get_contacts(self, **filters) -> List[dict]:
        raise NotImplementedError(
            "Apollo API client not yet implemented. "
            "Set MOCK_MODE=true or provide APOLLO_API_KEY in .env."
        )
