"""
HubSpot sync mock module — builds CRM-ready company and contact records.
# Future: Replace this CSV-ready transformation with HubSpot Private App API upsert logic.
"""

from __future__ import annotations
import json
import os

_LIFECYCLE_MAP: dict = None
_LIFECYCLE_CONFIG_PATH: str = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "config", "lifecycle_mapping.json",
)


def _load_lifecycle_map(file_path: str = None) -> dict:
    global _LIFECYCLE_MAP
    if _LIFECYCLE_MAP is None:
        path = file_path or _LIFECYCLE_CONFIG_PATH
        with open(path, "r", encoding="utf-8") as f:
            _LIFECYCLE_MAP = json.load(f)
    return _LIFECYCLE_MAP


def _company_lifecycle(company: dict) -> str:
    cfg = _load_lifecycle_map()
    rules = cfg.get("company_lifecycle_rules", {})

    tier = company.get("icp_tier", "Disqualified")
    approved = company.get("contact_discovery_approved", False)

    if tier == "Tier 1" and approved:
        return rules.get("tier_1_enriched", "Contact Discovery Approved")
    if tier == "Tier 2" and approved:
        return rules.get("tier_2_enriched", "Contact Discovery Approved")
    if tier == "Tier 3":
        return rules.get("tier_3_enriched", "Enriched Account")
    return rules.get("disqualified", "Suppressed")


def _contact_lifecycle(contact: dict) -> str:
    cfg = _load_lifecycle_map()
    rules = cfg.get("contact_lifecycle_rules", {})

    status = contact.get("final_validation_status", "suppressed")
    return rules.get(status, "Suppressed")


def create_hubspot_company_records(companies: list) -> list:
    records = []
    for c in companies:
        records.append({
            "company_id": c.get("company_id"),
            "company_name": c.get("company_name"),
            "domain": c.get("domain"),
            "website": c.get("website"),
            "industry": c.get("industry"),
            "employee_count": c.get("employee_count"),
            "state": c.get("state"),
            "icp_score": c.get("icp_score"),
            "icp_tier": c.get("icp_tier"),
            "recommended_personas": c.get("recommended_personas"),
            "contact_discovery_approved": c.get("contact_discovery_approved"),
            "lifecycle_stage": _company_lifecycle(c),
            "hubspot_sync_status": "ready_for_sync",
        })
    return records


def create_hubspot_contact_records(contacts: list, companies: list) -> list:
    company_tier = {c["company_id"]: c.get("icp_tier", "") for c in companies}
    company_name_map = {c["company_id"]: c.get("company_name", "") for c in companies}

    records = []
    for ct in contacts:
        cid = ct.get("company_id")
        records.append({
            "contact_id": ct.get("contact_id"),
            "company_id": cid,
            "company_name": company_name_map.get(cid, ct.get("company_name", "")),
            "first_name": ct.get("first_name"),
            "last_name": ct.get("last_name"),
            "email": ct.get("email"),
            "title": ct.get("title"),
            "linkedin_url": ct.get("linkedin_url"),
            "persona_type": ct.get("persona_type"),
            "icp_tier": company_tier.get(cid, ""),
            "final_validation_status": ct.get("final_validation_status"),
            "lifecycle_stage": _contact_lifecycle(ct),
            "hubspot_sync_status": "ready_for_sync",
        })
    return records
