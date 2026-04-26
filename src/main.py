"""
GTM System MVP — main orchestrator.
Runs the full pipeline end-to-end and writes checkpoint CSV files to outputs/.

Pipeline: Apollo ingestion -> Clay enrichment -> ICP scoring -> Contact discovery
          -> Email validation -> HubSpot sync -> Outreach export -> Campaign monitoring
"""

from __future__ import annotations
import logging
import os
import sys

import pandas as pd

BASE_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR   = os.path.join(BASE_DIR, "data")
CONFIG_DIR = os.path.join(BASE_DIR, "config")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")

sys.path.insert(0, BASE_DIR)

from src.ingestion.company_ingestion import load_companies
from src.scoring.icp_scoring import load_icp_rules, score_companies
from src.enrichment.clay_mock_enrichment import enrich_accounts
from src.validation.email_validation_mock import (
    load_contacts,
    filter_contacts_for_approved_accounts,
    validate_contacts,
)
from src.hubspot.hubspot_sync_mock import (
    create_hubspot_company_records,
    create_hubspot_contact_records,
)
from src.outreach.sequence_export import (
    create_email_sequence_export,
    create_linkedin_sequence_export,
)
from src.monitoring.campaign_health import load_campaign_metrics, evaluate_all_campaigns

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def save(df: pd.DataFrame, filename: str) -> str:
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    path = os.path.join(OUTPUT_DIR, filename)
    df.to_csv(path, index=False)
    return path


# ── Stage functions ───────────────────────────────────────────────────────────

def run_ingestion() -> list[dict]:
    companies = load_companies(os.path.join(DATA_DIR, "fake_companies.json"))
    cols = [
        "company_id", "company_name", "website", "domain", "industry",
        "employee_count", "revenue_range", "state",
        "medicaid_members", "medicare_members",
        "growth_signal", "hiring_signal", "tech_stack_signal",
        "ingestion_source", "ingestion_status",
    ]
    save(pd.DataFrame(companies)[cols], "01_apollo_company_ingestion.csv")
    log.info("01 Apollo ingestion — %d companies loaded", len(companies))
    return companies


def run_enrichment_and_scoring(companies: list[dict]) -> list[dict]:
    icp_rules = load_icp_rules(os.path.join(CONFIG_DIR, "icp_rules.json"))
    scored    = score_companies([dict(c) for c in companies], icp_rules)
    enriched  = enrich_accounts(scored)

    enrichment_cols = [
        "company_id", "company_name", "domain", "industry", "employee_count",
        "state", "medicaid_members", "medicare_members",
        "growth_signal", "hiring_signal", "tech_stack_signal",
        "enrichment_status", "enrichment_source",
        "recommended_personas", "enriched_signal_summary",
    ]
    scoring_cols = [
        "company_id", "company_name", "domain", "industry", "employee_count",
        "state", "total_member_volume",
        "industry_score", "member_volume_score", "employee_count_score",
        "growth_signal_score", "hiring_signal_score", "tech_stack_score",
        "icp_score", "icp_tier", "score_reason", "tier_reason",
    ]
    save(pd.DataFrame(enriched)[enrichment_cols], "02_clay_enriched_accounts.csv")
    save(pd.DataFrame(enriched)[scoring_cols],    "03_icp_scored_accounts.csv")

    t1 = sum(1 for c in enriched if c["icp_tier"] == "Tier 1")
    t2 = sum(1 for c in enriched if c["icp_tier"] == "Tier 2")
    log.info("02-03 Clay + ICP scoring — Tier 1: %d  Tier 2: %d  of %d", t1, t2, len(enriched))
    return enriched


def run_tier_distribution(enriched: list[dict]) -> None:
    tier_counts = (
        pd.DataFrame(enriched)["icp_tier"]
        .value_counts()
        .reset_index()
    )
    tier_counts.columns = ["icp_tier", "account_count"]
    total = tier_counts["account_count"].sum()
    tier_counts["percentage_of_total"] = (
        tier_counts["account_count"] / total * 100
    ).map(lambda x: f"{x:.1f}%")
    save(tier_counts, "04_icp_tier_distribution.csv")
    log.info("04 Tier distribution saved")


def run_approved_accounts(enriched: list[dict]) -> list[dict]:
    rows = []
    for c in enriched:
        rows.append({
            "company_id": c["company_id"],
            "company_name": c["company_name"],
            "domain": c["domain"],
            "industry": c["industry"],
            "state": c["state"],
            "icp_score": c["icp_score"],
            "icp_tier": c["icp_tier"],
            "recommended_personas": c["recommended_personas"],
            "contact_discovery_approved": c["contact_discovery_approved"],
            "approval_reason": (
                "Tier 1 or Tier 2 — approved for contact discovery"
                if c["contact_discovery_approved"]
                else f"{c['icp_tier']} — not approved"
            ),
        })
    save(pd.DataFrame(rows), "05_approved_accounts_for_contact_discovery.csv")
    approved = [c for c in enriched if c.get("contact_discovery_approved")]
    log.info("05 Approved accounts — %d approved, %d blocked", len(approved), len(enriched) - len(approved))
    return approved


def run_contact_discovery(enriched: list[dict], approved_cos: list[dict]) -> list[dict]:
    all_contacts = load_contacts(os.path.join(DATA_DIR, "fake_contacts.json"))
    co_name_map  = {c["company_id"]: c["company_name"] for c in enriched}
    co_tier_map  = {c["company_id"]: c["icp_tier"]     for c in enriched}

    contacts = filter_contacts_for_approved_accounts(all_contacts, approved_cos)
    for ct in contacts:
        ct["icp_tier"]                 = co_tier_map.get(ct["company_id"], "")
        ct["company_name"]             = co_name_map.get(ct["company_id"], "")
        ct["contact_source"]           = "fake_data"
        ct["contact_discovery_status"] = "discovered"

    cols = [
        "contact_id", "company_id", "company_name", "first_name", "last_name",
        "title", "email", "linkedin_url", "persona_type",
        "icp_tier", "contact_source", "contact_discovery_status",
    ]
    save(pd.DataFrame(contacts)[cols], "06_discovered_contacts.csv")
    log.info("06 Contact discovery — %d contacts found", len(contacts))
    return contacts


def run_validation(contacts: list[dict]) -> list[dict]:
    validated = validate_contacts([dict(c) for c in contacts])

    zb_cols = [
        "contact_id", "company_id", "company_name", "first_name", "last_name", "email",
        "zerobounce_status", "zerobounce_reason",
    ]
    nb_cols = [
        "contact_id", "company_id", "company_name", "first_name", "last_name", "email",
        "zerobounce_status", "neverbounce_status", "neverbounce_reason",
    ]
    final_cols = [
        "contact_id", "company_id", "company_name", "first_name", "last_name",
        "title", "email", "linkedin_url", "persona_type", "icp_tier",
        "zerobounce_status", "neverbounce_status",
        "final_validation_status", "final_validation_reason",
    ]
    save(pd.DataFrame(validated)[zb_cols],    "07_zerobounce_validation.csv")
    save(pd.DataFrame(validated)[nb_cols],    "08_neverbounce_validation.csv")
    save(pd.DataFrame(validated)[final_cols], "09_final_validated_contacts.csv")

    approved   = sum(1 for c in validated if c.get("final_validation_status") == "approved")
    review     = sum(1 for c in validated if c.get("final_validation_status") == "review")
    suppressed = sum(1 for c in validated if c.get("final_validation_status") == "suppressed")
    log.info("07-09 Validation — approved: %d  review: %d  suppressed: %d", approved, review, suppressed)
    return validated


def run_approved_contacts(validated: list[dict]) -> list[dict]:
    rows = []
    for ct in validated:
        status = ct.get("final_validation_status")
        rows.append({
            "contact_id": ct["contact_id"],
            "company_id": ct["company_id"],
            "company_name": ct.get("company_name", ""),
            "first_name": ct["first_name"],
            "last_name": ct["last_name"],
            "title": ct["title"],
            "email": ct["email"],
            "linkedin_url": ct["linkedin_url"],
            "persona_type": ct["persona_type"],
            "icp_tier": ct.get("icp_tier", ""),
            "final_validation_status": status,
            "approved_for_hubspot":  status in ("approved", "review"),
            "approved_for_outreach": status == "approved",
        })
    save(pd.DataFrame(rows), "10_approved_contacts_for_hubspot_and_outreach.csv")
    approved = [ct for ct in validated if ct.get("final_validation_status") == "approved"]
    log.info("10 Approved contacts — %d ready for outreach", len(approved))
    return approved


def run_hubspot_sync(enriched: list[dict], validated: list[dict]) -> tuple[list[dict], list[dict]]:
    hs_companies = create_hubspot_company_records(enriched)
    hs_contacts  = create_hubspot_contact_records(validated, enriched)
    save(pd.DataFrame(hs_companies), "11_hubspot_companies.csv")
    save(pd.DataFrame(hs_contacts),  "12_hubspot_contacts.csv")
    log.info("11-12 HubSpot sync — %d companies, %d contacts", len(hs_companies), len(hs_contacts))
    return hs_companies, hs_contacts


def run_outreach_export(approved_contacts: list[dict], enriched: list[dict]) -> tuple[list[dict], list[dict]]:
    co_name_map = {c["company_id"]: c["company_name"] for c in enriched}
    for ct in approved_contacts:
        if not ct.get("company_name"):
            ct["company_name"] = co_name_map.get(ct["company_id"], "")

    email_export    = create_email_sequence_export(approved_contacts)
    linkedin_export = create_linkedin_sequence_export(approved_contacts)
    save(pd.DataFrame(email_export),    "13_email_sequence_export.csv")
    save(pd.DataFrame(linkedin_export), "14_linkedin_sequence_export.csv")
    log.info("13-14 Outreach export — %d email, %d LinkedIn sequences", len(email_export), len(linkedin_export))
    return email_export, linkedin_export


def run_campaign_monitoring() -> tuple[list[dict], list[dict]]:
    raw_metrics   = load_campaign_metrics(os.path.join(DATA_DIR, "fake_campaign_metrics.json"))
    health_report = evaluate_all_campaigns(raw_metrics)
    save(pd.DataFrame(raw_metrics),   "15_campaign_metrics_input.csv")
    save(pd.DataFrame(health_report), "16_campaign_health_report.csv")
    critical = sum(1 for h in health_report if h.get("health_status") == "critical")
    log.info("15-16 Campaign monitoring — %d campaigns, %d critical", len(health_report), critical)
    return raw_metrics, health_report


# ── Orchestrator ──────────────────────────────────────────────────────────────

def main() -> None:
    log.info("GTM pipeline starting")

    companies       = run_ingestion()
    enriched        = run_enrichment_and_scoring(companies)
    run_tier_distribution(enriched)
    approved_cos    = run_approved_accounts(enriched)
    contacts        = run_contact_discovery(enriched, approved_cos)
    validated       = run_validation(contacts)
    approved_cts    = run_approved_contacts(validated)
    run_hubspot_sync(enriched, validated)
    email_exp, li_exp = run_outreach_export(approved_cts, enriched)
    run_campaign_monitoring()

    log.info("Pipeline complete — 16 CSV files written to outputs/")
    print()
    print(f"  Companies loaded:          {len(companies)}")
    print(f"  Companies approved:        {len(approved_cos)}")
    print(f"  Contacts discovered:       {len(contacts)}")
    print(f"  Contacts validated:        {len(validated)}")
    print(f"  Contacts approved:         {len(approved_cts)}")
    print(f"  Email sequence records:    {len(email_exp)}")
    print(f"  LinkedIn sequence records: {len(li_exp)}")
    print()


if __name__ == "__main__":
    main()
