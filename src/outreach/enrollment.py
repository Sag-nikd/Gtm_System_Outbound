"""
Outreach sequence enrollment module.
Enrolls approved contacts into outreach sequences via the configured platform API.

Future platforms: Apollo Sequences, Salesloft, Outreach.io, Instantly, Smartlead,
HubSpot Sequences, HeyReach (LinkedIn).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

import requests

from src.utils.logger import get_logger

log = get_logger(__name__)

_APOLLO_BASE_URL = "https://api.apollo.io/v1"


class EnrollmentBase(ABC):
    @abstractmethod
    def enroll_contacts(self, contacts: List[dict], seq_id: str) -> List[dict]:
        """Enroll approved contacts into the named sequence. Returns enriched contacts."""


class MockEnrollmentClient(EnrollmentBase):
    """Mock enrollment — marks contacts as enrolled without API calls."""

    def enroll_contacts(self, contacts: List[dict], seq_id: str) -> List[dict]:
        enrolled = [
            c for c in contacts if c.get("final_validation_status") == "approved"
        ]
        for ct in enrolled:
            ct["sequence_enrolled"] = True
            ct["sequence_id"] = seq_id
            ct["sequence_status"] = "active"
        log.info(
            "Mock enrollment: %d/%d contacts enrolled in sequence '%s'",
            len(enrolled), len(contacts), seq_id,
        )
        return contacts


class ApolloSequenceClient(EnrollmentBase):
    """
    Apollo Sequences enrollment client.
    Calls Apollo v1 API to add contacts to an existing sequence.
    Requires APOLLO_API_KEY and a valid sequence_id from your Apollo account.
    """

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def enroll_contacts(self, contacts: List[dict], seq_id: str) -> List[dict]:
        approved = [c for c in contacts if c.get("final_validation_status") == "approved"]
        enrolled = failed = 0

        for ct in approved:
            try:
                self._add_to_sequence(ct, seq_id)
                ct["sequence_enrolled"] = True
                ct["sequence_id"] = seq_id
                ct["sequence_status"] = "active"
                enrolled += 1
            except (requests.HTTPError, requests.RequestException) as exc:
                log.warning(
                    "Enrollment failed for %s <%s>: %s",
                    ct.get("first_name", ""), ct.get("email", ""), exc,
                )
                ct["sequence_enrolled"] = False
                ct["sequence_status"] = "error"
                failed += 1

        log.info(
            "Apollo enrollment: %d enrolled, %d failed (sequence=%s)",
            enrolled, failed, seq_id,
        )
        return contacts

    def _add_to_sequence(self, contact: dict, seq_id: str) -> None:
        payload = {
            "api_key": self.api_key,
            "sequence_id": seq_id,
            "contact_email": contact.get("email", ""),
            "contact_first_name": contact.get("first_name", ""),
            "contact_last_name": contact.get("last_name", ""),
        }
        resp = requests.post(
            f"{_APOLLO_BASE_URL}/emailer_campaigns/{seq_id}/add_contact_ids",
            json=payload,
            timeout=20,
        )
        resp.raise_for_status()


def get_enrollment_client(api_key: str = "", mock: bool = True) -> EnrollmentBase:
    """Factory: return the appropriate enrollment client based on mode."""
    if mock or not api_key:
        return MockEnrollmentClient()
    return ApolloSequenceClient(api_key)
