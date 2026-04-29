#!/usr/bin/env python
"""
Run the GTM simulation pipeline and push all records to HubSpot.

Usage:
    python scripts/sync_to_hubspot.py
"""
from __future__ import annotations

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from src.main import run_company_pipeline, run_contact_pipeline
from src.integrations.apollo import ApolloMockClient
from src.integrations.clay import ClayMockClient
from src.integrations.zerobounce import ZeroBounceMockClient
from src.integrations.neverbounce import NeverBounceMockClient
from src.crm.hubspot.sync import (
    HubSpotSyncClient,
    build_company_properties,
    build_contact_properties,
)
from src.utils.logger import get_logger

log = get_logger("sync_to_hubspot")

_TOKEN = os.getenv("HUBSPOT_PRIVATE_APP_TOKEN", "")
_PORTAL_ID = os.getenv("HUBSPOT_PORTAL_ID", "")


def main() -> None:
    if not _TOKEN:
        log.error("HUBSPOT_PRIVATE_APP_TOKEN not set in .env")
        sys.exit(1)

    # ── Step 1: Run GTM simulation ────────────────────────────────────────────
    log.info("Running GTM simulation pipeline...")
    apollo = ApolloMockClient()
    clay = ClayMockClient()
    zerobounce = ZeroBounceMockClient()
    neverbounce = NeverBounceMockClient()

    enriched = run_company_pipeline(apollo, clay)
    validated = run_contact_pipeline(enriched, apollo, zerobounce, neverbounce)

    log.info("Simulation complete: %d companies, %d contacts", len(enriched), len(validated))

    # ── Step 2: Connect to HubSpot ────────────────────────────────────────────
    client = HubSpotSyncClient(_TOKEN)
    log.info("Connected to HubSpot")

    # ── Step 3: Push companies ────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  Pushing Companies to HubSpot")
    print("=" * 60)

    company_id_map: dict = {}  # gtm company_id -> hubspot_id
    created_cos = updated_cos = failed_cos = 0

    for co in enriched:
        name = co.get("company_name", "")
        props = build_company_properties(co)
        try:
            hs_id, action = client.upsert_company(props)
            company_id_map[co["company_id"]] = hs_id
            if action == "created":
                created_cos += 1
                print(f"  [CREATED] {name} (tier={co.get('icp_tier')} score={co.get('icp_score')}) -> id={hs_id}")
            else:
                updated_cos += 1
                print(f"  [UPDATED] {name} -> id={hs_id}")
            time.sleep(0.15)  # stay within HubSpot rate limits
        except Exception as exc:
            failed_cos += 1
            log.error("Failed to push company '%s': %s", name, exc)

    print(f"\n  Companies: {created_cos} created, {updated_cos} updated, {failed_cos} failed")

    # ── Step 4: Push contacts ─────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  Pushing Contacts to HubSpot")
    print("=" * 60)

    created_cts = updated_cts = failed_cts = associated = 0

    for ct in validated:
        email = ct.get("email", "")
        name = f"{ct.get('first_name','')} {ct.get('last_name','')}".strip()
        props = build_contact_properties(ct)
        try:
            hs_contact_id, action = client.upsert_contact(props)
            if action == "created":
                created_cts += 1
                print(f"  [CREATED] {name} <{email}> ({ct.get('final_validation_status')}) -> id={hs_contact_id}")
            else:
                updated_cts += 1
                print(f"  [UPDATED] {name} <{email}> -> id={hs_contact_id}")

            # Associate contact to its company
            co_id = ct.get("company_id", "")
            hs_co_id = company_id_map.get(co_id)
            if hs_co_id:
                try:
                    client.associate_contact_to_company(hs_contact_id, hs_co_id)
                    associated += 1
                except Exception as assoc_exc:
                    log.warning("Could not associate %s to company: %s", name, assoc_exc)

            time.sleep(0.15)
        except Exception as exc:
            failed_cts += 1
            log.error("Failed to push contact '%s': %s", name, exc)

    print(f"\n  Contacts: {created_cts} created, {updated_cts} updated, {failed_cts} failed")
    print(f"  Associations: {associated} contact-company links created")

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  Sync Complete")
    print("=" * 60)
    print(f"  Companies pushed: {created_cos + updated_cos} / {len(enriched)}")
    print(f"  Contacts pushed:  {created_cts + updated_cts} / {len(validated)}")
    print(f"  Associations:     {associated}")
    if _PORTAL_ID:
        print(f"\n  View in HubSpot:")
        print(f"    Companies: https://app.hubspot.com/contacts/{_PORTAL_ID}/companies")
        print(f"    Contacts:  https://app.hubspot.com/contacts/{_PORTAL_ID}/contacts")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
