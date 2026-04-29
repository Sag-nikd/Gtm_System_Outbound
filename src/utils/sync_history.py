"""
Cross-run deduplication via outputs/sync_history.json.

Records which company domains and contact emails were successfully synced to
HubSpot, along with their ICP score at sync time. On subsequent runs, records
whose domain/email + icp_score are unchanged are skipped.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Dict, List, Tuple

from src.utils.logger import get_logger

log = get_logger(__name__)

_HISTORY_FILE = "sync_history.json"


def _history_path(output_dir: str) -> str:
    return os.path.join(output_dir, _HISTORY_FILE)


def load_sync_history(output_dir: str) -> dict:
    """Load sync history from disk. Returns empty history structure if absent."""
    path = _history_path(output_dir)
    if not os.path.exists(path):
        return {"synced_domains": {}, "synced_emails": {}}
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        log.warning("Could not load sync history: %s — starting fresh", exc)
        return {"synced_domains": {}, "synced_emails": {}}


def save_sync_history(history: dict, output_dir: str) -> None:
    """Persist sync history to disk."""
    os.makedirs(output_dir, exist_ok=True)
    history["last_updated"] = datetime.now(timezone.utc).isoformat()
    path = _history_path(output_dir)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2)
    except OSError as exc:
        log.warning("Could not save sync history: %s", exc)


def filter_new_companies(companies: List[dict], history: dict) -> Tuple[List[dict], int]:
    """
    Return companies not yet synced, or whose icp_score changed since last sync.
    Also returns the count of skipped (already-synced) companies.
    """
    synced = history.get("synced_domains", {})
    new, skipped = [], 0
    for co in companies:
        domain = co.get("domain", "")
        score = float(co.get("icp_score", 0) or 0)
        if domain and domain in synced:
            prev_score = float(synced[domain].get("icp_score", -1))
            if prev_score == score:
                skipped += 1
                continue
        new.append(co)
    if skipped:
        log.info("Dedup: skipping %d already-synced companies (score unchanged)", skipped)
    return new, skipped


def filter_new_contacts(contacts: List[dict], history: dict) -> Tuple[List[dict], int]:
    """
    Return contacts not yet synced to HubSpot.
    """
    synced = history.get("synced_emails", {})
    new, skipped = [], 0
    for ct in contacts:
        email = ct.get("email", "")
        if email and email in synced:
            skipped += 1
            continue
        new.append(ct)
    if skipped:
        log.info("Dedup: skipping %d already-synced contacts", skipped)
    return new, skipped


def record_synced_companies(
    companies: List[dict], hubspot_id_map: Dict[str, str], history: dict
) -> dict:
    """Update history with newly-synced companies."""
    synced = history.setdefault("synced_domains", {})
    now = datetime.now(timezone.utc).isoformat()
    for co in companies:
        domain = co.get("domain", "")
        if not domain:
            continue
        synced[domain] = {
            "hubspot_id": hubspot_id_map.get(co.get("company_id", ""), ""),
            "icp_score": float(co.get("icp_score", 0) or 0),
            "icp_tier": co.get("icp_tier", ""),
            "synced_at": now,
        }
    return history


def record_synced_contacts(
    contacts: List[dict], history: dict
) -> dict:
    """Update history with newly-synced contacts."""
    synced = history.setdefault("synced_emails", {})
    now = datetime.now(timezone.utc).isoformat()
    for ct in contacts:
        email = ct.get("email", "")
        if not email:
            continue
        synced[email] = {
            "hubspot_id": ct.get("hubspot_id", ""),
            "synced_at": now,
        }
    return history
