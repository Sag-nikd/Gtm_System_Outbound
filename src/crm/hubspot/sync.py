from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

import requests

from src.utils.logger import get_logger

log = get_logger(__name__)

_BASE_URL = "https://api.hubapi.com"

# HubSpot native `industry` property requires exact enum values
# Map GTM industry names to the closest valid HubSpot option
_INDUSTRY_MAP: Dict[str, str] = {
    "Managed Care": "HOSPITAL_HEALTH_CARE",
    "Health Plan": "INSURANCE",
    "Healthcare Tech": "HOSPITAL_HEALTH_CARE",
    "Healthcare SaaS": "HOSPITAL_HEALTH_CARE",
    "Hospital": "HOSPITAL_HEALTH_CARE",
    "Medical": "MEDICAL_PRACTICE",
    "Financial Services": "FINANCIAL_SERVICES",
    "Banking": "BANKING",
    "Insurance": "INSURANCE",
    "Retail": "RETAIL",
    "Technology": "INFORMATION_TECHNOLOGY_AND_SERVICES",
    "SaaS": "COMPUTER_SOFTWARE",
    "B2B SaaS": "COMPUTER_SOFTWARE",
    "Software": "COMPUTER_SOFTWARE",
    "Consulting": "MANAGEMENT_CONSULTING",
    "Education": "EDUCATION_MANAGEMENT",
    "Government": "GOVERNMENT_ADMINISTRATION",
}

# Map GTM icp_tier values to HubSpot enumeration option values
_TIER_VALUE_MAP = {
    "Tier 1": "tier_1",
    "Tier 2": "tier_2",
    "Tier 3": "tier_3",
    "Disqualified": "rejected",
}

# Map GTM enrichment_status to HubSpot option values
_ENRICHMENT_STATUS_MAP = {
    "enriched": "enriched",
    "Enriched": "enriched",
    "failed": "failed",
    "needs_review": "needs_review",
    "not_started": "not_started",
}

# Map GTM lifecycle_stage to HubSpot native lifecyclestage property
_LIFECYCLE_MAP = {
    "Contact Discovery Approved": "lead",
    "Enriched Account": "lead",
    "Suppressed": "other",
    "Contact Validated": "salesqualifiedlead",
    "Nurture": "lead",
}

# Map validation status to email_validation_status enum value
_VALIDATION_STATUS_MAP = {
    "approved": "valid",
    "review": "risky",
    "suppressed": "invalid",
}

# Map persona_type to buyer_persona enum value
_PERSONA_MAP = {
    "VP Member Engagement": "other",
    "CTO": "other",
    "CFO": "other",
    "CEO": "ceo",
    "Founder": "founder",
    "CRO": "cro",
    "VP Sales": "vp_sales",
    "RevOps": "revops",
    "Marketing": "marketing",
    "Operations": "operations",
    "IT": "it",
}


class HubSpotSyncClient:
    """Pushes GTM simulation records into HubSpot via CRM API."""

    def __init__(self, token: str) -> None:
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    def _post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{_BASE_URL}{path}"
        resp = requests.post(url, headers=self._headers, json=payload, timeout=20)
        if not resp.ok:
            try:
                log.debug("HubSpot error: %s", resp.json())
            except Exception:
                pass
        resp.raise_for_status()
        return resp.json()

    def _put(self, path: str) -> None:
        url = f"{_BASE_URL}{path}"
        resp = requests.put(url, headers=self._headers, timeout=20)
        resp.raise_for_status()

    def _get(self, path: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        url = f"{_BASE_URL}{path}"
        resp = requests.get(url, headers=self._headers, params=params, timeout=20)
        resp.raise_for_status()
        return resp.json()

    # ── Search for existing records ───────────────────────────────────────────

    def find_company_by_domain(self, domain: str) -> Optional[str]:
        """Return HubSpot company ID if a company with this domain already exists."""
        payload = {
            "filterGroups": [{"filters": [{"propertyName": "domain", "operator": "EQ", "value": domain}]}],
            "properties": ["domain", "name"],
            "limit": 1,
        }
        try:
            resp = self._post("/crm/v3/objects/companies/search", payload)
            results = resp.get("results", [])
            return results[0]["id"] if results else None
        except Exception:
            return None

    def find_contact_by_email(self, email: str) -> Optional[str]:
        """Return HubSpot contact ID if a contact with this email already exists."""
        payload = {
            "filterGroups": [{"filters": [{"propertyName": "email", "operator": "EQ", "value": email}]}],
            "properties": ["email"],
            "limit": 1,
        }
        try:
            resp = self._post("/crm/v3/objects/contacts/search", payload)
            results = resp.get("results", [])
            return results[0]["id"] if results else None
        except Exception:
            return None

    # ── Create / update ───────────────────────────────────────────────────────

    def upsert_company(self, props: Dict[str, Any]) -> Tuple[str, str]:
        """Create or update a company. Returns (hubspot_id, action)."""
        domain = props.get("domain", "")
        existing_id = self.find_company_by_domain(domain) if domain else None

        if existing_id:
            url = f"{_BASE_URL}/crm/v3/objects/companies/{existing_id}"
            resp = requests.patch(url, headers=self._headers, json={"properties": props}, timeout=20)
            resp.raise_for_status()
            return existing_id, "updated"

        result = self._post("/crm/v3/objects/companies", {"properties": props})
        return result["id"], "created"

    def upsert_contact(self, props: Dict[str, Any]) -> Tuple[str, str]:
        """Create or update a contact. Returns (hubspot_id, action)."""
        email = props.get("email", "")
        existing_id = self.find_contact_by_email(email) if email else None

        if existing_id:
            url = f"{_BASE_URL}/crm/v3/objects/contacts/{existing_id}"
            resp = requests.patch(url, headers=self._headers, json={"properties": props}, timeout=20)
            resp.raise_for_status()
            return existing_id, "updated"

        result = self._post("/crm/v3/objects/contacts", {"properties": props})
        return result["id"], "created"

    def associate_contact_to_company(self, contact_id: str, company_id: str) -> None:
        """Associate a contact record with a company record."""
        self._put(
            f"/crm/v3/objects/contacts/{contact_id}/associations/companies/{company_id}/contact_to_company"
        )

    # ── Batch operations (Story 2.4) ──────────────────────────────────────────

    _BATCH_SIZE = 100

    def _batch_post(self, object_type: str, action: str, inputs: list) -> list:
        """POST to batch create or update endpoint, returning all result records."""
        results = []
        for i in range(0, len(inputs), self._BATCH_SIZE):
            chunk = inputs[i: i + self._BATCH_SIZE]
            data = self._post(f"/crm/v3/objects/{object_type}/batch/{action}", {"inputs": chunk})
            results.extend(data.get("results", []))
        return results

    def _search_by_values(self, object_type: str, prop: str, values: list) -> dict:
        """Return {value: hubspot_id} for matching records."""
        if not values:
            return {}
        payload = {
            "filterGroups": [
                {"filters": [{"propertyName": prop, "operator": "IN", "values": values}]}
            ],
            "properties": [prop],
            "limit": len(values),
        }
        try:
            resp = self._post(f"/crm/v3/objects/{object_type}/search", payload)
            return {
                r["properties"].get(prop, ""): r["id"]
                for r in resp.get("results", [])
                if r["properties"].get(prop)
            }
        except Exception as exc:
            log.warning("HubSpot batch search failed: %s", exc)
            return {}

    def batch_upsert_companies(self, companies: list) -> dict:
        """
        Batch upsert companies (max 100 per API call).
        Returns {gtm_company_id: hubspot_id}.
        """
        domains = [build_company_properties(co).get("domain", "") for co in companies]
        existing = self._search_by_values("companies", "domain", [d for d in domains if d])

        to_create, to_update = [], []
        company_meta = []  # track which gtm company_id maps to which batch slot

        for co in companies:
            props = build_company_properties(co)
            domain = props.get("domain", "")
            hs_id = existing.get(domain)
            if hs_id:
                to_update.append({"id": hs_id, "properties": props})
                company_meta.append(("update", co["company_id"], hs_id))
            else:
                to_create.append({"properties": props})
                company_meta.append(("create", co["company_id"], None))

        if to_update:
            self._batch_post("companies", "update", to_update)

        created_ids: list = []
        if to_create:
            created = self._batch_post("companies", "create", to_create)
            created_ids = [r["id"] for r in created]

        id_map: dict = {}
        create_cursor = 0
        for action, cid, hs_id in company_meta:
            if action == "update":
                id_map[cid] = hs_id
            else:
                if create_cursor < len(created_ids):
                    id_map[cid] = created_ids[create_cursor]
                create_cursor += 1

        log.info(
            "HubSpot batch: %d companies created, %d updated",
            len(to_create), len(to_update),
        )
        return id_map

    def batch_upsert_contacts(
        self, contacts: list, company_id_map: dict
    ) -> tuple:
        """
        Batch upsert contacts (max 100 per API call).
        Returns (created_count, updated_count, associated_count).
        """
        emails = [build_contact_properties(ct).get("email", "") for ct in contacts]
        existing = self._search_by_values("contacts", "email", [e for e in emails if e])

        to_create, to_update = [], []
        contact_meta = []  # (action, contact, hs_id_or_None)

        for ct in contacts:
            props = build_contact_properties(ct)
            email = props.get("email", "")
            hs_id = existing.get(email)
            if hs_id:
                to_update.append({"id": hs_id, "properties": props})
                contact_meta.append(("update", ct, hs_id))
            else:
                to_create.append({"properties": props})
                contact_meta.append(("create", ct, None))

        if to_update:
            self._batch_post("contacts", "update", to_update)

        created_ids: list = []
        if to_create:
            created = self._batch_post("contacts", "create", to_create)
            created_ids = [r["id"] for r in created]

        # Build full contact→hubspot_id map and associate
        created_count = updated_count = associated = 0
        create_cursor = 0
        for action, ct, hs_id in contact_meta:
            if action == "update":
                hs_contact_id = hs_id
                updated_count += 1
            else:
                hs_contact_id = created_ids[create_cursor] if create_cursor < len(created_ids) else None
                create_cursor += 1
                created_count += 1

            if hs_contact_id:
                hs_co_id = company_id_map.get(ct.get("company_id", ""))
                if hs_co_id:
                    try:
                        self.associate_contact_to_company(hs_contact_id, hs_co_id)
                        associated += 1
                    except Exception as exc:
                        name = f"{ct.get('first_name', '')} {ct.get('last_name', '')}".strip()
                        log.warning("Association failed for %s: %s", name, exc)

        log.info(
            "HubSpot batch: %d contacts created, %d updated, %d associations",
            created_count, updated_count, associated,
        )
        return created_count, updated_count, associated


# ── Property builders ─────────────────────────────────────────────────────────

def build_company_properties(row: Dict[str, Any]) -> Dict[str, Any]:
    """Map a GTM company dict to HubSpot company property values."""
    tier_raw = row.get("icp_tier", "")
    props: Dict[str, Any] = {
        # Standard HubSpot company properties
        "name": row.get("company_name", ""),
        "domain": row.get("domain", ""),
        "website": row.get("website", row.get("domain", "")),
        "industry": _INDUSTRY_MAP.get(row.get("industry", ""), ""),
        "state": row.get("state", ""),
        # GTM custom properties — numbers must be numeric, not strings
        "icp_tier": _TIER_VALUE_MAP.get(tier_raw, ""),
        "account_source": "Apollo",
        "enrichment_status": _ENRICHMENT_STATUS_MAP.get(
            str(row.get("enrichment_status", "enriched")), "enriched"
        ),
        "fit_reason": _safe_str(row.get("score_reason", row.get("tier_reason", ""))),
        "gtm_segment": _gtm_segment(row.get("employee_count", 0)),
        "last_scored_date": _today_ms(),
    }
    # Number fields — only add if value is a valid number
    try:
        props["numberofemployees"] = int(row.get("employee_count", 0))
    except (TypeError, ValueError):
        pass
    try:
        props["icp_score"] = float(row.get("icp_score", 0))
    except (TypeError, ValueError):
        pass
    # Remove blank / None values
    return {k: v for k, v in props.items() if v not in ("", "None", None)}


def build_contact_properties(row: Dict[str, Any]) -> Dict[str, Any]:
    """Map a GTM contact dict to HubSpot contact property values."""
    validation = row.get("final_validation_status", "")
    persona_raw = row.get("persona_type", row.get("buyer_persona", ""))
    props: Dict[str, Any] = {
        # Standard HubSpot contact properties
        "firstname": row.get("first_name", ""),
        "lastname": row.get("last_name", ""),
        "email": row.get("email", ""),
        "jobtitle": row.get("title", ""),
        "company": row.get("company_name", ""),
        "lifecyclestage": _LIFECYCLE_MAP.get(
            row.get("lifecycle_stage", ""), "lead"
        ),
        # GTM custom properties
        "email_validation_status": _VALIDATION_STATUS_MAP.get(validation, "unknown"),
        "buyer_persona": _PERSONA_MAP.get(persona_raw, "other"),
        "sequence_status": "not_added",
        "outreach_channel": "email" if validation == "approved" else "none",
        "contact_source": "Apollo",
        "gtm_linkedin_url": row.get("linkedin_url", ""),
    }
    return {k: v for k, v in props.items() if v not in ("", "None", None)}


def _gtm_segment(employee_count: Any) -> str:
    try:
        n = int(employee_count)
    except (TypeError, ValueError):
        return "unknown"
    if n >= 1000:
        return "enterprise"
    if n >= 200:
        return "mid_market"
    if n >= 50:
        return "smb"
    return "startup"


def _today_ms() -> int:
    """HubSpot date properties require Unix timestamp in milliseconds (midnight UTC)."""
    from datetime import datetime, timezone
    dt = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    return int(dt.timestamp() * 1000)


def _safe_str(value: Any) -> str:
    """Convert value to ASCII-safe string, stripping non-encodable characters."""
    s = str(value) if value is not None else ""
    return s.encode("ascii", errors="ignore").decode("ascii")
