from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.crm.base import (
    CRMProvider,
    FieldResult,
    FieldStatus,
    PipelineResult,
    SetupMode,
    SetupReport,
    StageResult,
)
from src.crm.hubspot.lifecycle import GTM_LIFECYCLE_PROPERTIES, MANUAL_STEPS
from src.crm.hubspot.pipeline import (
    build_pipeline_payload,
    build_stage_payload,
    pipeline_exists,
    stage_exists,
    stage_has_conflict,
)
from src.crm.hubspot.properties import (
    build_property_payload,
    field_exists,
    field_has_type_conflict,
)
from src.utils.logger import get_logger

log = get_logger(__name__)

_TOKEN = os.getenv("HUBSPOT_PRIVATE_APP_TOKEN", "")


class HubSpotSetupProvider(CRMProvider):
    """
    HubSpot CRM setup provider.

    dry-run / inspect-only: no API calls, generates plan from config.
    live: calls HubSpot API — creates only missing components, never overwrites.
    """

    def __init__(self, mode: SetupMode, client_name: str) -> None:
        super().__init__(mode, client_name)
        self._client: Optional[Any] = None
        self._report = SetupReport(
            client_name=client_name,
            crm_type="hubspot",
            mode=mode.value,
            timestamp=datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
        self._existing_props: Dict[str, List[Dict[str, Any]]] = {}
        self._existing_pipelines: List[Dict[str, Any]] = []
        # Stages embedded in pipeline creation response — label -> id
        self._created_stage_ids: Dict[str, str] = {}

    # ── Authentication ────────────────────────────────────────────────────────

    def authenticate(self) -> bool:
        if self.mode in (SetupMode.DRY_RUN, SetupMode.INSPECT_ONLY):
            log.info("HubSpot: dry-run / inspect-only — skipping authentication")
            return True
        if not _TOKEN:
            log.error(
                "HUBSPOT_PRIVATE_APP_TOKEN is not set. "
                "Add it to .env or use --mode dry-run."
            )
            return False
        from src.crm.hubspot.client import HubSpotClient
        self._client = HubSpotClient(_TOKEN)
        log.info("HubSpot: authenticated with private app token")
        return True

    # ── Property group ────────────────────────────────────────────────────────

    def _ensure_property_group(self, object_name: str) -> None:
        """Create the gtm_properties group for the object if it doesn't already exist."""
        try:
            existing = self._client.get_property_groups(object_name)
            if any(g.get("name") == "gtm_properties" for g in existing):
                log.info("[%s] Property group 'gtm_properties' already exists", object_name)
                return
            self._client.create_property_group(object_name, {
                "name": "gtm_properties",
                "label": "GTM Properties",
                "displayOrder": -1,
            })
            log.info("[%s] Created property group: gtm_properties", object_name)
        except Exception as exc:
            log.warning(
                "[%s] Could not ensure property group, properties will use default group: %s",
                object_name, exc,
            )

    # ── Fetch existing state ──────────────────────────────────────────────────

    def get_existing_fields(self, object_name: str) -> List[Dict[str, Any]]:
        if self._client is None:
            return []
        if object_name not in self._existing_props:
            self._existing_props[object_name] = self._client.get_properties(object_name)
        return self._existing_props[object_name]

    def get_existing_pipelines(self) -> List[Dict[str, Any]]:
        if self._client is None:
            return []
        if not self._existing_pipelines:
            self._existing_pipelines = self._client.get_pipelines("deals")
        return self._existing_pipelines

    # ── Custom fields ─────────────────────────────────────────────────────────

    def create_custom_field(
        self, object_name: str, field_config: Dict[str, Any]
    ) -> FieldResult:
        internal_name = field_config["internal_name"]
        label = field_config.get("label", internal_name)
        field_type = field_config.get("type", "string")

        # dry-run / inspect-only: plan only
        if self.mode in (SetupMode.DRY_RUN, SetupMode.INSPECT_ONLY):
            log.info("[dry-run] Would create property [%s] %s (%s)", object_name, internal_name, field_type)
            return FieldResult(
                object_name=object_name,
                internal_name=internal_name,
                label=label,
                field_type=field_type,
                status=FieldStatus.PLANNED,
            )

        # Ensure the GTM property group exists before first property in each object
        if object_name not in self._existing_props:
            self._ensure_property_group(object_name)

        existing = self.get_existing_fields(object_name)

        # Type conflict → needs review
        if field_has_type_conflict(internal_name, field_type, existing):
            log.warning(
                "[%s] %s already exists with a different type — flagged for review",
                object_name, internal_name,
            )
            return FieldResult(
                object_name=object_name,
                internal_name=internal_name,
                label=label,
                field_type=field_type,
                status=FieldStatus.NEEDS_REVIEW,
                note="Field exists but has a different type. Do not overwrite automatically.",
            )

        # Already exists with matching type → skip
        if field_exists(internal_name, existing):
            log.info("[%s] %s already exists — skipping", object_name, internal_name)
            return FieldResult(
                object_name=object_name,
                internal_name=internal_name,
                label=label,
                field_type=field_type,
                status=FieldStatus.SKIPPED_EXISTS,
            )

        # Create
        payload = build_property_payload(object_name, field_config)
        try:
            self._client.create_property(object_name, payload)
            log.info("[%s] Created property: %s", object_name, internal_name)
            self._existing_props.pop(object_name, None)  # invalidate cache
            return FieldResult(
                object_name=object_name,
                internal_name=internal_name,
                label=label,
                field_type=field_type,
                status=FieldStatus.CREATED,
            )
        except Exception as exc:
            log.error("[%s] Failed to create %s: %s", object_name, internal_name, exc)
            return FieldResult(
                object_name=object_name,
                internal_name=internal_name,
                label=label,
                field_type=field_type,
                status=FieldStatus.FAILED,
                note=str(exc),
            )

    # ── Pipeline ──────────────────────────────────────────────────────────────

    def create_pipeline(self, pipeline_config: Dict[str, Any]) -> PipelineResult:
        pipeline_name = pipeline_config["name"]

        if self.mode in (SetupMode.DRY_RUN, SetupMode.INSPECT_ONLY):
            log.info("[dry-run] Would create pipeline: %s", pipeline_name)
            return PipelineResult(
                pipeline_name=pipeline_name,
                status=FieldStatus.PLANNED,
                pipeline_id=None,
            )

        existing = self.get_existing_pipelines()
        existing_id = pipeline_exists(pipeline_name, existing)
        if existing_id:
            log.info("Pipeline '%s' already exists — skipping", pipeline_name)
            return PipelineResult(
                pipeline_name=pipeline_name,
                status=FieldStatus.SKIPPED_EXISTS,
                pipeline_id=existing_id,
            )

        payload = build_pipeline_payload(pipeline_config)
        try:
            result = self._client.create_pipeline("deals", payload)
            pid = result.get("id")
            log.info("Created pipeline: %s (id=%s)", pipeline_name, pid)
            for stage in result.get("stages", []):
                self._created_stage_ids[stage.get("label", "")] = stage.get("id", "")
            self._existing_pipelines = []
            return PipelineResult(
                pipeline_name=pipeline_name,
                status=FieldStatus.CREATED,
                pipeline_id=pid,
            )
        except Exception as exc:
            # Check if this is a pipeline limit error (free plan = 1 pipeline max)
            is_limit = False
            try:
                import requests as _req
                if isinstance(exc, _req.HTTPError) and exc.response is not None:
                    body = exc.response.json()
                    is_limit = body.get("category") == "API_LIMIT" or "limit" in body.get("message", "").lower()
            except Exception:
                pass
            if is_limit:
                log.info("Pipeline limit reached — adopting existing pipeline")
                return self._adopt_existing_pipeline(pipeline_name)
            log.error("Failed to create pipeline '%s': %s", pipeline_name, exc)
            return PipelineResult(
                pipeline_name=pipeline_name,
                status=FieldStatus.FAILED,
                note=str(exc),
            )

    def _adopt_existing_pipeline(self, desired_name: str) -> PipelineResult:
        """Rename the first existing pipeline to the desired name and reuse it."""
        existing = self.get_existing_pipelines()
        if not existing:
            return PipelineResult(
                pipeline_name=desired_name,
                status=FieldStatus.FAILED,
                note="Pipeline limit reached and no existing pipeline found to adopt.",
            )
        first = existing[0]
        pid = first.get("id", "")
        current_label = first.get("label", "")
        if current_label != desired_name:
            try:
                self._client.rename_pipeline("deals", pid, desired_name)
                log.info(
                    "Renamed existing pipeline '%s' to '%s' (id=%s)",
                    current_label, desired_name, pid,
                )
            except Exception as exc:
                log.warning("Could not rename pipeline: %s — using as-is", exc)
        else:
            log.info("Existing pipeline already named '%s' — reusing (id=%s)", desired_name, pid)
        # Cache existing stage IDs so create_stage() can detect them
        for stage in first.get("stages", []):
            self._created_stage_ids[stage.get("label", "")] = stage.get("id", "")
        self._existing_pipelines = []
        return PipelineResult(
            pipeline_name=desired_name,
            status=FieldStatus.CREATED,
            pipeline_id=pid,
            note="Reused and renamed existing pipeline (plan limit: 1 pipeline).",
        )

    def create_stage(self, pipeline_id: str, stage_config: Dict[str, Any]) -> StageResult:
        label = stage_config["label"]
        probability = stage_config.get("probability", 0.0)
        pipeline_name = stage_config.get("pipeline_name", pipeline_id)

        if self.mode in (SetupMode.DRY_RUN, SetupMode.INSPECT_ONLY):
            log.info("[dry-run] Would create stage: %s (%.0f%%)", label, probability * 100)
            return StageResult(
                pipeline_name=pipeline_name,
                stage_label=label,
                probability=probability,
                status=FieldStatus.PLANNED,
            )

        # If stage was already created as part of pipeline creation payload
        if label in self._created_stage_ids:
            sid = self._created_stage_ids[label]
            log.info("Stage '%s' created with pipeline (id=%s)", label, sid)
            return StageResult(
                pipeline_name=pipeline_name,
                stage_label=label,
                probability=probability,
                status=FieldStatus.CREATED,
                stage_id=sid,
            )

        # Find the full pipeline object for stage inspection
        existing_pipelines = self.get_existing_pipelines()
        pipeline_obj = next(
            (p for p in existing_pipelines if p.get("id") == pipeline_id), {}
        )

        if stage_has_conflict(label, probability, pipeline_obj):
            log.warning("Stage '%s' exists with different probability — flagged for review", label)
            return StageResult(
                pipeline_name=pipeline_name,
                stage_label=label,
                probability=probability,
                status=FieldStatus.NEEDS_REVIEW,
                note="Stage exists but probability differs. Do not overwrite automatically.",
            )

        if stage_exists(label, pipeline_obj):
            log.info("Stage '%s' already exists — skipping", label)
            return StageResult(
                pipeline_name=pipeline_name,
                stage_label=label,
                probability=probability,
                status=FieldStatus.SKIPPED_EXISTS,
            )

        payload = build_stage_payload(stage_config)
        try:
            result = self._client.create_pipeline_stage("deals", pipeline_id, payload)
            sid = result.get("id")
            log.info("Created stage: %s (id=%s)", label, sid)
            self._existing_pipelines = []  # invalidate cache
            return StageResult(
                pipeline_name=pipeline_name,
                stage_label=label,
                probability=probability,
                status=FieldStatus.CREATED,
                stage_id=sid,
            )
        except Exception as exc:
            log.error("Failed to create stage '%s': %s", label, exc)
            return StageResult(
                pipeline_name=pipeline_name,
                stage_label=label,
                probability=probability,
                status=FieldStatus.FAILED,
                note=str(exc),
            )

    # ── Validation / inspect ──────────────────────────────────────────────────

    def validate_setup(self, required_config: Dict[str, Any]) -> SetupReport:
        """inspect-only: compare required config against live CRM state."""
        report = SetupReport(
            client_name=self.client_name,
            crm_type="hubspot",
            mode=self.mode.value,
            timestamp=datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        )

        for object_name, fields in required_config.get("custom_fields", {}).items():
            existing = self.get_existing_fields(object_name)
            for field_cfg in fields:
                internal_name = field_cfg["internal_name"]
                label = field_cfg.get("label", internal_name)
                field_type = field_cfg.get("type", "string")

                if field_has_type_conflict(internal_name, field_type, existing):
                    status = FieldStatus.NEEDS_REVIEW
                    note = "Exists with different type"
                elif field_exists(internal_name, existing):
                    status = FieldStatus.SKIPPED_EXISTS
                    note = ""
                else:
                    status = FieldStatus.PLANNED
                    note = "Missing — will be created in live mode"

                report.fields.append(FieldResult(
                    object_name=object_name,
                    internal_name=internal_name,
                    label=label,
                    field_type=field_type,
                    status=status,
                    note=note,
                ))

        pipeline_cfg = required_config.get("pipeline", {})
        if pipeline_cfg:
            existing_pipelines = self.get_existing_pipelines()
            existing_id = pipeline_exists(pipeline_cfg["name"], existing_pipelines)
            report.pipelines.append(PipelineResult(
                pipeline_name=pipeline_cfg["name"],
                status=FieldStatus.SKIPPED_EXISTS if existing_id else FieldStatus.PLANNED,
                pipeline_id=existing_id,
                note="" if existing_id else "Missing — will be created in live mode",
            ))

        report.next_manual_steps = MANUAL_STEPS
        return report

    def generate_setup_report(self) -> SetupReport:
        return self._report
