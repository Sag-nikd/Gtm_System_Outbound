"""
GTM System MVP - Interactive Demo
Run: python demo.py

Step-by-step pipeline with y/n confirmation after every stage result.
Each tool saves to its own named folder: outputs/apollo/, outputs/clay/, etc.
Filename: <date_timestamp>.csv
"""

from __future__ import annotations
import os
import sys
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

import pandas as pd

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

DATA_DIR   = os.path.join(BASE_DIR, "data")
CONFIG_DIR = os.path.join(BASE_DIR, "config")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")

W = 90

TIER_ICON = {
    "Tier 1":       "[T1]",
    "Tier 2":       "[T2]",
    "Tier 3":       "[T3]",
    "Disqualified": "[DQ]",
}

HEALTH_ICON = {
    "healthy":         "[OK]      ",
    "needs_attention": "[WATCH]   ",
    "warning":         "[WARN]    ",
    "critical":        "[CRITICAL]",
}

VALID_ICON = {
    "approved":   "[APPROVED] ",
    "review":     "[REVIEW]   ",
    "suppressed": "[SUPPRESS] ",
}


# ── helpers ───────────────────────────────────────────────────────────────────

def sep(char="-"):
    print(char * W)


def header(title: str, tool: str = ""):
    print()
    sep("=")
    label = f"  [{tool}]  {title}" if tool else f"  {title}"
    print(label)
    sep("=")


def ts() -> str:
    return datetime.now().strftime("%Y-%m-%d_%H%M%S")


def save_stage(data: list[dict], tool_folder: str) -> str:
    folder = os.path.join(OUTPUT_DIR, tool_folder)
    os.makedirs(folder, exist_ok=True)
    filename = f"{ts()}.csv"
    path = os.path.join(folder, filename)
    pd.DataFrame(data).to_csv(path, index=False)
    print(f"  Saved -> outputs/{tool_folder}/{filename}")
    return path


def confirm(summary: str, next_tool: str) -> bool:
    """Show what just finished, then ask if user wants to proceed to the next tool."""
    print()
    sep("-")
    print(f"  DONE: {summary}")
    sep("-")
    ans = input(f"  >> Proceed to {next_tool}? [y/n]: ").strip().lower()
    print()
    if ans in ("y", "yes"):
        return True
    print(f"  Pipeline stopped after: {summary}")
    print()
    return False


def stop(summary: str):
    print()
    sep("-")
    print(f"  DONE: {summary}")
    sep("-")


# ── Stage renderers ───────────────────────────────────────────────────────────

def show_apollo(companies: list[dict]):
    header("APOLLO — Company Ingestion", "APOLLO")
    print(f"  Source : data/fake_companies.json  (Future: Apollo API)")
    print(f"  Records: {len(companies)} companies loaded and normalized")
    sep()
    fmt = "  {id:<6} {name:<32} {industry:<24} {emp:>8}  {state}"
    print(fmt.format(id="ID", name="Company", industry="Industry",
                     emp="Employees", state="State"))
    sep()
    for c in companies:
        print(fmt.format(
            id=c["company_id"],
            name=c["company_name"][:31],
            industry=c["industry"][:23],
            emp=f"{c['employee_count']:,}",
            state=c["state"],
        ))
    sep()


def show_clay(companies: list[dict]):
    header("CLAY — Enrichment + ICP Scoring", "CLAY")
    print("  Scoring weights: industry_fit=25  member_volume=25  employee_count=15")
    print("                   growth_signal=15  hiring_signal=10  tech_stack=10")
    print("  Tiers: Tier 1 = 80-100 | Tier 2 = 60-79 | Tier 3 = 40-59 | DQ = <40")
    sep()
    fmt = "  {tier:<6} {score:>6}  {name:<32} {industry:<22} {members:>12}"
    print(fmt.format(tier="Tier", score="Score", name="Company",
                     industry="Industry", members="Total Members"))
    sep()
    for c in sorted(companies, key=lambda x: x["icp_score"], reverse=True):
        icon = TIER_ICON.get(c["icp_tier"], "[?]")
        print(fmt.format(
            tier=icon,
            score=f"{c['icp_score']:.1f}",
            name=c["company_name"][:31],
            industry=c["industry"][:21],
            members=f"{c.get('total_member_volume', 0):,}",
        ))
    sep()


def show_icp_scoring(companies: list[dict]):
    header("ICP SCORING — Tier Distribution", "ICP")
    total = len(companies)
    tier_order = ["Tier 1", "Tier 2", "Tier 3", "Disqualified"]
    counts = {}
    for c in companies:
        counts[c["icp_tier"]] = counts.get(c["icp_tier"], 0) + 1
    sep()
    print(f"  {'Tier':<14} {'Count':>6}   {'Share':>7}   Bar")
    sep()
    for tier in tier_order:
        n = counts.get(tier, 0)
        pct = n / total * 100 if total else 0
        bar = "#" * int(pct / 5)
        print(f"  {TIER_ICON.get(tier, tier):<14} {n:>6}   {pct:>6.1f}%   {bar}")
    sep()
    print(f"  Total accounts: {total}")


def show_approved_accounts(companies: list[dict]):
    approved     = [c for c in companies if c.get("contact_discovery_approved")]
    not_approved = [c for c in companies if not c.get("contact_discovery_approved")]
    header("APPROVED ACCOUNTS — Contact Discovery Gate", "GATE")
    print(f"  Rule     : Tier 1 and Tier 2 only move forward")
    print(f"  Approved : {len(approved)} companies  |  Blocked: {len(not_approved)} companies")
    sep()
    print("  APPROVED FOR CONTACT DISCOVERY:")
    for c in approved:
        icon = TIER_ICON.get(c["icp_tier"], "")
        print(f"    {icon}  {c['company_name']:<34} score={c['icp_score']:.1f}  "
              f"personas: {c['recommended_personas'][:38]}")
    print()
    print("  BLOCKED:")
    for c in not_approved:
        icon = TIER_ICON.get(c["icp_tier"], "")
        print(f"    {icon}  {c['company_name']:<34} score={c['icp_score']:.1f}  -> not proceeding")
    sep()


def show_contact_discovery(contacts: list[dict]):
    header("CONTACT DISCOVERY — Apollo / Clay (mock)", "CONTACTS")
    print(f"  Contacts discovered for approved accounts: {len(contacts)}")
    sep()
    fmt = "  {cid:<6} {cname:<32} {name:<28} {persona}"
    print(fmt.format(cid="ID", cname="Company", name="Name + Title", persona="Persona"))
    sep()
    for ct in contacts:
        full = f"{ct['first_name']} {ct['last_name']} / {ct['title']}"
        print(fmt.format(
            cid=ct["contact_id"],
            cname=ct.get("company_name", "")[:31],
            name=full[:27],
            persona=ct["persona_type"][:30],
        ))
    sep()


def show_zerobounce(contacts: list[dict]):
    header("ZEROBOUNCE — Email Validation Pass 1", "ZEROBOUNCE")
    print("  Checking each email against ZeroBounce API (mock)")
    sep()
    fmt = "  {status:<12} {name:<28} {email:<40} {reason}"
    print(fmt.format(status="ZB Status", name="Name", email="Email", reason="Reason"))
    sep()
    for ct in contacts:
        name = f"{ct['first_name']} {ct['last_name']}"
        print(fmt.format(
            status=ct.get("zerobounce_status", "")[:11],
            name=name[:27],
            email=ct["email"][:39],
            reason=ct.get("zerobounce_reason", "")[:30],
        ))
    sep()
    valid   = sum(1 for c in contacts if c.get("zerobounce_status") == "valid")
    risky   = sum(1 for c in contacts if c.get("zerobounce_status") == "risky")
    invalid = sum(1 for c in contacts if c.get("zerobounce_status") == "invalid")
    print(f"  Valid: {valid}  |  Risky: {risky}  |  Invalid: {invalid}")


def show_neverbounce(contacts: list[dict]):
    header("NEVERBOUNCE — Email Validation Pass 2", "NEVERBOUNCE")
    print("  Cross-checking with NeverBounce API (mock)")
    sep()
    fmt = "  {zb:<10} {nb:<10} {name:<28} {email}"
    print(fmt.format(zb="ZeroBounce", nb="NeverBounce", name="Name", email="Email"))
    sep()
    for ct in contacts:
        name = f"{ct['first_name']} {ct['last_name']}"
        print(fmt.format(
            zb=ct.get("zerobounce_status", "")[:9],
            nb=ct.get("neverbounce_status", "")[:9],
            name=name[:27],
            email=ct["email"][:38],
        ))
    sep()


def show_final_validation(contacts: list[dict]):
    header("FINAL VALIDATION — Decision", "VALIDATION")
    print("  Logic: both valid=approved | one risky=review | any invalid=suppressed")
    sep()
    fmt = "  {icon:<12} {name:<28} {email:<40} {zb:<10} {nb}"
    print(fmt.format(icon="Decision", name="Name", email="Email",
                     zb="ZeroBounce", nb="NeverBounce"))
    sep()
    for ct in contacts:
        icon = VALID_ICON.get(ct.get("final_validation_status", ""), "[?]")
        name = f"{ct['first_name']} {ct['last_name']}"
        print(fmt.format(
            icon=icon,
            name=name[:27],
            email=ct["email"][:39],
            zb=ct.get("zerobounce_status", "")[:9],
            nb=ct.get("neverbounce_status", "")[:9],
        ))
    sep()
    approved   = sum(1 for c in contacts if c.get("final_validation_status") == "approved")
    review     = sum(1 for c in contacts if c.get("final_validation_status") == "review")
    suppressed = sum(1 for c in contacts if c.get("final_validation_status") == "suppressed")
    print(f"  Approved: {approved}  |  Review: {review}  |  Suppressed: {suppressed}")


def show_hubspot(hs_companies: list[dict], hs_contacts: list[dict]):
    header("HUBSPOT — CRM Sync (CSV ready / Future: HubSpot API)", "HUBSPOT")
    print("  Company lifecycle stages based on ICP tier + enrichment")
    print("  Contact lifecycle: Contact Validated | Nurture | Suppressed")
    sep()
    print("  COMPANY RECORDS:")
    fmt = "  {name:<32} {tier:<14} {score:>6}  {stage}"
    print(fmt.format(name="Company", tier="Tier", score="Score", stage="Lifecycle Stage"))
    sep("-")
    for c in hs_companies:
        print(fmt.format(
            name=str(c.get("company_name", ""))[:31],
            tier=str(c.get("icp_tier", ""))[:13],
            score=str(c.get("icp_score", "")),
            stage=str(c.get("lifecycle_stage", "")),
        ))
    print()
    print("  CONTACT RECORDS:")
    fmt2 = "  {name:<28} {company:<28} {stage}"
    print(fmt2.format(name="Contact", company="Company", stage="Lifecycle Stage"))
    sep("-")
    for ct in hs_contacts:
        name = f"{ct.get('first_name','')} {ct.get('last_name','')}"
        print(fmt2.format(
            name=name[:27],
            company=str(ct.get("company_name",""))[:27],
            stage=str(ct.get("lifecycle_stage","")),
        ))
    sep()


def show_outreach(email_export: list[dict], linkedin_export: list[dict]):
    header("OUTREACH — Email + LinkedIn Sequence Export", "OUTREACH")
    print("  Email    -> Future: Outreach / Instantly / Smartlead / HubSpot Sequences")
    print("  LinkedIn -> Future: HeyReach")
    sep()
    print(f"  EMAIL SEQUENCE  ({len(email_export)} contacts):")
    fmt = "  {name:<28} {company:<28} {tier:<8} {angle}"
    print(fmt.format(name="Contact", company="Company", tier="Tier", angle="Step 1 Angle"))
    sep("-")
    for r in email_export:
        name = f"{r['first_name']} {r['last_name']}"
        print(fmt.format(
            name=name[:27],
            company=str(r.get("company_name",""))[:27],
            tier=str(r.get("icp_tier",""))[:7],
            angle=str(r.get("email_step_1_angle",""))[:38],
        ))
    print()
    print(f"  LINKEDIN SEQUENCE  ({len(linkedin_export)} contacts):")
    fmt2 = "  {name:<28} {company:<28} {msg}"
    print(fmt2.format(name="Contact", company="Company", msg="Connection Message (preview)"))
    sep("-")
    for r in linkedin_export:
        name = f"{r['first_name']} {r['last_name']}"
        print(fmt2.format(
            name=name[:27],
            company=str(r.get("company_name",""))[:27],
            msg=str(r.get("connection_message",""))[:38],
        ))
    sep()


def show_campaign_health(metrics: list[dict], health: list[dict]):
    header("CAMPAIGN HEALTH — Monitoring (Future: Validity API)", "MONITORING")
    print("  Thresholds: bounce>4% | open<30% | reply<2% | spam>0.3% | domain<70")
    sep()
    fmt = "  {icon:<12} {name:<40} {issue:<28} {action}"
    print(fmt.format(icon="Status", name="Campaign", issue="Primary Issue", action="Recommended Action"))
    sep()
    for h in health:
        icon = HEALTH_ICON.get(h["health_status"], "[?]")
        print(fmt.format(
            icon=icon,
            name=h["campaign_name"][:39],
            issue=h["primary_issue"][:27],
            action=h["recommended_action"][:42],
        ))
    sep()


def show_final_summary(companies, contacts, email_export, linkedin_export):
    header("PIPELINE COMPLETE — Full Run Summary")
    sep()
    total         = len(companies)
    approved_co   = sum(1 for c in companies if c.get("contact_discovery_approved"))
    blocked_co    = total - approved_co
    total_ct      = len(contacts)
    approved_ct   = sum(1 for c in contacts if c.get("final_validation_status") == "approved")
    review_ct     = sum(1 for c in contacts if c.get("final_validation_status") == "review")
    suppressed_ct = sum(1 for c in contacts if c.get("final_validation_status") == "suppressed")

    print(f"  [APOLLO]      Companies ingested        : {total}")
    print(f"  [CLAY]        Tier 1 + Tier 2 approved  : {approved_co}  (blocked: {blocked_co})")
    print(f"  [CONTACTS]    Contacts discovered        : {total_ct}")
    print(f"  [ZEROBOUNCE]  Contacts approved          : {approved_ct}")
    print(f"  [NEVERBOUNCE] Contacts in review         : {review_ct}")
    print(f"  [VALIDATION]  Contacts suppressed        : {suppressed_ct}")
    print(f"  [OUTREACH]    Email sequence records     : {len(email_export)}")
    print(f"  [OUTREACH]    LinkedIn sequence records  : {len(linkedin_export)}")
    print()
    print(f"  Output folders:")
    folders = [
        "apollo", "clay", "icp_scoring", "approved_accounts",
        "contact_discovery", "zerobounce", "neverbounce", "final_validation",
        "approved_contacts", "hubspot_companies", "hubspot_contacts",
        "email_sequences", "linkedin_sequences", "campaign_metrics", "campaign_health",
    ]
    for f in folders:
        print(f"    outputs/{f}/")
    sep()
    print()
    print("  GTM System MVP run complete.")
    print()


# ── Main pipeline flow ────────────────────────────────────────────────────────

def run_demo():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print()
    sep("=")
    print("  GTM SYSTEM MVP  —  STEP-BY-STEP PIPELINE")
    print("  Apollo -> Clay -> ICP Scoring -> Validation -> HubSpot -> Outreach -> Monitoring")
    print("  Each tool saves to: outputs/<tool_name>/<date_timestamp>.csv")
    sep("=")
    ans = input("  >> Start pipeline? [y/n]: ").strip().lower()
    print()
    if ans not in ("y", "yes"):
        print("  Aborted.")
        return

    # ── APOLLO: Company ingestion ─────────────────────────────────────────
    companies = load_companies(os.path.join(DATA_DIR, "fake_companies.json"))
    show_apollo(companies)
    save_stage(companies, "apollo")
    if not confirm(
        f"Apollo complete — {len(companies)} companies ingested",
        "Clay (Enrichment + ICP Scoring)"
    ):
        return

    # ── CLAY: Enrichment + ICP scoring ───────────────────────────────────
    icp_rules = load_icp_rules(os.path.join(CONFIG_DIR, "icp_rules.json"))
    scored    = score_companies([dict(c) for c in companies], icp_rules)
    enriched  = enrich_accounts(scored)
    show_clay(enriched)
    save_stage(enriched, "clay")
    t1 = sum(1 for c in enriched if c["icp_tier"] == "Tier 1")
    t2 = sum(1 for c in enriched if c["icp_tier"] == "Tier 2")
    if not confirm(
        f"Clay complete — Tier 1: {t1}  Tier 2: {t2}  scored from {len(enriched)} accounts",
        "ICP Scoring (Tier Distribution)"
    ):
        return

    # ── ICP SCORING: Tier distribution ───────────────────────────────────
    show_icp_scoring(enriched)
    tier_order = ["Tier 1", "Tier 2", "Tier 3", "Disqualified"]
    counts = {}
    for c in enriched:
        counts[c["icp_tier"]] = counts.get(c["icp_tier"], 0) + 1
    total = len(enriched)
    tier_rows = [
        {"icp_tier": t, "account_count": counts.get(t, 0),
         "percentage": f"{counts.get(t,0)/total*100:.1f}%" if total else "0%"}
        for t in tier_order
    ]
    save_stage(tier_rows, "icp_scoring")
    if not confirm(
        f"ICP Scoring complete — {t1+t2} accounts eligible for contact discovery",
        "Approved Accounts Gate"
    ):
        return

    # ── APPROVED ACCOUNTS gate ────────────────────────────────────────────
    show_approved_accounts(enriched)
    approved_cos = [c for c in enriched if c.get("contact_discovery_approved")]
    blocked_cos  = [c for c in enriched if not c.get("contact_discovery_approved")]
    approved_rows = [
        {
            "company_id": c["company_id"],
            "company_name": c["company_name"],
            "icp_tier": c["icp_tier"],
            "icp_score": c["icp_score"],
            "contact_discovery_approved": c.get("contact_discovery_approved"),
        }
        for c in enriched
    ]
    save_stage(approved_rows, "approved_accounts")
    if not confirm(
        f"Gate complete — {len(approved_cos)} approved, {len(blocked_cos)} blocked",
        "Contact Discovery"
    ):
        return

    # ── CONTACT DISCOVERY ────────────────────────────────────────────────
    all_contacts = load_contacts(os.path.join(DATA_DIR, "fake_contacts.json"))
    co_name_map  = {c["company_id"]: c["company_name"] for c in enriched}
    co_tier_map  = {c["company_id"]: c["icp_tier"]     for c in enriched}
    filtered_cts = filter_contacts_for_approved_accounts(all_contacts, approved_cos)
    for ct in filtered_cts:
        ct["company_name"]             = co_name_map.get(ct["company_id"], "")
        ct["icp_tier"]                 = co_tier_map.get(ct["company_id"], "")
        ct["contact_source"]           = "fake_data"
        ct["contact_discovery_status"] = "discovered"
    show_contact_discovery(filtered_cts)
    save_stage(filtered_cts, "contact_discovery")
    if not confirm(
        f"Contact Discovery complete — {len(filtered_cts)} contacts found",
        "ZeroBounce Validation"
    ):
        return

    # ── ZEROBOUNCE: Pass 1 ───────────────────────────────────────────────
    validated_cts = validate_contacts([dict(c) for c in filtered_cts])
    show_zerobounce(validated_cts)
    zb_rows = [
        {"contact_id": c["contact_id"], "first_name": c["first_name"],
         "last_name": c["last_name"], "email": c["email"],
         "zerobounce_status": c.get("zerobounce_status"),
         "zerobounce_reason": c.get("zerobounce_reason")}
        for c in validated_cts
    ]
    save_stage(zb_rows, "zerobounce")
    zb_valid = sum(1 for c in validated_cts if c.get("zerobounce_status") == "valid")
    if not confirm(
        f"ZeroBounce complete — {zb_valid}/{len(validated_cts)} valid",
        "NeverBounce Validation"
    ):
        return

    # ── NEVERBOUNCE: Pass 2 ──────────────────────────────────────────────
    show_neverbounce(validated_cts)
    nb_rows = [
        {"contact_id": c["contact_id"], "first_name": c["first_name"],
         "last_name": c["last_name"], "email": c["email"],
         "zerobounce_status": c.get("zerobounce_status"),
         "neverbounce_status": c.get("neverbounce_status"),
         "neverbounce_reason": c.get("neverbounce_reason")}
        for c in validated_cts
    ]
    save_stage(nb_rows, "neverbounce")
    nb_valid = sum(1 for c in validated_cts if c.get("neverbounce_status") == "valid")
    if not confirm(
        f"NeverBounce complete — {nb_valid}/{len(validated_cts)} valid",
        "Final Validation Decision"
    ):
        return

    # ── FINAL VALIDATION decision ────────────────────────────────────────
    show_final_validation(validated_cts)
    save_stage(validated_cts, "final_validation")
    approved_cts = [c for c in validated_cts if c.get("final_validation_status") == "approved"]
    review_cts   = [c for c in validated_cts if c.get("final_validation_status") == "review"]
    supp_cts     = [c for c in validated_cts if c.get("final_validation_status") == "suppressed"]
    for ct in approved_cts:
        if not ct.get("company_name"):
            ct["company_name"] = co_name_map.get(ct["company_id"], "")

    approved_ct_rows = [
        {
            **{k: ct.get(k) for k in
               ("contact_id", "company_id", "first_name", "last_name", "email", "icp_tier")},
            "final_validation_status": ct.get("final_validation_status"),
            "approved_for_hubspot":  ct.get("final_validation_status") in ("approved", "review"),
            "approved_for_outreach": ct.get("final_validation_status") == "approved",
        }
        for ct in validated_cts
    ]
    save_stage(approved_ct_rows, "approved_contacts")
    if not confirm(
        f"Validation complete — approved: {len(approved_cts)}, review: {len(review_cts)}, suppressed: {len(supp_cts)}",
        "HubSpot CRM Sync"
    ):
        return

    # ── HUBSPOT: CRM sync ────────────────────────────────────────────────
    hs_companies = create_hubspot_company_records(enriched)
    hs_contacts  = create_hubspot_contact_records(validated_cts, enriched)
    show_hubspot(hs_companies, hs_contacts)
    save_stage(hs_companies, "hubspot_companies")
    save_stage(hs_contacts,  "hubspot_contacts")
    if not confirm(
        f"HubSpot complete — {len(hs_companies)} company records, {len(hs_contacts)} contact records",
        "Outreach Sequence Export"
    ):
        return

    # ── OUTREACH: Sequence export ────────────────────────────────────────
    email_export    = create_email_sequence_export(approved_cts)
    linkedin_export = create_linkedin_sequence_export(approved_cts)
    show_outreach(email_export, linkedin_export)
    save_stage(email_export,    "email_sequences")
    save_stage(linkedin_export, "linkedin_sequences")
    if not confirm(
        f"Outreach complete — {len(email_export)} email, {len(linkedin_export)} LinkedIn sequences",
        "Campaign Health Monitoring"
    ):
        return

    # ── CAMPAIGN HEALTH: Monitoring ──────────────────────────────────────
    raw_metrics   = load_campaign_metrics(os.path.join(DATA_DIR, "fake_campaign_metrics.json"))
    health_report = evaluate_all_campaigns(raw_metrics)
    show_campaign_health(raw_metrics, health_report)
    save_stage(raw_metrics,   "campaign_metrics")
    save_stage(health_report, "campaign_health")
    critical = sum(1 for h in health_report if h.get("health_status") == "critical")
    stop(f"Campaign Monitoring complete — {len(health_report)} campaigns, {critical} critical")

    show_final_summary(enriched, validated_cts, email_export, linkedin_export)


if __name__ == "__main__":
    run_demo()
