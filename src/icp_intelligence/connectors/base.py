from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional


class ICPDataConnectorBase(ABC):
    """Abstract base class for ICP data connectors."""

    @abstractmethod
    def connect(self) -> bool:
        """Authenticate and verify connection. Returns True on success."""
        ...

    @abstractmethod
    def pull_deals(self, since: Optional[str] = None) -> List[dict]:
        """Pull deal/opportunity records, optionally filtered by date string."""
        ...

    @abstractmethod
    def pull_pipeline(self, since: Optional[str] = None) -> List[dict]:
        """Pull active pipeline records."""
        ...

    @abstractmethod
    def pull_companies(self) -> List[dict]:
        """Pull company/account records."""
        ...

    @abstractmethod
    def map_to_deal_record(self, raw: dict) -> dict:
        """Transform CRM-specific fields to the DealRecord schema."""
        ...
