from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List


class ValidityBase(ABC):
    @abstractmethod
    def get_campaign_metrics(self, file_path: str) -> List[dict]:
        """Return a list of campaign metric dicts from Validity (or mock source)."""
