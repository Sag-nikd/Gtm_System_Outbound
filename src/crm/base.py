from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class SetupMode(str, Enum):
    INSPECT_ONLY = "inspect-only"
    DRY_RUN = "dry-run"
    LIVE = "live"
    FORCE_UPDATE = "force-update"


class FieldStatus(str, Enum):
    PLANNED = "planned"
    CREATED = "created"
    SKIPPED_EXISTS = "skipped_exists"
    NEEDS_REVIEW = "needs_review"
    FAILED = "failed"


@dataclass
class FieldResult:
    object_name: str
    internal_name: str
    label: str
    field_type: str
    status: FieldStatus
    note: str = ""


@dataclass
class PipelineResult:
    pipeline_name: str
    status: FieldStatus
    pipeline_id: Optional[str] = None
    note: str = ""


@dataclass
class StageResult:
    pipeline_name: str
    stage_label: str
    probability: float
    status: FieldStatus
    stage_id: Optional[str] = None
    note: str = ""


@dataclass
class SetupReport:
    client_name: str
    crm_type: str
    mode: str
    timestamp: str
    fields: List[FieldResult] = field(default_factory=list)
    pipelines: List[PipelineResult] = field(default_factory=list)
    stages: List[StageResult] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    next_manual_steps: List[str] = field(default_factory=list)

    def fields_by_status(self, status: FieldStatus) -> List[FieldResult]:
        return [f for f in self.fields if f.status == status]

    def summary(self) -> Dict[str, Any]:
        return {
            "client_name": self.client_name,
            "crm_type": self.crm_type,
            "mode": self.mode,
            "timestamp": self.timestamp,
            "fields_planned": len(self.fields_by_status(FieldStatus.PLANNED)),
            "fields_created": len(self.fields_by_status(FieldStatus.CREATED)),
            "fields_skipped": len(self.fields_by_status(FieldStatus.SKIPPED_EXISTS)),
            "fields_needs_review": len(self.fields_by_status(FieldStatus.NEEDS_REVIEW)),
            "fields_failed": len(self.fields_by_status(FieldStatus.FAILED)),
            "pipelines_planned": len([p for p in self.pipelines if p.status == FieldStatus.PLANNED]),
            "pipelines_created": len([p for p in self.pipelines if p.status == FieldStatus.CREATED]),
            "pipelines_skipped": len([p for p in self.pipelines if p.status == FieldStatus.SKIPPED_EXISTS]),
            "stages_planned": len([s for s in self.stages if s.status == FieldStatus.PLANNED]),
            "stages_created": len([s for s in self.stages if s.status == FieldStatus.CREATED]),
            "stages_skipped": len([s for s in self.stages if s.status == FieldStatus.SKIPPED_EXISTS]),
            "warnings": len(self.warnings),
            "errors": len(self.errors),
        }


class CRMProvider(ABC):
    """Abstract base for all CRM providers. HubSpot and Salesforce implement this."""

    def __init__(self, mode: SetupMode, client_name: str) -> None:
        self.mode = mode
        self.client_name = client_name

    @abstractmethod
    def authenticate(self) -> bool:
        """Verify credentials. Returns True if authenticated (or dry-run)."""

    @abstractmethod
    def get_existing_fields(self, object_name: str) -> List[Dict[str, Any]]:
        """Return list of existing custom fields for the given CRM object."""

    @abstractmethod
    def get_existing_pipelines(self) -> List[Dict[str, Any]]:
        """Return list of existing pipelines."""

    @abstractmethod
    def create_custom_field(self, object_name: str, field_config: Dict[str, Any]) -> FieldResult:
        """Create a custom field/property. Idempotent — skip if exists."""

    @abstractmethod
    def create_pipeline(self, pipeline_config: Dict[str, Any]) -> PipelineResult:
        """Create a sales pipeline. Idempotent — skip if exists."""

    @abstractmethod
    def create_stage(self, pipeline_id: str, stage_config: Dict[str, Any]) -> StageResult:
        """Create a pipeline stage. Idempotent — skip if exists."""

    @abstractmethod
    def validate_setup(self, required_config: Dict[str, Any]) -> SetupReport:
        """Compare required setup against existing CRM config. Return gap report."""

    @abstractmethod
    def generate_setup_report(self) -> SetupReport:
        """Return the accumulated SetupReport for the current run."""
