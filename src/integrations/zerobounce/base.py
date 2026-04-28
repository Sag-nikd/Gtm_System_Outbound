from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List


class ZeroBounceBase(ABC):
    @abstractmethod
    def validate_contacts(self, contacts: List[dict]) -> List[dict]:
        """Validate email addresses and return contacts with zerobounce_status populated."""
