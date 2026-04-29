from __future__ import annotations

from typing import Any, Dict, List, Optional

import requests

from src.integrations.hubspot.base import HubSpotBase
from src.utils.retry import api_retry
from src.utils.logger import get_logger

log = get_logger(__name__)

_BASE_URL = "https://api.hubapi.com"
_BATCH_SIZE = 100


class HubSpotAPIClient(HubSpotBase):
    """
    HubSpot API client — real CRM sync via batch create/update endpoints.
    Requires HUBSPOT_PRIVATE_APP_TOKEN. Set HUBSPOT_MODE=live to activate.
    """

    def __init__(self, token: str) -> None:
        self._headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    # ── Low-level HTTP helpers ────────────────────────────────────────────────

    def _post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        resp = requests.post(
            f"{_BASE_URL}{path}", headers=self._headers, json=payload, timeout=30
        )
        resp.raise_for_status()
        return resp.json()

    def _patch(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        resp = requests.patch(
            f"{_BASE_URL}{path}", headers=self._headers, json=payload, timeout=30
        )
        resp.raise_for_status()
        return resp.json()

    # ── Search helpers ────────────────────────────────────────────────────────

    def _find_by_property(
        self, object_type: str, prop_name: str, values: List[str]
    ) -> Dict[str, str]:
        """Return {value: hubspot_id} for any matching records found."""
        if not values:
            return {}
        payload = {
            "filterGroups": [
                {"filters": [{"propertyName": prop_name, "operator": "IN", "values": values}]}
            ],
            "properties": [prop_name],
            "limit": len(values),
        }
        try:
            resp = self._post(f"/crm/v3/objects/{object_type}/search", payload)
            return {
                r["properties"].get(prop_name, ""): r["id"]
                for r in resp.get("results", [])
                if r["properties"].get(prop_name)
            }
        except Exception as exc:
            log.warning("HubSpot search failed: %s", exc)
            return {}

    # ── Batch create / update ─────────────────────────────────────────────────

    def _batch_create(self, object_type: str, inputs: List[Dict]) -> List[Dict]:
        """POST /crm/v3/objects/{type}/batch/create → list of created records."""
        results = []
        for i in range(0, len(inputs), _BATCH_SIZE):
            chunk = inputs[i: i + _BATCH_SIZE]
            resp = self._post(
                f"/crm/v3/objects/{object_type}/batch/create",
                {"inputs": chunk},
            )
            results.extend(resp.get("results", []))
        return results

    def _batch_update(self, object_type: str, inputs: List[Dict]) -> List[Dict]:
        """POST /crm/v3/objects/{type}/batch/update → list of updated records."""
        results = []
        for i in range(0, len(inputs), _BATCH_SIZE):
            chunk = inputs[i: i + _BATCH_SIZE]
            resp = self._post(
                f"/crm/v3/objects/{object_type}/batch/update",
                {"inputs": chunk},
            )
            results.extend(resp.get("results", []))
        return results

    # ── Public interface ──────────────────────────────────────────────────────

    @api_retry
    def upsert_companies(self, companies: List[dict]) -> List[dict]:
        """Batch-upsert companies by domain. Returns companies with hubspot_id populated."""
        from src.crm.hubspot.sync import build_company_properties

        domains = [c.get("domain", c.get("website", "")) for c in companies]
        existing = self._find_by_property("companies", "domain", [d for d in domains if d])

        to_create, to_update = [], []
        for co in companies:
            domain = co.get("domain", co.get("website", ""))
            props = build_company_properties(co)
            hs_id = existing.get(domain)
            if hs_id:
                to_update.append({"id": hs_id, "properties": props})
                co["hubspot_id"] = hs_id
                co["hubspot_action"] = "updated"
            else:
                to_create.append({"properties": props})
                co["hubspot_action"] = "pending_create"

        if to_create:
            created = self._batch_create("companies", to_create)
            create_idx = 0
            for co in companies:
                if co.get("hubspot_action") == "pending_create":
                    if create_idx < len(created):
                        co["hubspot_id"] = created[create_idx]["id"]
                    co["hubspot_action"] = "created"
                    create_idx += 1

        if to_update:
            self._batch_update("companies", to_update)

        log.info(
            "HubSpot: %d companies created, %d updated",
            len(to_create), len(to_update),
        )
        return companies

    @api_retry
    def upsert_contacts(self, contacts: List[dict], companies: List[dict]) -> List[dict]:
        """Batch-upsert contacts by email. Returns contacts with hubspot_id populated."""
        from src.crm.hubspot.sync import build_contact_properties

        emails = [c.get("email", "") for c in contacts]
        existing = self._find_by_property("contacts", "email", [e for e in emails if e])

        company_id_map = {co.get("company_id", ""): co.get("hubspot_id", "") for co in companies}

        to_create, to_update = [], []
        for ct in contacts:
            email = ct.get("email", "")
            props = build_contact_properties(ct)
            hs_id = existing.get(email)
            if hs_id:
                to_update.append({"id": hs_id, "properties": props})
                ct["hubspot_id"] = hs_id
                ct["hubspot_action"] = "updated"
            else:
                to_create.append({"properties": props})
                ct["hubspot_action"] = "pending_create"

        if to_create:
            created = self._batch_create("contacts", to_create)
            create_idx = 0
            for ct in contacts:
                if ct.get("hubspot_action") == "pending_create":
                    if create_idx < len(created):
                        ct["hubspot_id"] = created[create_idx]["id"]
                    ct["hubspot_action"] = "created"
                    create_idx += 1

        if to_update:
            self._batch_update("contacts", to_update)

        # Associate contacts to companies (best-effort, one at a time)
        associations_created = 0
        for ct in contacts:
            hs_contact_id = ct.get("hubspot_id", "")
            hs_co_id = company_id_map.get(ct.get("company_id", ""), "")
            if hs_contact_id and hs_co_id:
                try:
                    requests.put(
                        f"{_BASE_URL}/crm/v3/objects/contacts/{hs_contact_id}"
                        f"/associations/companies/{hs_co_id}/contact_to_company",
                        headers=self._headers,
                        timeout=20,
                    ).raise_for_status()
                    associations_created += 1
                except Exception as exc:
                    log.warning("Association failed for contact %s: %s", hs_contact_id, exc)

        log.info(
            "HubSpot: %d contacts created, %d updated, %d associations",
            len(to_create), len(to_update), associations_created,
        )
        return contacts
