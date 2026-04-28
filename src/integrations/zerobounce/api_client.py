from __future__ import annotations

from typing import List

from src.integrations.zerobounce.base import ZeroBounceBase
from src.utils.retry import api_retry
from src.utils.logger import get_logger

log = get_logger(__name__)

BASE_URL = "https://api.zerobounce.net/v2"


class ZeroBounceAPIClient(ZeroBounceBase):
    """
    ZeroBounce API client — real integration stub.
    Set MOCK_MODE=false and provide ZEROBOUNCE_API_KEY to activate.
    """

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    @api_retry
    def validate_contacts(self, contacts: List[dict]) -> List[dict]:
        raise NotImplementedError(
            "ZeroBounce API client not yet implemented. "
            "Set MOCK_MODE=true or provide ZEROBOUNCE_API_KEY in .env."
        )
