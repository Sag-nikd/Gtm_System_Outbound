from __future__ import annotations

from typing import List

from src.integrations.neverbounce.base import NeverBounceBase
from src.utils.retry import api_retry
from src.utils.logger import get_logger

log = get_logger(__name__)

BASE_URL = "https://api.neverbounce.com/v4"


class NeverBounceAPIClient(NeverBounceBase):
    """
    NeverBounce API client — real integration stub.
    Set MOCK_MODE=false and provide NEVERBOUNCE_API_KEY to activate.
    """

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    @api_retry
    def validate_contacts(self, contacts: List[dict]) -> List[dict]:
        raise NotImplementedError(
            "NeverBounce API client not yet implemented. "
            "Set MOCK_MODE=true or provide NEVERBOUNCE_API_KEY in .env."
        )
