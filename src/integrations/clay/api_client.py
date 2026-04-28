from __future__ import annotations

from typing import List

from src.integrations.clay.base import ClayBase
from src.utils.retry import api_retry
from src.utils.logger import get_logger

log = get_logger(__name__)


class ClayAPIClient(ClayBase):
    """
    Clay API client — real integration stub.
    Set MOCK_MODE=false and provide CLAY_API_KEY to activate.
    """

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    @api_retry
    def enrich_accounts(self, companies: List[dict]) -> List[dict]:
        raise NotImplementedError(
            "Clay API client not yet implemented. "
            "Set MOCK_MODE=true or provide CLAY_API_KEY in .env."
        )
