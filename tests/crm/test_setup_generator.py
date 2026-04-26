from __future__ import annotations

import os
import json
import pytest

from src.crm.base import FieldStatus, SetupMode
from src.crm.setup_generator import CRMSetupGenerator

_CONFIG_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "config",
    "crm",
)


@pytest.fixture
def hs_generator(tmp_path):
    return CRMSetupGenerator(
        client_name="acme_saas",
        crm="hubspot",
        mode=SetupMode.DRY_RUN,
        output_dir=str(tmp_path),
        config_dir=_CONFIG_DIR,
    )


@pytest.fixture
def sf_generator(tmp_path):
    return CRMSetupGenerator(
        client_name="acme_saas",
        crm="salesforce",
        mode=SetupMode.DRY_RUN,
        output_dir=str(tmp_path),
        config_dir=_CONFIG_DIR,
    )


# ── Generator init ────────────────────────────────────────────────────────────

def test_generator_builds_hubspot_provider(hs_generator):
    from src.crm.hubspot.setup import HubSpotSetupProvider
    assert isinstance(hs_generator.provider, HubSpotSetupProvider)


def test_generator_builds_salesforce_provider(sf_generator):
    from src.crm.salesforce.setup import SalesforceSetupProvider
    assert isinstance(sf_generator.provider, SalesforceSetupProvider)


def test_generator_raises_for_unknown_crm(tmp_path):
    with pytest.raises(ValueError, match="Unsupported CRM"):
        CRMSetupGenerator(
            client_name="acme_saas",
            crm="dynamics",
            mode=SetupMode.DRY_RUN,
            output_dir=str(tmp_path),
        )


# ── Dry-run HubSpot run ───────────────────────────────────────────────────────

def test_hs_dry_run_returns_report(hs_generator):
    report = hs_generator.run()
    assert report.client_name == "acme_saas"
    assert report.crm_type == "hubspot"
    assert report.mode == "dry-run"


def test_hs_dry_run_fields_are_planned(hs_generator):
    report = hs_generator.run()
    assert len(report.fields) > 0
    for f in report.fields:
        assert f.status == FieldStatus.PLANNED


def test_hs_dry_run_has_pipeline(hs_generator):
    report = hs_generator.run()
    assert len(report.pipelines) == 1
    assert report.pipelines[0].status == FieldStatus.PLANNED
    assert "GTM Outbound Pipeline" in report.pipelines[0].pipeline_name


def test_hs_dry_run_has_9_stages(hs_generator):
    report = hs_generator.run()
    assert len(report.stages) == 9


def test_hs_dry_run_has_manual_steps(hs_generator):
    report = hs_generator.run()
    assert len(report.next_manual_steps) > 0


# ── Dry-run Salesforce run ────────────────────────────────────────────────────

def test_sf_dry_run_returns_report(sf_generator):
    report = sf_generator.run()
    assert report.client_name == "acme_saas"
    assert report.crm_type == "salesforce"
    assert report.mode == "dry-run"


def test_sf_dry_run_fields_are_planned(sf_generator):
    report = sf_generator.run()
    assert len(report.fields) > 0
    for f in report.fields:
        assert f.status == FieldStatus.PLANNED


def test_sf_dry_run_has_pipeline(sf_generator):
    report = sf_generator.run()
    assert len(report.pipelines) == 1


def test_sf_dry_run_has_9_stages(sf_generator):
    report = sf_generator.run()
    assert len(report.stages) == 9


# ── Output files ──────────────────────────────────────────────────────────────

def test_hs_dry_run_writes_5_files(hs_generator, tmp_path):
    hs_generator.run()
    expected = [
        "acme_saas_hubspot_setup_plan.json",
        "acme_saas_hubspot_setup_report.md",
        "acme_saas_hubspot_field_inventory.csv",
        "acme_saas_hubspot_pipeline_plan.csv",
        "acme_saas_hubspot_validation_report.json",
    ]
    for fname in expected:
        path = os.path.join(str(tmp_path), fname)
        assert os.path.exists(path), f"Missing: {fname}"
        assert os.path.getsize(path) > 0, f"Empty: {fname}"


def test_sf_dry_run_writes_5_files(sf_generator, tmp_path):
    sf_generator.run()
    expected = [
        "acme_saas_salesforce_setup_plan.json",
        "acme_saas_salesforce_setup_report.md",
        "acme_saas_salesforce_field_inventory.csv",
        "acme_saas_salesforce_pipeline_plan.csv",
        "acme_saas_salesforce_validation_report.json",
    ]
    for fname in expected:
        path = os.path.join(str(tmp_path), fname)
        assert os.path.exists(path), f"Missing: {fname}"


def test_setup_plan_json_is_valid(hs_generator, tmp_path):
    hs_generator.run()
    path = os.path.join(str(tmp_path), "acme_saas_hubspot_setup_plan.json")
    with open(path) as fh:
        data = json.load(fh)
    assert "client_name" in data
    assert "fields" in data
    assert "pipelines" in data
    assert "stages" in data


def test_summary_counts_match_report(hs_generator):
    report = hs_generator.run()
    summary = report.summary()
    assert summary["fields_planned"] == len(report.fields_by_status(FieldStatus.PLANNED))
    assert summary["stages_planned"] == len([s for s in report.stages if s.status == FieldStatus.PLANNED])
