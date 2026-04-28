from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List


class ApolloBase(ABC):
    @abstractmethod
    def get_companies(self, file_path: str) -> List[dict]:
        """Return a list of company dicts from Apollo (or mock source)."""

    @abstractmethod
    def get_contacts(self, file_path: str) -> List[dict]:
        """Return a list of contact dicts from Apollo (or mock source)."""
