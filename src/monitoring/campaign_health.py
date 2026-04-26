"""
Campaign health monitoring module.
# Future: Replace fake campaign metrics with Validity and sequencing platform engagement data.
"""

from __future__ import annotations
import json


def load_campaign_metrics(file_path: str) -> list[dict]:
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def evaluate_campaign_health(campaign: dict) -> dict:
    name = campaign.get("campaign_name", "Unknown")
    bounce = campaign.get("bounce_rate", 0)
    open_r = campaign.get("open_rate", 0)
    reply_r = campaign.get("reply_rate", 0)
    spam = campaign.get("spam_rate", 0)
    domain_score = campaign.get("domain_health_score", 100)

    # Evaluate in priority order — most severe issue wins
    if spam > 0.003:
        status = "critical"
        issue = "spam_rate too high"
        action = "Pause campaign immediately and investigate sending domain"
    elif bounce > 0.04:
        status = "warning"
        issue = "bounce_rate too high"
        action = "Check list quality and deliverability settings"
    elif domain_score < 70:
        status = "warning"
        issue = "domain_health_score low"
        action = "Check domain health — review DMARC, SPF, and DKIM configuration"
    elif open_r < 0.30:
        status = "needs_attention"
        issue = "open_rate below threshold"
        action = "A/B test subject lines and review sending time/frequency"
    elif reply_r < 0.02:
        status = "needs_attention"
        issue = "reply_rate below threshold"
        action = "Optimize messaging and refine ICP targeting"
    else:
        status = "healthy"
        issue = "none"
        action = "Continue — no critical issues detected"

    return {
        "campaign_name": name,
        "health_status": status,
        "primary_issue": issue,
        "recommended_action": action,
        "open_rate": open_r,
        "reply_rate": reply_r,
        "bounce_rate": bounce,
        "spam_rate": spam,
        "domain_health_score": domain_score,
    }


def evaluate_all_campaigns(campaigns: list[dict]) -> list[dict]:
    return [evaluate_campaign_health(c) for c in campaigns]
