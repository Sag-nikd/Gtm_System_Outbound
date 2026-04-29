#!/usr/bin/env python3
"""
Weekly GTM pipeline summary — generates an HTML email report and optionally
sends it via SMTP.

Usage:
  python scripts/weekly_report.py                    # print HTML to stdout
  python scripts/weekly_report.py --send             # send via SMTP
  python scripts/weekly_report.py --output report.html  # write to file
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import smtplib
import sys
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_OUTPUTS_DIR = os.path.join(_ROOT, "outputs")


# ── Data loading ──────────────────────────────────────────────────────────────

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


def _collect_stats() -> dict:
    icp = _read_csv("03_icp_scored_accounts.csv")
    contacts = _read_csv("05_discovered_contacts.csv")
    validated = _read_csv("06_email_validation_results.csv")
    campaigns = _read_csv("11_campaign_health_report.csv")
    manifest = _read_json("run_manifest.json") or {}
    if isinstance(manifest, list):
        manifest = manifest[-1] if manifest else {}

    tier1 = sum(1 for r in icp if r.get("icp_tier") == "Tier 1")
    tier2 = sum(1 for r in icp if r.get("icp_tier") == "Tier 2")
    approved = sum(1 for r in validated if r.get("final_validation_status") == "approved")
    suppressed = sum(1 for r in validated if r.get("final_validation_status") == "suppressed")
    critical = sum(1 for c in campaigns if c.get("health_status") == "critical")

    return {
        "run_id": manifest.get("run_id", "—"),
        "run_date": manifest.get("completed_at", datetime.now(timezone.utc).isoformat()),
        "companies_scored": len(icp),
        "tier1": tier1,
        "tier2": tier2,
        "contacts_discovered": len(contacts),
        "emails_approved": approved,
        "emails_suppressed": suppressed,
        "campaigns_total": len(campaigns),
        "campaigns_critical": critical,
        "stages": manifest.get("stages", []),
        "campaigns": campaigns[:10],
    }


# ── HTML generation ───────────────────────────────────────────────────────────

_STYLE = """
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f5f6fa; margin: 0; padding: 20px; color: #2d3748; }
.wrapper { max-width: 680px; margin: 0 auto; }
.header { background: #1a202c; color: white; padding: 24px; border-radius: 8px 8px 0 0; }
.header h1 { font-size: 1.25rem; margin: 0; }
.header p { font-size: 0.85rem; color: #a0aec0; margin: 4px 0 0; }
.body { background: white; padding: 24px; }
.footer { background: #f7fafc; padding: 16px 24px; border-radius: 0 0 8px 8px; font-size: 0.75rem; color: #718096; border-top: 1px solid #e2e8f0; }
.stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 24px; }
.stat-box { background: #f7fafc; border-radius: 6px; padding: 16px; text-align: center; }
.stat-num { font-size: 1.75rem; font-weight: 700; color: #2d3748; }
.stat-label { font-size: 0.75rem; color: #718096; margin-top: 4px; }
h2 { font-size: 1rem; font-weight: 600; margin: 24px 0 12px; color: #2d3748; border-bottom: 2px solid #e2e8f0; padding-bottom: 6px; }
table { width: 100%; border-collapse: collapse; font-size: 0.875rem; margin-bottom: 16px; }
th { text-align: left; padding: 8px 10px; background: #f7fafc; border-bottom: 2px solid #e2e8f0; font-weight: 600; color: #4a5568; }
td { padding: 8px 10px; border-bottom: 1px solid #e2e8f0; }
.badge-green { background: #c6f6d5; color: #22543d; border-radius: 4px; padding: 1px 6px; font-size: 0.75rem; }
.badge-yellow { background: #fefcbf; color: #744210; border-radius: 4px; padding: 1px 6px; font-size: 0.75rem; }
.badge-red { background: #fed7d7; color: #742a2a; border-radius: 4px; padding: 1px 6px; font-size: 0.75rem; }
.badge-gray { background: #e2e8f0; color: #4a5568; border-radius: 4px; padding: 1px 6px; font-size: 0.75rem; }
"""

def _badge(status: str) -> str:
    cls = {"completed": "badge-green", "failed": "badge-red", "running": "badge-yellow",
           "skipped": "badge-gray", "healthy": "badge-green", "warning": "badge-yellow",
           "critical": "badge-red"}.get(status, "badge-gray")
    return f'<span class="{cls}">{status}</span>'


def generate_html(stats: dict) -> str:
    run_date_raw = stats.get("run_date", "")
    try:
        run_dt = datetime.fromisoformat(run_date_raw.replace("Z", "+00:00"))
        run_date_str = run_dt.strftime("%B %d, %Y %H:%M UTC")
    except (ValueError, AttributeError):
        run_date_str = run_date_raw or "—"

    stage_rows = ""
    for s in stats.get("stages", []):
        stage_rows += f"""
        <tr>
          <td>{s.get('name', '—')}</td>
          <td>{s.get('record_count', '—'):,}</td>
          <td>{_badge(s.get('status', ''))}</td>
        </tr>"""

    campaign_rows = ""
    for c in stats.get("campaigns", []):
        open_pct = f"{float(c.get('open_rate', 0))*100:.1f}%" if c.get("open_rate") else "—"
        bounce_pct = f"{float(c.get('bounce_rate', 0))*100:.2f}%" if c.get("bounce_rate") else "—"
        campaign_rows += f"""
        <tr>
          <td>{c.get('campaign_name', '—')}</td>
          <td>{c.get('volume', '—')}</td>
          <td>{open_pct}</td>
          <td>{bounce_pct}</td>
          <td>{_badge(c.get('health_status', ''))}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><style>{_STYLE}</style></head>
<body>
<div class="wrapper">
  <div class="header">
    <h1>GTM Pipeline — Weekly Summary</h1>
    <p>Run ID: {stats.get('run_id', '—')} &nbsp;·&nbsp; {run_date_str}</p>
  </div>
  <div class="body">
    <div class="stats">
      <div class="stat-box"><div class="stat-num">{stats['companies_scored']}</div><div class="stat-label">Companies Scored</div></div>
      <div class="stat-box"><div class="stat-num">{stats['tier1'] + stats['tier2']}</div><div class="stat-label">Tier 1 + 2 Accounts</div></div>
      <div class="stat-box"><div class="stat-num">{stats['contacts_discovered']}</div><div class="stat-label">Contacts Discovered</div></div>
      <div class="stat-box"><div class="stat-num">{stats['emails_approved']}</div><div class="stat-label">Emails Approved</div></div>
      <div class="stat-box"><div class="stat-num">{stats['emails_suppressed']}</div><div class="stat-label">Emails Suppressed</div></div>
      <div class="stat-box"><div class="stat-num">{stats['campaigns_critical']}</div><div class="stat-label">Critical Campaigns</div></div>
    </div>

    <h2>Pipeline Stages</h2>
    <table>
      <thead><tr><th>Stage</th><th>Records</th><th>Status</th></tr></thead>
      <tbody>{stage_rows or '<tr><td colspan="3" style="color:#718096">No stage data</td></tr>'}</tbody>
    </table>

    <h2>Campaign Health</h2>
    <table>
      <thead><tr><th>Campaign</th><th>Sent</th><th>Open Rate</th><th>Bounce Rate</th><th>Health</th></tr></thead>
      <tbody>{campaign_rows or '<tr><td colspan="5" style="color:#718096">No campaign data</td></tr>'}</tbody>
    </table>
  </div>
  <div class="footer">
    Generated by GTM System &nbsp;·&nbsp; {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}
  </div>
</div>
</body>
</html>"""


# ── Email sending ─────────────────────────────────────────────────────────────

def send_report(html: str, subject: str) -> None:
    smtp_host = os.getenv("SMTP_HOST", "")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER", "")
    smtp_pass = os.getenv("SMTP_PASS", "")
    from_email = os.getenv("FROM_EMAIL", smtp_user)
    to_email = os.getenv("REPORT_TO_EMAIL", "")

    if not smtp_host:
        sys.exit("SMTP_HOST env var is not set. Cannot send email.")
    if not to_email:
        sys.exit("REPORT_TO_EMAIL env var is not set. Cannot send email.")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = to_email
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as s:
            s.starttls()
            if smtp_user:
                s.login(smtp_user, smtp_pass)
            s.sendmail(from_email, [to_email], msg.as_string())
        print(f"Report sent to {to_email}")
    except (OSError, smtplib.SMTPException) as exc:
        sys.exit(f"Failed to send email: {exc}")


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="GTM weekly summary report")
    parser.add_argument("--send", action="store_true", help="Send via SMTP")
    parser.add_argument("--output", help="Write HTML to this file instead of stdout")
    parser.add_argument("--outputs-dir", default=_OUTPUTS_DIR, help="Pipeline outputs directory")
    args = parser.parse_args()

    global _OUTPUTS_DIR
    _OUTPUTS_DIR = args.outputs_dir

    stats = _collect_stats()
    html = generate_html(stats)
    subject = f"GTM Pipeline Weekly Report — {datetime.now(timezone.utc).strftime('%Y-%m-%d')}"

    if args.send:
        send_report(html, subject)
    elif args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"Report written to {args.output}")
    else:
        print(html)


if __name__ == "__main__":
    main()
