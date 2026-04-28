from __future__ import annotations

import hashlib
import json
import os
import sys
import uuid
from datetime import datetime, timezone
from typing import List, Tuple

import pandas as pd

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from src.config.settings import settings
from src.utils.logger import get_logger

from src.integrations.apollo import ApolloMockClient, ApolloAPIClient
from src.integrations.clay import ClayMockClient, ClayAPIClient
from src.integrations.hubspot import HubSpotMockClient, HubSpotAPIClient
from src.integrations.zerobounce import ZeroBounceMockClient, ZeroBounceAPIClient
from src.integrations.neverbounce import NeverBounceMockClient, NeverBounceAPIClient
from src.integrations.validity import ValidityMockClient, ValidityAPIClient

from src.scoring.icp_scoring import load_icp_rules, score_companies
from src.validation.email_validation_mock import filter_contacts_for_approved_accounts
from src.outreach.sequence_export import (
    create_email_sequence_export,
    create_linkedin_sequence_export,
)
from src.monitoring.campaign_health import evaluate_all_campaigns

log = get_logger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _save(df: pd.DataFrame, filename: str) -> str:
    os.makedirs(settings.OUTPUT_DIR, exist_ok=True)
    path = os.path.join(settings.OUTPUT_DIR, filename)
    df.to_csv(path, index=False)
    log.info("Saved %s (%d rows)", filename, len(df))
    return path


def _get_clients() -> Tuple:
    if settings.MOCK_MODE:
        return (
            ApolloMockClient(),
            ClayMockClient(),
            HubSpotMockClient(),
            ZeroBounceMockClient(),
            NeverBounceMockClient(),
            ValidityMockClient(),
        )
    return (
        ApolloAPIClient(settings.APOLLO_API_KEY),
        ClayAPIClient(settings.CLAY_API_KEY),
        HubSpotAPIClient(settings.HUBSPOT_PRIVATE_APP_TOKEN),
        ZeroBounceAPIClient(settings.ZEROBOUNCE_API_KEY),
        NeverBounceAPIClient(settings.NEVERBOUNCE_API_KEY),
        ValidityAPIClient(settings.VALIDITY_API_KEY),
    )


# ── Pipeline stages ───────────────────────────────────────────────────────────

def run_company_pipeline(apollo, clay) -> List[dict]:
    """
    Stage 1: Apollo ingestion → ICP scoring → Clay enrichment → approval gate.
    Outputs: 01_company_ingestion.csv, 02_company_enrichment.csv,
             03_icp_scored_accounts.csv, 04_approved_accounts.csv
    """
    try:
        # Apollo: fetch companies
        companies = apollo.get_companies(
            os.path.join(settings.DATA_DIR, "fake_companies.json")
        )
        log.info("Companies loaded: %d", len(companies))
        _save(
            pd.DataFrame(companies)[[
                "company_id", "company_name", "website", "domain", "industry",
                "employee_count", "revenue_range", "state",
                "medicaid_members", "medicare_members",
                "growth_signal", "hiring_signal", "tech_stack_signal",
                "ingestion_source", "ingestion_status",
            ]],
            "01_company_ingestion.csv",
        )

        # ICP scoring (internal — not an external API)
        icp_rules = load_icp_rules(
            os.path.join(settings.CONFIG_DIR, "icp_rules.json")
        )
        scored = score_companies([dict(c) for c in companies], icp_rules)

        # Clay: enrich accounts
        enriched = clay.enrich_accounts(scored)
        t1 = sum(1 for c in enriched if c.get("icp_tier") == "Tier 1")
        t2 = sum(1 for c in enriched if c.get("icp_tier") == "Tier 2")
        log.info("Tier distribution — Tier 1: %d  Tier 2: %d  of %d total",
                 t1, t2, len(enriched))

        _save(
            pd.DataFrame(enriched)[[
                "company_id", "company_name", "domain", "industry", "employee_count",
                "state", "medicaid_members", "medicare_members",
                "growth_signal", "hiring_signal", "tech_stack_signal",
                "enrichment_status", "enrichment_source",
                "recommended_personas", "enriched_signal_summary",
            ]],
            "02_company_enrichment.csv",
        )
        _save(
            pd.DataFrame(enriched)[[
                "company_id", "company_name", "domain", "industry", "employee_count",
                "state", "total_member_volume",
                "industry_score", "member_volume_score", "employee_count_score",
                "growth_signal_score", "hiring_signal_score", "tech_stack_score",
                "icp_score", "icp_tier", "score_reason", "tier_reason",
            ]],
            "03_icp_scored_accounts.csv",
        )

        # Approval gate
        approved = [c for c in enriched if c.get("contact_discovery_approved")]
        blocked = len(enriched) - len(approved)
        log.info("Approved accounts: %d  |  Blocked: %d", len(approved), blocked)

        approval_rows = [
            {
                "company_id": c["company_id"],
                "company_name": c["company_name"],
                "domain": c.get("domain", ""),
                "industry": c["industry"],
                "state": c["state"],
                "icp_score": c["icp_score"],
                "icp_tier": c["icp_tier"],
                "recommended_personas": c.get("recommended_personas", ""),
                "contact_discovery_approved": c.get("contact_discovery_approved"),
                "approval_reason": (
                    "Tier 1 or Tier 2 — approved for contact discovery"
                    if c.get("contact_discovery_approved")
                    else f"{c['icp_tier']} — not approved"
                ),
            }
            for c in enriched
        ]
        _save(pd.DataFrame(approval_rows), "04_approved_accounts.csv")

        return enriched

    except Exception as exc:
        log.error("Company pipeline failed: %s", exc)
        raise


def run_contact_pipeline(enriched: List[dict], apollo, zerobounce, neverbounce) -> List[dict]:
    """
    Stage 2: Contact discovery → ZeroBounce → NeverBounce → final decision.
    Outputs: 05_discovered_contacts.csv, 06_email_validation_results.csv
    """
    try:
        approved_cos = [c for c in enriched if c.get("contact_discovery_approved")]
        co_name_map = {c["company_id"]: c["company_name"] for c in enriched}
        co_tier_map = {c["company_id"]: c["icp_tier"] for c in enriched}

        # Apollo: fetch contacts
        all_contacts = apollo.get_contacts(
            os.path.join(settings.DATA_DIR, "fake_contacts.json")
        )
        contacts = filter_contacts_for_approved_accounts(all_contacts, approved_cos)
        for ct in contacts:
            ct["company_name"] = co_name_map.get(ct["company_id"], "")
            ct["icp_tier"] = co_tier_map.get(ct["company_id"], "")
            ct["contact_source"] = "fake_data"
            ct["contact_discovery_status"] = "discovered"

        log.info("Contacts discovered: %d", len(contacts))
        _save(
            pd.DataFrame(contacts)[[
                "contact_id", "company_id", "company_name",
                "first_name", "last_name", "title",
                "email", "linkedin_url", "persona_type",
                "icp_tier", "contact_source", "contact_discovery_status",
            ]],
            "05_discovered_contacts.csv",
        )

        # ZeroBounce: validate (also populates neverbounce fields in mock)
        validated = zerobounce.validate_contacts([dict(c) for c in contacts])

        # NeverBounce: second-pass (pass-through in mock, real API call in production)
        validated = neverbounce.validate_contacts(validated)

        n_approved = sum(1 for c in validated if c.get("final_validation_status") == "approved")
        n_review = sum(1 for c in validated if c.get("final_validation_status") == "review")
        n_suppressed = sum(1 for c in validated if c.get("final_validation_status") == "suppressed")
        log.info("Validation results — approved: %d  review: %d  suppressed: %d",
                 n_approved, n_review, n_suppressed)

        _save(
            pd.DataFrame(validated)[[
                "contact_id", "company_id", "company_name",
                "first_name", "last_name", "title",
                "email", "linkedin_url", "persona_type", "icp_tier",
                "zerobounce_status", "zerobounce_reason",
                "neverbounce_status", "neverbounce_reason",
                "final_validation_status", "final_validation_reason",
            ]],
            "06_email_validation_results.csv",
        )

        return validated

    except Exception as exc:
        log.error("Contact pipeline failed: %s", exc)
        raise


def run_activation_pipeline(
    validated: List[dict], enriched: List[dict], hubspot
) -> None:
    """
    Stage 3: HubSpot sync → email sequence export → LinkedIn sequence export.
    Outputs: 07_hubspot_company_export.csv, 08_hubspot_contact_export.csv,
             09_email_sequence_export.csv, 10_linkedin_outreach_export.csv
    """
    try:
        hs_companies = hubspot.upsert_companies(enriched)
        _save(pd.DataFrame(hs_companies), "07_hubspot_company_export.csv")
        log.info("HubSpot company records: %d", len(hs_companies))

        hs_contacts = hubspot.upsert_contacts(validated, enriched)
        _save(pd.DataFrame(hs_contacts), "08_hubspot_contact_export.csv")
        log.info("HubSpot contact records: %d", len(hs_contacts))

        # Only approved contacts go to outreach sequences
        co_name_map = {c["company_id"]: c["company_name"] for c in enriched}
        approved_cts = [
            c for c in validated if c.get("final_validation_status") == "approved"
        ]
        for ct in approved_cts:
            if not ct.get("company_name"):
                ct["company_name"] = co_name_map.get(ct["company_id"], "")

        email_export = create_email_sequence_export(approved_cts)
        _save(pd.DataFrame(email_export), "09_email_sequence_export.csv")
        log.info("Email sequence records: %d", len(email_export))

        linkedin_export = create_linkedin_sequence_export(approved_cts)
        _save(pd.DataFrame(linkedin_export), "10_linkedin_outreach_export.csv")
        log.info("LinkedIn sequence records: %d", len(linkedin_export))

    except Exception as exc:
        log.error("Activation pipeline failed: %s", exc)
        raise


def run_campaign_monitoring(validity) -> None:
    """
    Stage 4: Fetch campaign metrics → evaluate health → write report.
    Output: 11_campaign_health_report.csv
    """
    try:
        raw_metrics = validity.get_campaign_metrics(
            os.path.join(settings.DATA_DIR, "fake_campaign_metrics.json")
        )
        health_report = evaluate_all_campaigns(raw_metrics)

        critical = sum(1 for h in health_report if h.get("health_status") == "critical")
        log.info("Campaign health — %d campaigns, %d critical", len(health_report), critical)

        _save(pd.DataFrame(health_report), "11_campaign_health_report.csv")

    except Exception as exc:
        log.error("Campaign monitoring failed: %s", exc)
        raise


# ── Orchestrator ──────────────────────────────────────────────────────────────

def _config_hash() -> str:
    path = os.path.join(settings.CONFIG_DIR, "icp_rules.json")
    try:
        with open(path, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()
    except Exception:
        return ""


def _stage_entry(name: str, record_count: int, status: str = "completed") -> dict:
    return {"name": name, "record_count": record_count, "status": status}


def main() -> None:
    log.info("GTM pipeline starting — MOCK_MODE=%s", settings.MOCK_MODE)
    started_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    run_id = str(uuid.uuid4())
    stages = []

    apollo, clay, hubspot, zerobounce, neverbounce, validity = _get_clients()

    enriched = run_company_pipeline(apollo, clay)
    stages.append(_stage_entry("company_pipeline", len(enriched)))

    approved_companies = [c for c in enriched if c.get("contact_discovery_approved")]
    if not approved_companies:
        log.warning(
            "Circuit breaker: no approved companies — skipping contact pipeline and activation"
        )
        run_campaign_monitoring(validity)
        stages.append(_stage_entry("contact_pipeline", 0, "skipped"))
        stages.append(_stage_entry("activation_pipeline", 0, "skipped"))
        stages.append(_stage_entry("campaign_monitoring", 0, "completed"))
        _write_manifest(run_id, started_at, stages)
        return

    validated = run_contact_pipeline(enriched, apollo, zerobounce, neverbounce)
    stages.append(_stage_entry("contact_pipeline", len(validated)))

    approved_contacts = [
        c for c in validated if c.get("final_validation_status") == "approved"
    ]
    if not approved_contacts:
        log.warning(
            "Circuit breaker: no approved contacts — skipping activation pipeline"
        )
        run_campaign_monitoring(validity)
        stages.append(_stage_entry("activation_pipeline", 0, "skipped"))
        stages.append(_stage_entry("campaign_monitoring", 0, "completed"))
        _write_manifest(run_id, started_at, stages)
        return

    run_activation_pipeline(validated, enriched, hubspot)
    stages.append(_stage_entry("activation_pipeline", len(approved_contacts)))
    run_campaign_monitoring(validity)
    stages.append(_stage_entry("campaign_monitoring", 0, "completed"))

    _write_manifest(run_id, started_at, stages)
    log.info("Pipeline complete — 11 checkpoint CSVs written to %s", settings.OUTPUT_DIR)


def _write_manifest(run_id: str, started_at: str, stages: list) -> None:
    manifest = {
        "run_id": run_id,
        "started_at": started_at,
        "completed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "mock_mode": settings.MOCK_MODE,
        "stages": stages,
        "config_hash": _config_hash(),
    }
    os.makedirs(settings.OUTPUT_DIR, exist_ok=True)
    path = os.path.join(settings.OUTPUT_DIR, "run_manifest.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    log.info("Run manifest written: %s", path)


if __name__ == "__main__":
    main()
