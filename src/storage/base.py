from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List, Optional


class StorageBackend(ABC):
    """Abstract interface for pipeline run persistence."""

    @abstractmethod
    def save_pipeline_run(self, run_data: dict) -> str:
        """Persist pipeline run metadata. Returns run_id."""

    @abstractmethod
    def update_pipeline_run(self, run_id: str, updates: dict) -> None:
        """Update fields on an existing pipeline run record."""

    @abstractmethod
    def save_companies(self, companies: List[dict], run_id: str) -> None:
        """Persist scored and enriched company records for a run."""

    @abstractmethod
    def save_contacts(self, contacts: List[dict], run_id: str) -> None:
        """Persist validated contact records for a run."""

    @abstractmethod
    def save_campaign_health(self, metrics: List[dict], run_id: str) -> None:
        """Persist campaign health metrics for a run."""

    @abstractmethod
    def get_latest_run(self) -> Optional[dict]:
        """Return the most recent pipeline run record, or None."""

    @abstractmethod
    def get_run(self, run_id: str) -> Optional[dict]:
        """Return a specific pipeline run record by ID, or None."""
