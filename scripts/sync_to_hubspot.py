#!/usr/bin/env python
"""
Run the GTM simulation pipeline and push all records to HubSpot via batch API.

Usage:
    python scripts/sync_to_hubspot.py
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from src.main import run_company_pipeline, run_contact_pipeline
from src.integrations.apollo import ApolloMockClient
from src.integrations.clay import ClayMockClient
from src.integrations.zerobounce import ZeroBounceMockClient
from src.integrations.neverbounce import NeverBounceMockClient
from src.crm.hubspot.sync import HubSpotSyncClient
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

    # ── Step 3: Batch push companies ──────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  Pushing Companies to HubSpot (batch)")
    print("=" * 60)

    try:
        company_id_map = client.batch_upsert_companies(enriched)
        print(f"  Companies pushed: {len(company_id_map)} / {len(enriched)}")
    except Exception as exc:
        log.error("Batch company push failed: %s", exc)
        company_id_map = {}

    # ── Step 4: Batch push contacts ───────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  Pushing Contacts to HubSpot (batch)")
    print("=" * 60)

    try:
        created_cts, updated_cts, associated = client.batch_upsert_contacts(
            validated, company_id_map
        )
        print(f"  Contacts: {created_cts} created, {updated_cts} updated")
        print(f"  Associations: {associated} contact-company links created")
    except Exception as exc:
        log.error("Batch contact push failed: %s", exc)
        created_cts = updated_cts = associated = 0

    # ── Summary ───────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  Sync Complete")
    print("=" * 60)
    print(f"  Companies pushed: {len(company_id_map)} / {len(enriched)}")
    print(f"  Contacts pushed:  {created_cts + updated_cts} / {len(validated)}")
    print(f"  Associations:     {associated}")
    if _PORTAL_ID:
        print(f"\n  View in HubSpot:")
        print(f"    Companies: https://app.hubspot.com/contacts/{_PORTAL_ID}/companies")
        print(f"    Contacts:  https://app.hubspot.com/contacts/{_PORTAL_ID}/contacts")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    main()
