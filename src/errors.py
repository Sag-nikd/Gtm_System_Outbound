"""Domain errors — raised loud, caught only at CLI/webhook boundary."""
from __future__ import annotations


class GTMError(Exception):
    """Base for all GTM-OS domain errors."""


class ConfigError(GTMError):
    """Bad or missing configuration."""


class IngestionError(GTMError):
    """Failure during data ingestion."""


class ScoringError(GTMError):
    """Failure during ICP scoring."""


class EnrichmentError(GTMError):
    """Failure during contact/company enrichment."""


class ValidationError(GTMError):
    """Failure during email/data validation."""


class CRMError(GTMError):
    """Failure syncing to CRM."""


class SequencerError(GTMError):
    """Failure communicating with sequencer."""


class SuppressionError(GTMError):
    """Failure in suppression list operations."""


class VendorError(GTMError):
    """Vendor API returned an unexpected error."""

    def __init__(self, vendor: str, message: str) -> None:
        super().__init__(f"[{vendor}] {message}")
        self.vendor = vendor


class ApolloError(VendorError):
    def __init__(self, message: str) -> None:
        super().__init__("Apollo", message)


class ZeroBounceError(VendorError):
    def __init__(self, message: str) -> None:
        super().__init__("ZeroBounce", message)


class InstantlyError(VendorError):
    def __init__(self, message: str) -> None:
        super().__init__("Instantly", message)


class HubSpotError(VendorError):
    def __init__(self, message: str) -> None:
        super().__init__("HubSpot", message)


class GongError(VendorError):
    def __init__(self, message: str) -> None:
        super().__init__("Gong", message)


class LLMError(GTMError):
    """Failure in LLM call or output parsing."""


class EmbeddingError(GTMError):
    """Failure generating or storing embeddings."""


class PipelineRunNotFound(GTMError):
    """Referenced pipeline run does not exist."""

    def __init__(self, run_id: str) -> None:
        super().__init__(f"Pipeline run not found: {run_id}")
        self.run_id = run_id
