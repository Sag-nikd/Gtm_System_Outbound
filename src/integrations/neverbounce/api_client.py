from __future__ import annotations

from typing import List

import requests

from src.integrations.neverbounce.base import NeverBounceBase
from src.utils.retry import api_retry
from src.utils.logger import get_logger

log = get_logger(__name__)

_BASE_URL = "https://api.neverbounce.com/v4"

_STATUS_MAP = {
    "valid": "valid",
    "invalid": "invalid",
    "catchall": "risky",
    "unknown": "unknown",
    "disposable": "invalid",
    "bad_syntax": "invalid",
}


class NeverBounceAPIClient(NeverBounceBase):
    """
    NeverBounce API client — second-pass email validation via single-check endpoint.
    Requires NEVERBOUNCE_API_KEY. Set NEVERBOUNCE_MODE=live to activate.
    """

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    @api_retry
    def validate_contacts(self, contacts: List[dict]) -> List[dict]:
        """Re-validate each contact email via NeverBounce single-check. Modifies in place."""
        validated = []
        overridden = 0
        for ct in contacts:
            email = ct.get("email", "")
            if not email:
                validated.append(ct)
                continue
            nb_status = self._check_email(email)
            ct["neverbounce_status"] = nb_status
            # Only override final_validation_status when NeverBounce strongly disagrees
            if nb_status == "invalid" and ct.get("final_validation_status") == "approved":
                ct["final_validation_status"] = "suppressed"
                ct["final_validation_reason"] = "NeverBounce: invalid"
                overridden += 1
            elif nb_status == "valid" and ct.get("final_validation_status") == "suppressed":
                ct["final_validation_status"] = "review"
                ct["final_validation_reason"] = "NeverBounce: valid (was suppressed)"
            validated.append(ct)

        approved = sum(1 for c in validated if c.get("final_validation_status") == "approved")
        log.info(
            "NeverBounce API: %d contacts checked, %d status overrides, %d approved",
            len(validated), overridden, approved,
        )
        return validated

    def _check_email(self, email: str) -> str:
        """Single-check one email. Returns mapped status string."""
        try:
            resp = requests.get(
                f"{_BASE_URL}/single/check",
                params={"email": email, "key": self.api_key},
                timeout=15,
            )
            resp.raise_for_status()
            raw_status = resp.json().get("result", "unknown")
            return _STATUS_MAP.get(raw_status, "unknown")
        except (requests.HTTPError, requests.RequestException) as exc:
            log.warning("NeverBounce check failed for %s: %s", email, exc)
            return "unknown"
