from __future__ import annotations

from typing import List

from src.integrations.zerobounce.base import ZeroBounceBase
from src.validation.email_validation_mock import validate_contacts
from src.utils.logger import get_logger

log = get_logger(__name__)


class ZeroBounceMockClient(ZeroBounceBase):
    """
    ZeroBounce mock client — simulates email deliverability validation locally.
    Also populates NeverBounce fields in one pass (mock architecture limitation).
    Future: replace with real ZeroBounce API calls (separate from NeverBounce).
    """

    def validate_contacts(self, contacts: List[dict]) -> List[dict]:
        log.info("ZeroBounce mock: validating %d contacts", len(contacts))
        validated = validate_contacts(contacts)
        valid = sum(1 for c in validated if c.get("zerobounce_status") == "valid")
        log.info("ZeroBounce mock: %d/%d valid", valid, len(validated))
        return validated
