from __future__ import annotations

import pytest

from src.crm.base import FieldStatus, SetupMode
from src.crm.hubspot.setup import HubSpotSetupProvider
from src.crm.hubspot.properties import (
    build_property_payload,
    field_exists,
    field_has_type_conflict,
)
from src.crm.hubspot.pipeline import (
    build_pipeline_payload,
    build_stage_payload,
    pipeline_exists,
    stage_exists,
    stage_has_conflict,
)


@pytest.fixture
def provider():
    return HubSpotSetupProvider(mode=SetupMode.DRY_RUN, client_name="test_client")


# ── Authentication ────────────────────────────────────────────────────────────

def test_dry_run_authenticates_without_token(provider):
    assert provider.authenticate() is True


def test_dry_run_returns_empty_existing_fields(provider):
    assert provider.get_existing_fields("companies") == []


def test_dry_run_returns_empty_existing_pipelines(provider):
    assert provider.get_existing_pipelines() == []


# ── Field creation (dry-run) ──────────────────────────────────────────────────

def test_create_field_dry_run_returns_planned(provider):
    result = provider.create_custom_field("companies", {
        "internal_name": "icp_score",
        "label": "ICP Score",
        "type": "number",
    })
    assert result.status == FieldStatus.PLANNED
    assert result.internal_name == "icp_score"


def test_create_enumeration_field_dry_run(provider):
    result = provider.create_custom_field("contacts", {
        "internal_name": "buyer_persona",
        "label": "Buyer Persona",
        "type": "enumeration",
        "options": ["CEO", "Founder", "VP Sales"],
    })
    assert result.status == FieldStatus.PLANNED
    assert result.field_type == "enumeration"


def test_create_pipeline_dry_run_returns_planned(provider):
    result = provider.create_pipeline({"name": "GTM Outbound Pipeline", "stages": []})
    assert result.status == FieldStatus.PLANNED
    assert result.pipeline_name == "GTM Outbound Pipeline"


def test_create_stage_dry_run_returns_planned(provider):
    result = provider.create_stage("pipe_001", {
        "label": "Meeting Booked",
        "probability": 0.50,
        "display_order": 5,
    })
    assert result.status == FieldStatus.PLANNED
    assert result.stage_label == "Meeting Booked"
    assert result.probability == 0.50


# ── Property payload builder ──────────────────────────────────────────────────

def test_build_property_payload_number():
    payload = build_property_payload("companies", {
        "internal_name": "icp_score",
        "label": "ICP Score",
        "type": "number",
    })
    assert payload["name"] == "icp_score"
    assert payload["type"] == "number"
    assert payload["fieldType"] == "number"


def test_build_property_payload_enumeration_has_options():
    payload = build_property_payload("contacts", {
        "internal_name": "icp_tier",
        "label": "ICP Tier",
        "type": "enumeration",
        "options": [
            {"label": "Tier 1", "value": "tier_1"},
            {"label": "Tier 2", "value": "tier_2"},
        ],
    })
    assert payload["type"] == "enumeration"
    assert len(payload["options"]) == 2
    assert payload["options"][0]["value"] == "tier_1"


def test_build_property_payload_string_options_auto_value():
    payload = build_property_payload("contacts", {
        "internal_name": "buyer_persona",
        "label": "Buyer Persona",
        "type": "enumeration",
        "options": ["CEO", "Founder", "VP Sales"],
    })
    values = [o["value"] for o in payload["options"]]
    assert "ceo" in values
    assert "founder" in values


def test_build_property_payload_bool():
    payload = build_property_payload("contacts", {
        "internal_name": "persona_match",
        "label": "Persona Match",
        "type": "bool",
    })
    assert payload["type"] == "booleancheckbox"


# ── Field existence checks ────────────────────────────────────────────────────

def test_field_exists_returns_true_when_present():
    existing = [{"name": "icp_score", "type": "number"}]
    assert field_exists("icp_score", existing) is True


def test_field_exists_returns_false_when_absent():
    existing = [{"name": "icp_score", "type": "number"}]
    assert field_exists("icp_tier", existing) is False


def test_field_has_type_conflict_returns_true_on_mismatch():
    existing = [{"name": "icp_score", "type": "text"}]
    assert field_has_type_conflict("icp_score", "number", existing) is True


def test_field_has_type_conflict_returns_false_on_match():
    existing = [{"name": "icp_score", "type": "number"}]
    assert field_has_type_conflict("icp_score", "number", existing) is False


# ── Pipeline helpers ──────────────────────────────────────────────────────────

def test_pipeline_exists_returns_id_when_found():
    existing = [{"label": "GTM Outbound Pipeline", "id": "pipe_123"}]
    assert pipeline_exists("GTM Outbound Pipeline", existing) == "pipe_123"


def test_pipeline_exists_returns_none_when_absent():
    existing = [{"label": "Other Pipeline", "id": "pipe_999"}]
    assert pipeline_exists("GTM Outbound Pipeline", existing) is None


def test_stage_exists_returns_id_when_found():
    pipeline = {"stages": [{"label": "Meeting Booked", "id": "s_001"}]}
    assert stage_exists("Meeting Booked", pipeline) == "s_001"


def test_stage_exists_returns_none_when_absent():
    pipeline = {"stages": [{"label": "Other Stage", "id": "s_001"}]}
    assert stage_exists("Meeting Booked", pipeline) is None


def test_stage_has_conflict_returns_true_on_prob_mismatch():
    pipeline = {
        "stages": [{"label": "Meeting Booked", "metadata": {"probability": "0.40"}}]
    }
    assert stage_has_conflict("Meeting Booked", 0.50, pipeline) is True


def test_stage_has_conflict_returns_false_on_match():
    pipeline = {
        "stages": [{"label": "Meeting Booked", "metadata": {"probability": "0.5"}}]
    }
    assert stage_has_conflict("Meeting Booked", 0.50, pipeline) is False


def test_build_pipeline_payload():
    payload = build_pipeline_payload({"name": "GTM Outbound Pipeline"})
    assert payload["label"] == "GTM Outbound Pipeline"


def test_build_stage_payload():
    payload = build_stage_payload({"label": "Meeting Booked", "probability": 0.50, "display_order": 5})
    assert payload["label"] == "Meeting Booked"
    assert payload["metadata"]["probability"] == "0.5"
