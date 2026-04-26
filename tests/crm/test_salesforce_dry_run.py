from __future__ import annotations

import pytest

from src.crm.base import FieldStatus, SetupMode
from src.crm.salesforce.setup import SalesforceSetupProvider
from src.crm.salesforce.fields import (
    build_field_metadata,
    field_exists,
    field_has_type_conflict,
)
from src.crm.salesforce.pipeline import (
    build_stage_metadata,
    stage_exists,
    stage_has_conflict,
)


@pytest.fixture
def provider():
    return SalesforceSetupProvider(mode=SetupMode.DRY_RUN, client_name="test_client")


# ── Authentication ────────────────────────────────────────────────────────────

def test_dry_run_authenticates_without_credentials(provider):
    assert provider.authenticate() is True


def test_dry_run_returns_empty_existing_fields(provider):
    assert provider.get_existing_fields("Account") == []


def test_dry_run_returns_empty_existing_pipelines(provider):
    assert provider.get_existing_pipelines() == []


# ── Field creation (dry-run) ──────────────────────────────────────────────────

def test_create_field_dry_run_returns_planned(provider):
    result = provider.create_custom_field("Account", {
        "internal_name": "ICP_Score__c",
        "label": "ICP Score",
        "type": "number",
    })
    assert result.status == FieldStatus.PLANNED
    assert result.internal_name == "ICP_Score__c"


def test_create_picklist_field_dry_run(provider):
    result = provider.create_custom_field("Contact", {
        "internal_name": "Buyer_Persona__c",
        "label": "Buyer Persona",
        "type": "enumeration",
        "options": ["CEO", "Founder"],
    })
    assert result.status == FieldStatus.PLANNED


def test_create_pipeline_dry_run_returns_planned(provider):
    result = provider.create_pipeline({"name": "GTM Outbound Pipeline", "stages": []})
    assert result.status == FieldStatus.PLANNED


def test_create_stage_dry_run_returns_planned(provider):
    result = provider.create_stage("sf_pipeline", {
        "name": "Meeting Booked",
        "label": "Meeting Booked",
        "probability": 0.50,
    })
    assert result.status == FieldStatus.PLANNED


# ── Live mode stubs raise correctly ──────────────────────────────────────────

def test_live_field_creation_returns_failed():
    live_provider = SalesforceSetupProvider(mode=SetupMode.LIVE, client_name="test")
    result = live_provider.create_custom_field("Account", {
        "internal_name": "ICP_Score__c",
        "label": "ICP Score",
        "type": "number",
    })
    assert result.status == FieldStatus.FAILED
    assert "not implemented" in result.note.lower()


def test_live_pipeline_creation_returns_failed():
    live_provider = SalesforceSetupProvider(mode=SetupMode.LIVE, client_name="test")
    result = live_provider.create_pipeline({"name": "GTM Outbound Pipeline"})
    assert result.status == FieldStatus.FAILED


# ── Field metadata builder ────────────────────────────────────────────────────

def test_build_field_metadata_number():
    meta = build_field_metadata({
        "internal_name": "ICP_Score__c",
        "label": "ICP Score",
        "type": "number",
    })
    assert meta["type"] == "Number"
    assert meta["fullName"] == "ICP_Score__c"


def test_build_field_metadata_picklist_has_values():
    meta = build_field_metadata({
        "internal_name": "ICP_Tier__c",
        "label": "ICP Tier",
        "type": "enumeration",
        "options": ["Tier 1", "Tier 2", "Tier 3"],
    })
    assert meta["type"] == "Picklist"
    values = [v["fullName"] for v in meta["valueSet"]["valueSetDefinition"]["value"]]
    assert "Tier 1" in values
    assert "Tier 3" in values


def test_build_field_metadata_checkbox():
    meta = build_field_metadata({
        "internal_name": "Persona_Match__c",
        "label": "Persona Match",
        "type": "bool",
        "default": False,
    })
    assert meta["type"] == "Checkbox"
    assert meta["defaultValue"] is False


def test_build_field_metadata_text_has_length():
    meta = build_field_metadata({
        "internal_name": "Fit_Reason__c",
        "label": "Fit Reason",
        "type": "string",
    })
    assert meta["type"] == "Text"
    assert meta["length"] == 255


# ── Field existence checks ────────────────────────────────────────────────────

def test_field_exists_returns_true():
    existing = [{"name": "ICP_Score__c", "type": "Number"}]
    assert field_exists("ICP_Score__c", existing) is True


def test_field_exists_returns_false():
    existing = [{"name": "ICP_Score__c", "type": "Number"}]
    assert field_exists("ICP_Tier__c", existing) is False


def test_field_has_type_conflict_true():
    existing = [{"name": "ICP_Score__c", "type": "Text"}]
    assert field_has_type_conflict("ICP_Score__c", "number", existing) is True


def test_field_has_type_conflict_false():
    existing = [{"name": "ICP_Score__c", "type": "Number"}]
    assert field_has_type_conflict("ICP_Score__c", "number", existing) is False


# ── Stage helpers ─────────────────────────────────────────────────────────────

def test_stage_exists_returns_true():
    existing = [{"MasterLabel": "Meeting Booked", "Probability": 50}]
    assert stage_exists("Meeting Booked", existing) is True


def test_stage_exists_returns_false():
    existing = [{"MasterLabel": "Other Stage"}]
    assert stage_exists("Meeting Booked", existing) is False


def test_stage_has_conflict_returns_true_on_mismatch():
    existing = [{"MasterLabel": "Meeting Booked", "Probability": 40}]
    assert stage_has_conflict("Meeting Booked", 0.50, existing) is True


def test_stage_has_conflict_returns_false_on_match():
    existing = [{"MasterLabel": "Meeting Booked", "Probability": 50}]
    assert stage_has_conflict("Meeting Booked", 0.50, existing) is False


def test_build_stage_metadata():
    meta = build_stage_metadata({
        "name": "Meeting Booked",
        "probability": 0.50,
        "forecast_category": "Pipeline",
    })
    assert meta["probability"] == 50
    assert meta["isActive"] is True
    assert meta["isClosed"] is False


def test_validate_setup_returns_report(provider):
    from src.crm.config_loader import resolve_setup_config
    import os
    config_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "config", "crm",
    )
    cfg = resolve_setup_config("acme_saas", "salesforce", config_dir)
    report = provider.validate_setup(cfg)
    assert report.crm_type == "salesforce"
    assert len(report.fields) > 0
    assert len(report.next_manual_steps) > 0
