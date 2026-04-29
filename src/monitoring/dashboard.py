"""
Pipeline health dashboard — terminal summary of the most recent pipeline run.
Story 4.2: Provides a human-readable status report from run_manifest.json and
           the campaign health report CSV.
"""
from __future__ import annotations

import json
import os
from typing import List, Optional


def _load_manifest(output_dir: str) -> Optional[dict]:
    path = os.path.join(output_dir, "run_manifest.json")
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _load_campaign_report(output_dir: str) -> List[dict]:
    import csv
    path = os.path.join(output_dir, "11_campaign_health_report.csv")
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _bar(value: float, width: int = 20) -> str:
    filled = int(value * width)
    return "[" + "█" * filled + "░" * (width - filled) + "]"


def print_dashboard(output_dir: str) -> None:
    """Print a formatted pipeline health dashboard to stdout."""
    sep = "=" * 70
    print(f"\n{sep}")
    print("  GTM PIPELINE HEALTH DASHBOARD")
    print(sep)

    manifest = _load_manifest(output_dir)
    if manifest:
        print(f"\n  Run ID:       {manifest.get('run_id', '—')[:8]}...")
        print(f"  Started:      {manifest.get('started_at', '—')}")
        print(f"  Completed:    {manifest.get('completed_at', '—')}")
        print(f"  Mock mode:    {manifest.get('mock_mode', '—')}")
        print(f"  Config hash:  {manifest.get('config_hash', '—')[:8]}...")

        stages = manifest.get("stages", [])
        if stages:
            print(f"\n  Pipeline Stages:")
            for s in stages:
                status_icon = "✓" if s.get("status") == "completed" else "⏭" if s.get("status") == "skipped" else "✗"
                print(f"    {status_icon}  {s['name']:<30} {s.get('record_count', 0):>5} records  [{s.get('status', '?')}]")
    else:
        print("\n  No run manifest found. Run src/main.py first.")

    campaigns = _load_campaign_report(output_dir)
    if campaigns:
        print(f"\n  Campaign Health ({len(campaigns)} campaigns):")
        status_icons = {"healthy": "●", "needs_attention": "◐", "warning": "!", "critical": "✗"}
        for c in campaigns:
            icon = status_icons.get(c.get("health_status", ""), "?")
            print(f"    {icon}  {c.get('campaign_name', '?')[:40]:<40}  [{c.get('health_status', '?')}]")
            if c.get("primary_issue") and c["primary_issue"] != "none":
                print(f"       Issue: {c['primary_issue']}")
    else:
        print("\n  No campaign health report found.")

    print(f"\n{sep}\n")


def get_pipeline_summary(output_dir: str) -> dict:
    """Return a structured summary dict (for programmatic use)."""
    manifest = _load_manifest(output_dir)
    campaigns = _load_campaign_report(output_dir)

    critical_campaigns = [c for c in campaigns if c.get("health_status") == "critical"]
    warning_campaigns = [c for c in campaigns if c.get("health_status") == "warning"]

    stages = manifest.get("stages", []) if manifest else []
    total_companies = next(
        (s.get("record_count", 0) for s in stages if s.get("name") == "company_pipeline"), 0
    )
    total_contacts = next(
        (s.get("record_count", 0) for s in stages if s.get("name") == "contact_pipeline"), 0
    )

    return {
        "run_id": manifest.get("run_id", "") if manifest else "",
        "started_at": manifest.get("started_at", "") if manifest else "",
        "completed_at": manifest.get("completed_at", "") if manifest else "",
        "total_companies": total_companies,
        "total_contacts": total_contacts,
        "campaign_count": len(campaigns),
        "critical_campaign_count": len(critical_campaigns),
        "warning_campaign_count": len(warning_campaigns),
        "overall_health": (
            "critical" if critical_campaigns
            else "warning" if warning_campaigns
            else "healthy" if campaigns
            else "unknown"
        ),
    }
