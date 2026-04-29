"""
Outreach sequence export module.
# Future: Replace email CSV export with Outreach, Salesloft, Apollo Sequences,
#         Instantly, Smartlead, or HubSpot Sequences API.
# Future: Replace LinkedIn CSV export with HeyReach API integration.
"""

from __future__ import annotations

import json
import os

_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "config", "outreach_templates.json",
)

with open(_CONFIG_PATH) as _f:
    _templates = json.load(_f)

CAMPAIGN_NAME: str = _templates["campaign_name"]
EMAIL_ANGLES: dict = _templates["email_angles"]
DEFAULT_ANGLES: list = _templates["default_angles"]
LINKEDIN_TEMPLATES: dict = _templates["linkedin_templates"]


def _get_email_angles(persona: str) -> list:
    return EMAIL_ANGLES.get(persona, DEFAULT_ANGLES)


def _fmt(template: str, **kwargs) -> str:
    try:
        return template.format(**kwargs)
    except KeyError:
        return template


def create_email_sequence_export(contacts: list[dict]) -> list[dict]:
    rows = []
    for ct in contacts:
        if ct.get("final_validation_status") != "approved":
            continue
        angles = _get_email_angles(ct.get("persona_type", ""))
        a1, a2, a3 = angles[0], angles[1], angles[2]
        industry_type = ct.get("industry", "")
        company_name = ct.get("company_name", "")
        rows.append({
            "first_name": ct.get("first_name"),
            "last_name": ct.get("last_name"),
            "email": ct.get("email"),
            "title": ct.get("title"),
            "company_name": company_name,
            "persona_type": ct.get("persona_type"),
            "icp_tier": ct.get("icp_tier"),
            "campaign_name": _fmt(CAMPAIGN_NAME, industry_type=industry_type),
            "sequence_status": "Ready for Outreach",
            "email_step_1_angle": _fmt(a1, industry_type=industry_type, company_name=company_name),
            "email_step_2_angle": _fmt(a2, industry_type=industry_type, company_name=company_name),
            "email_step_3_angle": _fmt(a3, industry_type=industry_type, company_name=company_name),
        })
    return rows


def create_linkedin_sequence_export(contacts: list[dict]) -> list[dict]:
    rows = []
    for ct in contacts:
        if ct.get("final_validation_status") != "approved":
            continue
        first = ct.get("first_name", "")
        industry_type = ct.get("industry", "your industry")
        rows.append({
            "first_name": first,
            "last_name": ct.get("last_name"),
            "linkedin_url": ct.get("linkedin_url"),
            "title": ct.get("title"),
            "company_name": ct.get("company_name", ""),
            "persona_type": ct.get("persona_type"),
            "icp_tier": ct.get("icp_tier"),
            "campaign_name": _fmt(CAMPAIGN_NAME, industry_type=industry_type),
            "connection_message": _fmt(
                LINKEDIN_TEMPLATES["connection_message"],
                first_name=first, industry_type=industry_type,
            ),
            "followup_message_1": _fmt(
                LINKEDIN_TEMPLATES["followup_message_1"],
                first_name=first, industry_type=industry_type,
            ),
            "followup_message_2": _fmt(
                LINKEDIN_TEMPLATES["followup_message_2"],
                first_name=first, industry_type=industry_type,
            ),
            "linkedin_sequence_status": "Ready for Outreach",
        })
    return rows
