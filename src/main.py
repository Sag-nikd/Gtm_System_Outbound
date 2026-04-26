"""
GTM System MVP — main orchestrator.
Runs the full pipeline end-to-end and writes 16 checkpoint CSV files to outputs/.

This Python layer acts as the integration orchestration engine (like Zapier/n8n),
connecting each GTM stage: ingestion ->enrichment ->scoring ->validation →
CRM sync ->outreach export ->campaign monitoring.
"""

import os
import sys

import pandas as pd

# Resolve paths relative to this file so the script works from any working directory
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
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


def save(df: pd.DataFrame, filename: str) -> str:
    path = os.path.join(OUTPUT_DIR, filename)
    df.to_csv(path, index=False)
    return path


def main() -> None:
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # ── 01  Company ingestion ──────────────────────────────────────────────
    companies = load_companies(os.path.join(DATA_DIR, "fake_companies.json"))
    df01 = pd.DataFrame(companies)[[
        "company_id", "company_name", "website", "domain", "industry",
        "employee_count", "revenue_range", "state",
        "medicaid_members", "medicare_members",
        "growth_signal", "hiring_signal", "tech_stack_signal",
        "ingestion_source", "ingestion_status",
    ]]
    save(df01, "01_apollo_company_ingestion.csv")
    print(f"[01] Apollo/company ingestion completed ->outputs/01_apollo_company_ingestion.csv")

    # ── 02  Clay enrichment ───────────────────────────────────────────────
    icp_rules = load_icp_rules(os.path.join(CONFIG_DIR, "icp_rules.json"))
    # Score first so enrichment can read icp_tier
    scored_temp = score_companies([dict(c) for c in companies], icp_rules)
    enriched_companies = enrich_accounts(scored_temp)

    df02 = pd.DataFrame(enriched_companies)[[
        "company_id", "company_name", "domain", "industry", "employee_count",
        "state", "medicaid_members", "medicare_members",
        "growth_signal", "hiring_signal", "tech_stack_signal",
        "enrichment_status", "enrichment_source",
        "recommended_personas", "enriched_signal_summary",
    ]]
    save(df02, "02_clay_enriched_accounts.csv")
    print(f"[02] Clay enrichment completed ->outputs/02_clay_enriched_accounts.csv")

    # ── 03  ICP scoring ───────────────────────────────────────────────────
    df03 = pd.DataFrame(enriched_companies)[[
        "company_id", "company_name", "domain", "industry", "employee_count",
        "state", "total_member_volume",
        "industry_score", "member_volume_score", "employee_count_score",
        "growth_signal_score", "hiring_signal_score", "tech_stack_score",
        "icp_score", "icp_tier", "score_reason", "tier_reason",
    ]]
    save(df03, "03_icp_scored_accounts.csv")
    print(f"[03] ICP scoring completed ->outputs/03_icp_scored_accounts.csv")

    # ── 04  Tier distribution ─────────────────────────────────────────────
    tier_counts = (
        pd.DataFrame(enriched_companies)["icp_tier"]
        .value_counts()
        .reset_index()
        .rename(columns={"icp_tier": "icp_tier", "count": "account_count"})
    )
    tier_counts.columns = ["icp_tier", "account_count"]
    total = tier_counts["account_count"].sum()
    tier_counts["percentage_of_total"] = (
        tier_counts["account_count"] / total * 100
    ).map(lambda x: f"{x:.1f}%")
    save(tier_counts, "04_icp_tier_distribution.csv")
    print(f"[04] ICP tier distribution completed ->outputs/04_icp_tier_distribution.csv")

    # ── 05  Approved accounts ─────────────────────────────────────────────
    approved_companies = [
        c for c in enriched_companies if c.get("contact_discovery_approved")
    ]
    df05_rows = []
    for c in enriched_companies:
        df05_rows.append({
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
    save(pd.DataFrame(df05_rows), "05_approved_accounts_for_contact_discovery.csv")
    print(f"[05] Approved accounts exported ->outputs/05_approved_accounts_for_contact_discovery.csv")

    # ── 06  Contact discovery ─────────────────────────────────────────────
    all_contacts = load_contacts(os.path.join(DATA_DIR, "fake_contacts.json"))
    company_tier_map = {c["company_id"]: c["icp_tier"] for c in enriched_companies}
    company_name_map = {c["company_id"]: c["company_name"] for c in enriched_companies}

    filtered_contacts = filter_contacts_for_approved_accounts(all_contacts, approved_companies)
    for ct in filtered_contacts:
        ct["icp_tier"] = company_tier_map.get(ct["company_id"], "")
        ct["company_name"] = company_name_map.get(ct["company_id"], "")
        ct["contact_source"] = "fake_data"   # Future: Apollo, Clay
        ct["contact_discovery_status"] = "discovered"

    df06_cols = [
        "contact_id", "company_id", "company_name", "first_name", "last_name",
        "title", "email", "linkedin_url", "persona_type",
        "icp_tier", "contact_source", "contact_discovery_status",
    ]
    save(pd.DataFrame(filtered_contacts)[df06_cols], "06_discovered_contacts.csv")
    print(f"[06] Contact discovery completed ->outputs/06_discovered_contacts.csv")

    # ── 07  ZeroBounce validation ──────────────────────────────────────────
    # Run validation pipeline (adds zb + nb + final fields)
    validated_contacts = validate_contacts([dict(c) for c in filtered_contacts])

    df07_cols = [
        "contact_id", "company_id", "company_name",
        "first_name", "last_name", "email",
        "zerobounce_status", "zerobounce_reason",
    ]
    for ct in validated_contacts:
        ct["validation_step"] = "zerobounce_mock"
    save(
        pd.DataFrame(validated_contacts)[df07_cols + ["validation_step"]],
        "07_zerobounce_validation.csv",
    )
    print(f"[07] ZeroBounce validation completed ->outputs/07_zerobounce_validation.csv")

    # ── 08  NeverBounce validation ────────────────────────────────────────
    df08_cols = [
        "contact_id", "company_id", "company_name",
        "first_name", "last_name", "email",
        "zerobounce_status", "neverbounce_status", "neverbounce_reason",
    ]
    for ct in validated_contacts:
        ct["validation_step"] = "neverbounce_mock"
    save(
        pd.DataFrame(validated_contacts)[df08_cols + ["validation_step"]],
        "08_neverbounce_validation.csv",
    )
    print(f"[08] NeverBounce validation completed ->outputs/08_neverbounce_validation.csv")

    # ── 09  Final validated contacts ──────────────────────────────────────
    df09_cols = [
        "contact_id", "company_id", "company_name", "first_name", "last_name",
        "title", "email", "linkedin_url", "persona_type", "icp_tier",
        "zerobounce_status", "neverbounce_status",
        "final_validation_status", "final_validation_reason",
    ]
    save(pd.DataFrame(validated_contacts)[df09_cols], "09_final_validated_contacts.csv")
    print(f"[09] Final validation completed ->outputs/09_final_validated_contacts.csv")

    # ── 10  Approved contacts ─────────────────────────────────────────────
    approved_contacts = [
        c for c in validated_contacts if c.get("final_validation_status") == "approved"
    ]
    df10_rows = []
    for ct in validated_contacts:
        status = ct.get("final_validation_status")
        df10_rows.append({
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
            "approved_for_hubspot": status in ("approved", "review"),
            "approved_for_outreach": status == "approved",
        })
    save(pd.DataFrame(df10_rows), "10_approved_contacts_for_hubspot_and_outreach.csv")
    print(f"[10] Approved contacts exported ->outputs/10_approved_contacts_for_hubspot_and_outreach.csv")

    # ── 11  HubSpot companies ─────────────────────────────────────────────
    hs_companies = create_hubspot_company_records(enriched_companies)
    save(pd.DataFrame(hs_companies), "11_hubspot_companies.csv")
    print(f"[11] HubSpot companies export completed ->outputs/11_hubspot_companies.csv")

    # ── 12  HubSpot contacts ──────────────────────────────────────────────
    hs_contacts = create_hubspot_contact_records(validated_contacts, enriched_companies)
    save(pd.DataFrame(hs_contacts), "12_hubspot_contacts.csv")
    print(f"[12] HubSpot contacts export completed ->outputs/12_hubspot_contacts.csv")

    # ── 13  Email sequence export ─────────────────────────────────────────
    # Attach company_name to each contact for sequence exports
    for ct in approved_contacts:
        if not ct.get("company_name"):
            ct["company_name"] = company_name_map.get(ct["company_id"], "")

    email_export = create_email_sequence_export(approved_contacts)
    save(pd.DataFrame(email_export), "13_email_sequence_export.csv")
    print(f"[13] Email sequence export completed ->outputs/13_email_sequence_export.csv")

    # ── 14  LinkedIn sequence export ──────────────────────────────────────
    linkedin_export = create_linkedin_sequence_export(approved_contacts)
    save(pd.DataFrame(linkedin_export), "14_linkedin_sequence_export.csv")
    print(f"[14] LinkedIn sequence export completed ->outputs/14_linkedin_sequence_export.csv")

    # ── 15  Campaign metrics input ────────────────────────────────────────
    raw_metrics = load_campaign_metrics(os.path.join(DATA_DIR, "fake_campaign_metrics.json"))
    save(pd.DataFrame(raw_metrics), "15_campaign_metrics_input.csv")
    print(f"[15] Campaign metrics input exported ->outputs/15_campaign_metrics_input.csv")

    # ── 16  Campaign health report ────────────────────────────────────────
    health_report = evaluate_all_campaigns(raw_metrics)
    save(pd.DataFrame(health_report), "16_campaign_health_report.csv")
    print(f"[16] Campaign health report completed ->outputs/16_campaign_health_report.csv")

    # ── Summary ───────────────────────────────────────────────────────────
    print()
    print(f"  Companies loaded:          {len(companies)}")
    print(f"  Companies approved:        {len(approved_companies)}")
    print(f"  Contacts discovered:       {len(filtered_contacts)}")
    print(f"  Contacts validated:        {len(validated_contacts)}")
    print(f"  Contacts approved:         {len(approved_contacts)}")
    print(f"  Email sequence records:    {len(email_export)}")
    print(f"  LinkedIn sequence records: {len(linkedin_export)}")
    print()
    print("GTM system MVP run completed successfully.")


if __name__ == "__main__":
    main()
