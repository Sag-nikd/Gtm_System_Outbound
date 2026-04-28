from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.crm.base import CRMProvider, FieldStatus, SetupMode, SetupReport, StageResult
from src.crm.config_loader import resolve_setup_config
from src.crm.reporting import write_all_reports
from src.utils.logger import get_logger

log = get_logger(__name__)

_DEFAULT_OUTPUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "outputs",
    "crm_setup",
)


def build_provider(crm: str, mode: SetupMode, client_name: str) -> CRMProvider:
    """Instantiate the correct CRM provider for the given CRM type and mode."""
    if crm == "hubspot":
        from src.crm.hubspot.setup import HubSpotSetupProvider
        return HubSpotSetupProvider(mode=mode, client_name=client_name)
    if crm == "salesforce":
        from src.crm.salesforce.setup import SalesforceSetupProvider
        return SalesforceSetupProvider(mode=mode, client_name=client_name)
    raise ValueError(f"Unsupported CRM: '{crm}'. Supported: hubspot, salesforce")


class CRMSetupGenerator:
    """
    Orchestrates the CRM setup process for a given client and CRM type.

    Modes:
      inspect-only  — scan existing CRM, produce gap report, create nothing
      dry-run       — plan what would be created, create nothing
      live          — create only missing components, never overwrite
      force-update  — (future) update existing components where safe
    """

    def __init__(
        self,
        client_name: str,
        crm: str,
        mode: SetupMode,
        output_dir: Optional[str] = None,
        config_dir: Optional[str] = None,
    ) -> None:
        self.client_name = client_name
        self.crm = crm
        self.mode = mode
        self.output_dir = output_dir or _DEFAULT_OUTPUT_DIR
        self.config_dir = config_dir
        self.provider: CRMProvider = build_provider(crm, mode, client_name)

    def run(self) -> SetupReport:
        log.info(
            "CRM Setup Generator — client=%s  crm=%s  mode=%s",
            self.client_name, self.crm, self.mode.value,
        )

        if self.mode == SetupMode.FORCE_UPDATE:
            log.warning(
                "force-update mode is not enabled by default. "
                "Pass --mode force-update only when you intend to overwrite existing CRM setup."
            )

        authenticated = self.provider.authenticate()
        if not authenticated and self.mode == SetupMode.LIVE:
            raise RuntimeError(
                f"Authentication failed for {self.crm}. "
                "Check environment variables and retry."
            )

        resolved = resolve_setup_config(self.client_name, self.crm, self.config_dir)
        crm_setup_flags = resolved.get("crm_setup", {})

        report = SetupReport(
            client_name=self.client_name,
            crm_type=self.crm,
            mode=self.mode.value,
            timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        )

        if self.mode == SetupMode.INSPECT_ONLY:
            report = self.provider.validate_setup(resolved)
            report.mode = self.mode.value
        else:
            if crm_setup_flags.get("create_custom_fields", True):
                self._process_fields(resolved.get("custom_fields", {}), report)

            if crm_setup_flags.get("create_pipeline", True):
                self._process_pipeline(resolved.get("pipeline", {}), report)

        self._add_manual_steps(report)

        paths = write_all_reports(report, self.output_dir)
        log.info("Reports written to: %s", self.output_dir)
        for p in paths:
            log.info("  %s", os.path.basename(p))

        return report

    def _process_fields(
        self, custom_fields: Dict[str, List[Dict[str, Any]]], report: SetupReport
    ) -> None:
        for object_name, fields in custom_fields.items():
            log.info("Processing %d fields for object: %s", len(fields), object_name)
            for field_cfg in fields:
                result = self.provider.create_custom_field(object_name, field_cfg)
                report.fields.append(result)

    def _process_pipeline(
        self, pipeline_cfg: Dict[str, Any], report: SetupReport
    ) -> None:
        if not pipeline_cfg:
            return
        pipeline_result = self.provider.create_pipeline(pipeline_cfg)
        report.pipelines.append(pipeline_result)

        if pipeline_result.status == FieldStatus.FAILED:
            log.warning("Skipping stage creation — pipeline creation failed")
            for stage in pipeline_cfg.get("stages", []):
                report.stages.append(StageResult(
                    pipeline_name=pipeline_cfg.get("name", ""),
                    stage_label=stage.get("label", stage.get("name", "")),
                    probability=stage.get("probability", 0.0),
                    status=FieldStatus.FAILED,
                    note="Skipped because pipeline creation failed",
                ))
            return

        pipeline_id = pipeline_result.pipeline_id or ""
        for stage in pipeline_cfg.get("stages", []):
            stage_result = self.provider.create_stage(pipeline_id, stage)
            report.stages.append(stage_result)

    def _add_manual_steps(self, report: SetupReport) -> None:
        steps: List[str] = []
        if self.crm == "hubspot":
            steps += [
                "Create a HubSpot workflow to update GTM lifecycle stage when icp_tier = Tier 1 or Tier 2.",
                "Set up Deal association rules to link Contacts to the GTM Outbound Pipeline.",
                "Enable required HubSpot property groups under Settings > Properties > Group.",
                "Assign the GTM Outbound Pipeline as the default pipeline for your sales team.",
            ]
        if self.crm == "salesforce":
            steps += [
                "Add Opportunity Stage picklist values to match the GTM pipeline in Setup > Picklist Value Sets.",
                "Create a Salesforce Flow or Process Builder to update lifecycle status when ICP_Tier__c changes.",
                "Assign field-level security for new __c fields to the relevant profiles.",
                "Add new custom fields to Page Layouts for Account, Contact, Opportunity, and Lead objects.",
            ]
        if report.fields_by_status(FieldStatus.NEEDS_REVIEW):
            steps.append(
                "Review flagged fields in the validation report — some existing fields have type mismatches."
            )
        report.next_manual_steps = steps
