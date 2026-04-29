from __future__ import annotations

from typing import List

import requests

from src.integrations.zerobounce.base import ZeroBounceBase
from src.utils.retry import api_retry
from src.utils.logger import get_logger

log = get_logger(__name__)

_BASE_URL = "https://api.zerobounce.net/v2"
_BATCH_SIZE = 100

_STATUS_MAP = {
    "valid": "valid",
    "invalid": "invalid",
    "catch-all": "risky",
    "unknown": "unknown",
    "spamtrap": "invalid",
    "abuse": "invalid",
    "do_not_mail": "invalid",
}


class ZeroBounceAPIClient(ZeroBounceBase):
    """
    ZeroBounce API client — calls ZeroBounce v2 batch validation endpoint.
    Requires ZEROBOUNCE_API_KEY. Set ZEROBOUNCE_MODE=live (or MOCK_MODE=false) to activate.
    """

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    @api_retry
    def validate_contacts(self, contacts: List[dict]) -> List[dict]:
        """Validate all contact emails via ZeroBounce batch API. Modifies contacts in place."""
        results: List[dict] = []
        for i in range(0, len(contacts), _BATCH_SIZE):
            batch = contacts[i: i + _BATCH_SIZE]
            results.extend(self._validate_batch(batch))
        return results

    def _validate_batch(self, contacts: List[dict]) -> List[dict]:
        with_email = [c for c in contacts if c.get("email")]
        without_email = [c for c in contacts if not c.get("email")]

        for c in without_email:
            c["zerobounce_status"] = "unknown"
            c["neverbounce_status"] = "unknown"
            c["final_validation_status"] = "suppressed"

        if not with_email:
            return contacts

        payload = {
            "api_key": self.api_key,
            "email_batch": [{"email_address": c["email"]} for c in with_email],
        }
        resp = requests.post(f"{_BASE_URL}/validatebatch", json=payload, timeout=30)
        resp.raise_for_status()

        data = resp.json()
        status_by_email = {
            item["address"]: _STATUS_MAP.get(item.get("status", "unknown"), "unknown")
            for item in data.get("email_batch", [])
        }

        for c in with_email:
            zb_status = status_by_email.get(c["email"], "unknown")
            c["zerobounce_status"] = zb_status
            c["neverbounce_status"] = zb_status
            if zb_status == "valid":
                c["final_validation_status"] = "approved"
            elif zb_status == "risky":
                c["final_validation_status"] = "review"
            else:
                c["final_validation_status"] = "suppressed"

        log.info(
            "ZeroBounce API: validated %d emails — %d valid",
            len(with_email),
            sum(1 for c in with_email if c.get("zerobounce_status") == "valid"),
        )
        return without_email + with_email
