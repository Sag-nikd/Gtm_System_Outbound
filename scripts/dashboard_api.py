#!/usr/bin/env python3
"""
GTM Dashboard API — lightweight Flask server that reads pipeline output files
and serves them as JSON for the dashboard.

Usage:
  python scripts/dashboard_api.py
  python scripts/dashboard_api.py --port 5050 --outputs outputs/
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

try:
    from flask import Flask, jsonify, send_from_directory
    from flask_cors import CORS
except ImportError:
    sys.exit(
        "Flask not installed. Run:  pip install flask flask-cors\n"
        "Or add to requirements.txt and re-install."
    )

_DEFAULT_OUTPUTS = os.path.join(_ROOT, "outputs")
_DEFAULT_PORT = 5050

app = Flask(__name__, static_folder=None)
CORS(app)

_OUTPUTS_DIR = _DEFAULT_OUTPUTS


# ── Helpers ───────────────────────────────────────────────────────────────────

def _read_csv(filename: str) -> list[dict]:
    path = os.path.join(_OUTPUTS_DIR, filename)
    if not os.path.exists(path):
        return []
    try:
        with open(path, newline="", encoding="utf-8") as f:
            return list(csv.DictReader(f))
    except (OSError, csv.Error):
        return []


def _read_json(filename: str) -> object:
    path = os.path.join(_OUTPUTS_DIR, filename)
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def _latest_manifest() -> dict:
    manifest_path = os.path.join(_OUTPUTS_DIR, "run_manifest.json")
    data = _read_json("run_manifest.json")
    if isinstance(data, dict):
        return data
    # run_manifest.json may be a list of runs — take the last one
    if isinstance(data, list) and data:
        return data[-1]
    return {}


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/api/summary")
def summary():
    icp_scored = _read_csv("03_icp_scored_accounts.csv")
    contacts = _read_csv("05_discovered_contacts.csv")
    validated = _read_csv("06_email_validation_results.csv")
    campaigns = _read_csv("11_campaign_health_report.csv")
    manifest = _latest_manifest()

    # Tier distribution
    tiers: dict[str, int] = {}
    for row in icp_scored:
        t = row.get("icp_tier", "Unknown")
        tiers[t] = tiers.get(t, 0) + 1

    # Funnel
    approved_contacts = _read_csv("08_hubspot_contact_export.csv")
    email_seq = _read_csv("09_email_sequence_export.csv")
    funnel = [
        {"stage": "Scored", "count": len(icp_scored)},
        {"stage": "Approved", "count": sum(1 for r in icp_scored if r.get("icp_tier") in ("Tier 1", "Tier 2"))},
        {"stage": "Contacts", "count": len(contacts)},
        {"stage": "Validated", "count": sum(1 for r in validated if r.get("final_validation_status") == "approved")},
        {"stage": "In CRM", "count": len(approved_contacts)},
        {"stage": "Sequences", "count": len(email_seq)},
    ]

    campaigns_critical = sum(1 for c in campaigns if c.get("health_status") == "critical")

    return jsonify({
        "summary": {
            "companies_scored": len(icp_scored),
            "contacts_discovered": len(contacts),
            "emails_approved": sum(1 for r in validated if r.get("final_validation_status") == "approved"),
            "campaigns_monitored": len(campaigns),
            "campaigns_critical": campaigns_critical,
        },
        "tiers": tiers,
        "funnel": funnel,
        "stages": manifest.get("stages", []),
        "campaigns": campaigns[:20],  # cap for dashboard display
    })


@app.route("/api/icp-scored")
def icp_scored():
    return jsonify(_read_csv("03_icp_scored_accounts.csv"))


@app.route("/api/contacts")
def contacts():
    return jsonify(_read_csv("06_email_validation_results.csv"))


@app.route("/api/campaigns")
def campaigns():
    return jsonify(_read_csv("11_campaign_health_report.csv"))


@app.route("/api/manifest")
def manifest():
    return jsonify(_latest_manifest())


@app.route("/api/status")
def stage_status():
    data = _read_json("stage_status.json")
    return jsonify(data or {})


@app.route("/")
def index():
    dashboard_dir = os.path.join(_ROOT, "dashboard")
    return send_from_directory(dashboard_dir, "index.html")


@app.route("/<path:path>")
def static_files(path):
    dashboard_dir = os.path.join(_ROOT, "dashboard")
    return send_from_directory(dashboard_dir, path)


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    global _OUTPUTS_DIR
    parser = argparse.ArgumentParser(description="GTM Dashboard API server")
    parser.add_argument("--port", type=int, default=_DEFAULT_PORT)
    parser.add_argument("--outputs", default=_DEFAULT_OUTPUTS)
    parser.add_argument("--host", default="127.0.0.1")
    args = parser.parse_args()

    _OUTPUTS_DIR = args.outputs
    print(f"GTM Dashboard API starting on http://{args.host}:{args.port}")
    print(f"Serving outputs from: {_OUTPUTS_DIR}")
    print(f"Dashboard UI: http://{args.host}:{args.port}/")
    app.run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()
