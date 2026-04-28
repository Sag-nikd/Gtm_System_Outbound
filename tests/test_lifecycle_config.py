"""Tests that lifecycle stages are driven by config/lifecycle_mapping.json, not hardcoded."""
from __future__ import annotations

import pytest

from src.hubspot.hubspot_sync_mock import (
    _company_lifecycle,
    _contact_lifecycle,
    _load_lifecycle_map,
)


def test_tier1_approved_maps_to_contact_discovery_approved():
    company = {"icp_tier": "Tier 1", "contact_discovery_approved": True}
    assert _company_lifecycle(company) == "Contact Discovery Approved"


def test_tier2_approved_maps_to_contact_discovery_approved():
    company = {"icp_tier": "Tier 2", "contact_discovery_approved": True}
    assert _company_lifecycle(company) == "Contact Discovery Approved"


def test_tier3_maps_to_enriched_account():
    company = {"icp_tier": "Tier 3", "contact_discovery_approved": False}
    assert _company_lifecycle(company) == "Enriched Account"


def test_disqualified_maps_to_suppressed():
    company = {"icp_tier": "Disqualified", "contact_discovery_approved": False}
    assert _company_lifecycle(company) == "Suppressed"


def test_approved_contact_maps_to_contact_validated():
    contact = {"final_validation_status": "approved"}
    assert _contact_lifecycle(contact) == "Contact Validated"


def test_review_contact_maps_to_nurture():
    contact = {"final_validation_status": "review"}
    assert _contact_lifecycle(contact) == "Nurture"


def test_suppressed_contact_maps_to_suppressed():
    contact = {"final_validation_status": "suppressed"}
    assert _contact_lifecycle(contact) == "Suppressed"


def test_config_driven_company_lifecycle(tmp_path, monkeypatch):
    """Custom config changes the resolved lifecycle stage."""
    import json, importlib
    import src.hubspot.hubspot_sync_mock as mod

    custom_config = {
        "stages": ["Custom Stage"],
        "company_lifecycle_rules": {
            "tier_1_enriched": "Custom Stage",
            "tier_2_enriched": "Custom Stage",
            "tier_3_enriched": "Custom Stage",
            "disqualified": "Custom Stage",
        },
        "contact_lifecycle_rules": {
            "approved": "Custom Stage",
            "review": "Custom Stage",
            "suppressed": "Custom Stage",
        },
    }
    config_file = tmp_path / "lifecycle_mapping.json"
    config_file.write_text(json.dumps(custom_config))

    # Reset the module-level cache and force a reload from the custom file
    monkeypatch.setattr(mod, "_LIFECYCLE_MAP", None)
    monkeypatch.setattr(mod, "_LIFECYCLE_CONFIG_PATH", str(config_file))

    company = {"icp_tier": "Tier 1", "contact_discovery_approved": True}
    assert _company_lifecycle(company) == "Custom Stage"

    contact = {"final_validation_status": "approved"}
    assert _contact_lifecycle(contact) == "Custom Stage"
