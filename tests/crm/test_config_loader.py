from __future__ import annotations

import os
import pytest
import yaml

from src.crm.config_loader import (
    load_client_config,
    load_crm_default_setup,
    load_lifecycle_rules,
    load_pipeline_templates,
    resolve_setup_config,
)

_CONFIG_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "config",
    "crm",
)


def test_load_client_config_uses_template_for_unknown_client():
    cfg = load_client_config("nonexistent_client_xyz", _CONFIG_DIR)
    assert "client" in cfg
    assert cfg["client"]["name"] == "nonexistent_client_xyz"


def test_load_client_config_returns_required_keys():
    cfg = load_client_config("acme_saas", _CONFIG_DIR)
    assert "client" in cfg
    assert "gtm" in cfg
    assert "crm_setup" in cfg


def test_load_crm_default_setup_hubspot():
    cfg = load_crm_default_setup("hubspot", _CONFIG_DIR)
    assert cfg["crm"] == "hubspot"
    assert "custom_fields" in cfg
    assert "pipeline" in cfg


def test_load_crm_default_setup_salesforce():
    cfg = load_crm_default_setup("salesforce", _CONFIG_DIR)
    assert cfg["crm"] == "salesforce"
    assert "custom_fields" in cfg
    assert "pipeline" in cfg


def test_load_crm_default_setup_raises_for_unknown():
    with pytest.raises(FileNotFoundError):
        load_crm_default_setup("unknown_crm", _CONFIG_DIR)


def test_hubspot_setup_has_company_fields():
    cfg = load_crm_default_setup("hubspot", _CONFIG_DIR)
    fields = cfg["custom_fields"].get("companies", [])
    names = [f["internal_name"] for f in fields]
    assert "icp_score" in names
    assert "icp_tier" in names
    assert "gtm_segment" in names


def test_hubspot_setup_has_contact_fields():
    cfg = load_crm_default_setup("hubspot", _CONFIG_DIR)
    fields = cfg["custom_fields"].get("contacts", [])
    names = [f["internal_name"] for f in fields]
    assert "email_validation_status" in names
    assert "buyer_persona" in names
    assert "sequence_status" in names


def test_hubspot_setup_has_deal_fields():
    cfg = load_crm_default_setup("hubspot", _CONFIG_DIR)
    fields = cfg["custom_fields"].get("deals", [])
    names = [f["internal_name"] for f in fields]
    assert "gtm_campaign_source" in names
    assert "outbound_motion" in names


def test_hubspot_pipeline_has_9_stages():
    cfg = load_crm_default_setup("hubspot", _CONFIG_DIR)
    stages = cfg["pipeline"]["stages"]
    assert len(stages) == 9


def test_salesforce_setup_has_account_fields():
    cfg = load_crm_default_setup("salesforce", _CONFIG_DIR)
    fields = cfg["custom_fields"].get("Account", [])
    names = [f["internal_name"] for f in fields]
    assert "ICP_Score__c" in names
    assert "ICP_Tier__c" in names


def test_salesforce_pipeline_has_9_stages():
    cfg = load_crm_default_setup("salesforce", _CONFIG_DIR)
    stages = cfg["pipeline"]["stages"]
    assert len(stages) == 9


def test_load_lifecycle_rules_has_rules():
    cfg = load_lifecycle_rules(_CONFIG_DIR)
    assert "lifecycle_rules" in cfg
    assert len(cfg["lifecycle_rules"]["gtm_status_rules"]) > 0


def test_load_pipeline_templates_has_gtm_outbound():
    cfg = load_pipeline_templates(_CONFIG_DIR)
    assert "gtm_outbound" in cfg["pipelines"]


def test_resolve_setup_config_hubspot():
    cfg = resolve_setup_config("acme_saas", "hubspot", _CONFIG_DIR)
    assert "client" in cfg
    assert "custom_fields" in cfg
    assert "pipeline" in cfg
    assert cfg["client"]["name"] == "acme_saas"


def test_resolve_setup_config_salesforce():
    cfg = resolve_setup_config("acme_saas", "salesforce", _CONFIG_DIR)
    assert "custom_fields" in cfg
    assert "Account" in cfg["custom_fields"]
