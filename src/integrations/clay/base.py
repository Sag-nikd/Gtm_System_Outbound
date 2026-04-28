from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List


class ClayBase(ABC):
    @abstractmethod
    def enrich_accounts(self, companies: List[dict]) -> List[dict]:
        """Enrich a list of company dicts with persona and signal data."""
