from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List


class NeverBounceBase(ABC):
    @abstractmethod
    def validate_contacts(self, contacts: List[dict]) -> List[dict]:
        """Second-pass email validation; returns contacts with neverbounce_status populated."""
