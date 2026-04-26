from __future__ import annotations

from typing import List

from src.utils.retry import api_retry
from src.utils.logger import get_logger

log = get_logger(__name__)


class ValidityAPIClient:
    """
    Validity API client — real integration stub.
    Set MOCK_MODE=false and provide VALIDITY_API_KEY to activate.
    """

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    @api_retry
    def get_campaign_metrics(self, **kwargs) -> List[dict]:
        raise NotImplementedError(
            "Validity API client not yet implemented. "
            "Set MOCK_MODE=true or provide VALIDITY_API_KEY in .env."
        )
