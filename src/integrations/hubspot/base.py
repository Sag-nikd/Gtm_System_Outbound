from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List


class HubSpotBase(ABC):
    @abstractmethod
    def upsert_companies(self, companies: List[dict]) -> List[dict]:
        """Deduplicate by domain, then create or update company records in HubSpot."""

    @abstractmethod
    def upsert_contacts(self, contacts: List[dict], companies: List[dict]) -> List[dict]:
        """Deduplicate by email, then create or update contact records in HubSpot."""
