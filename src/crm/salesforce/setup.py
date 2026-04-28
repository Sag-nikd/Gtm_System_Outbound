from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from src.crm.base import (
    CRMProvider,
    FieldResult,
    FieldStatus,
    PipelineResult,
    SetupMode,
    SetupReport,
    StageResult,
)
from src.crm.salesforce.fields import (
    build_field_metadata,
    field_exists,
    field_has_type_conflict,
)
from src.crm.salesforce.lifecycle import MANUAL_STEPS
from src.crm.salesforce.pipeline import (
    build_stage_metadata,
    stage_exists,
    stage_has_conflict,
)
from src.utils.logger import get_logger

log = get_logger(__name__)


class SalesforceSetupProvider(CRMProvider):
    """
    Salesforce CRM setup provider.

    dry-run / inspect-only: fully supported — generates plan from config, no API calls.
    live: raises NotImplementedError for field/stage creation (Metadata API complexity).
          Use dry-run output as a manual setup guide.
    """

    def __init__(self, mode: SetupMode, client_name: str) -> None:
        super().__init__(mode, client_name)
        self._client = None

    # ── Authentication ────────────────────────────────────────────────────────

    def authenticate(self) -> bool:
        if self.mode in (SetupMode.DRY_RUN, SetupMode.INSPECT_ONLY):
            log.info("Salesforce: dry-run / inspect-only — skipping authentication")
            return True
        log.warning(
            "Salesforce live mode: authentication requires "
            "SALESFORCE_CLIENT_ID, SALESFORCE_CLIENT_SECRET, SALESFORCE_USERNAME, "
            "SALESFORCE_PASSWORD, SALESFORCE_SECURITY_TOKEN, SALESFORCE_INSTANCE_URL"
        )
        try:
            import os
            from src.crm.salesforce.client import SalesforceClient
            self._client = SalesforceClient(
                client_id=os.getenv("SALESFORCE_CLIENT_ID", ""),
                client_secret=os.getenv("SALESFORCE_CLIENT_SECRET", ""),
                username=os.getenv("SALESFORCE_USERNAME", ""),
                password=os.getenv("SALESFORCE_PASSWORD", ""),
                security_token=os.getenv("SALESFORCE_SECURITY_TOKEN", ""),
                instance_url=os.getenv("SALESFORCE_INSTANCE_URL", ""),
            )
            self._client.authenticate()
            return True
        except NotImplementedError as exc:
            log.error("Salesforce live mode not available: %s", exc)
            return False

    # ── Existing state ────────────────────────────────────────────────────────

    def get_existing_fields(self, object_name: str) -> List[Dict[str, Any]]:
        if self._client is None:
            return []
        try:
            return self._client.get_object_fields(object_name)
        except NotImplementedError:
            log.warning("Salesforce: get_existing_fields not implemented — returning empty list")
            return []

    def get_existing_pipelines(self) -> List[Dict[str, Any]]:
        if self._client is None:
            return []
        try:
            return self._client.get_opportunity_stages()
        except NotImplementedError:
            log.warning("Salesforce: get_existing_pipelines not implemented — returning empty list")
            return []

    # ── Custom fields ─────────────────────────────────────────────────────────

    def create_custom_field(
        self, object_name: str, field_config: Dict[str, Any]
    ) -> FieldResult:
        internal_name = field_config["internal_name"]
        label = field_config.get("label", internal_name)
        field_type = field_config.get("type", "string")

        if self.mode in (SetupMode.DRY_RUN, SetupMode.INSPECT_ONLY):
            metadata = build_field_metadata(field_config)
            log.info(
                "[dry-run] Would create Salesforce field [%s] %s (%s)",
                object_name, internal_name, metadata.get("type"),
            )
            return FieldResult(
                object_name=object_name,
                internal_name=internal_name,
                label=label,
                field_type=field_type,
                status=FieldStatus.PLANNED,
                note=f"Tooling API payload ready. Create manually in Setup → Object Manager → {object_name}.",
            )

        # live mode — not safely implemented yet
        log.error(
            "Salesforce live field creation is not implemented. "
            "Use --mode dry-run and follow the manual setup steps in the report."
        )
        return FieldResult(
            object_name=object_name,
            internal_name=internal_name,
            label=label,
            field_type=field_type,
            status=FieldStatus.FAILED,
            note=(
                "Live Salesforce field creation requires Metadata API or Tooling API deployment. "
                "Not implemented. Create field manually in Salesforce Setup."
            ),
        )

    # ── Pipeline (Opportunity Stages) ─────────────────────────────────────────

    def create_pipeline(self, pipeline_config: Dict[str, Any]) -> PipelineResult:
        pipeline_name = pipeline_config.get("name", "GTM Outbound Pipeline")

        if self.mode in (SetupMode.DRY_RUN, SetupMode.INSPECT_ONLY):
            log.info("[dry-run] Would configure Opportunity stages for: %s", pipeline_name)
            return PipelineResult(
                pipeline_name=pipeline_name,
                status=FieldStatus.PLANNED,
                note=(
                    "Salesforce does not have named pipelines. "
                    "Stages are added to the OpportunityStage picklist. "
                    "Add them in Setup → Opportunity Stages."
                ),
            )

        log.error(
            "Salesforce live pipeline/stage creation is not implemented. "
            "Add stages manually in Setup → Opportunity Stages."
        )
        return PipelineResult(
            pipeline_name=pipeline_name,
            status=FieldStatus.FAILED,
            note="Not implemented for live Salesforce. Add stages manually.",
        )

    def create_stage(self, pipeline_id: str, stage_config: Dict[str, Any]) -> StageResult:
        label = stage_config.get("label", stage_config.get("name", ""))
        probability = stage_config.get("probability", 0.0)
        if isinstance(probability, float) and probability <= 1.0:
            probability_pct = probability
        else:
            probability_pct = probability / 100.0

        if self.mode in (SetupMode.DRY_RUN, SetupMode.INSPECT_ONLY):
            metadata = build_stage_metadata(stage_config)
            log.info(
                "[dry-run] Would add Opportunity stage: %s (%d%%)",
                label, int(probability_pct * 100),
            )
            return StageResult(
                pipeline_name="GTM Outbound Pipeline",
                stage_label=label,
                probability=probability_pct,
                status=FieldStatus.PLANNED,
                note="Add manually in Salesforce Setup → Opportunity Stages.",
            )

        log.error("Salesforce live stage creation not implemented.")
        return StageResult(
            pipeline_name="GTM Outbound Pipeline",
            stage_label=label,
            probability=probability_pct,
            status=FieldStatus.FAILED,
            note="Not implemented for live Salesforce.",
        )

    # ── Validation ────────────────────────────────────────────────────────────

    def validate_setup(self, required_config: Dict[str, Any]) -> SetupReport:
        report = SetupReport(
            client_name=self.client_name,
            crm_type="salesforce",
            mode=self.mode.value,
            timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
        # Without live API access, all fields are "planned" (missing)
        for object_name, fields in required_config.get("custom_fields", {}).items():
            for field_cfg in fields:
                report.fields.append(FieldResult(
                    object_name=object_name,
                    internal_name=field_cfg["internal_name"],
                    label=field_cfg.get("label", field_cfg["internal_name"]),
                    field_type=field_cfg.get("type", "string"),
                    status=FieldStatus.PLANNED,
                    note="Cannot inspect Salesforce without live credentials. Assumed missing.",
                ))
        pipeline_cfg = required_config.get("pipeline", {})
        if pipeline_cfg:
            report.pipelines.append(PipelineResult(
                pipeline_name=pipeline_cfg.get("name", "GTM Outbound Pipeline"),
                status=FieldStatus.PLANNED,
                note="Add Opportunity stages manually in Salesforce Setup.",
            ))
            for stage in pipeline_cfg.get("stages", []):
                label = stage.get("label", stage.get("name", ""))
                prob = stage.get("probability", 0.0)
                report.stages.append(StageResult(
                    pipeline_name=pipeline_cfg.get("name", ""),
                    stage_label=label,
                    probability=prob,
                    status=FieldStatus.PLANNED,
                    note="Add manually in Setup → Opportunity Stages.",
                ))

        report.next_manual_steps = MANUAL_STEPS
        return report

    def generate_setup_report(self) -> SetupReport:
        return SetupReport(
            client_name=self.client_name,
            crm_type="salesforce",
            mode=self.mode.value,
            timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
