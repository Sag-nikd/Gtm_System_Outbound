from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List


class HubSpotBase(ABC):
    @abstractmethod
    def create_company_records(self, companies: List[dict]) -> List[dict]:
        """Create or update company records in HubSpot."""

    @abstractmethod
    def create_contact_records(self, contacts: List[dict], companies: List[dict]) -> List[dict]:
        """Create or update contact records in HubSpot, linked to their companies."""
