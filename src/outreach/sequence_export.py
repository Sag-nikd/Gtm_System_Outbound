"""
Outreach sequence export module.
# Future: Replace email CSV export with Outreach, Salesloft, Apollo Sequences,
#         Instantly, Smartlead, or HubSpot Sequences API.
# Future: Replace LinkedIn CSV export with HeyReach API integration.
"""

from __future__ import annotations

CAMPAIGN_NAME = "HealConnect Member Engagement - Tier 1/2"

EMAIL_ANGLES = {
    "VP Member Engagement": (
        "Member engagement ROI for health plans",
        "How peers improved HEDIS scores with better engagement",
        "Quick win: 3 tactics for Medicaid member retention",
    ),
    "Director Medicaid Operations": (
        "Reducing Medicaid churn with proactive outreach",
        "Operational efficiency in Medicaid member services",
        "Case study: lowering gaps-in-care rates at scale",
    ),
    "Chief Digital Officer": (
        "Digital transformation in member experience",
        "API-first engagement platforms for health plans",
        "Connecting your tech stack to member outcomes",
    ),
    "Director Member Services": (
        "Improving first-call resolution for member services",
        "Omnichannel strategies for Medicaid populations",
        "Reducing member friction across service touchpoints",
    ),
    "VP Population Health": (
        "Population health programs that drive engagement",
        "Closing care gaps with intelligent member outreach",
        "Outcomes-based engagement for at-risk populations",
    ),
    "Revenue Operations Manager": (
        "RevOps alignment in healthcare GTM",
        "Scaling outbound pipeline in health tech",
        "Improving CRM hygiene for faster sales cycles",
    ),
    "VP Customer Experience": (
        "CX-driven growth in digital health",
        "Building loyalty in member and patient journeys",
        "NPS improvement strategies for health plan CX teams",
    ),
}

DEFAULT_ANGLES = (
    "Improving engagement outcomes for health organizations",
    "Proven strategies for member retention and growth",
    "How leading teams are modernizing member engagement",
)

LINKEDIN_TEMPLATES = {
    "connection_message": (
        "Hi {first_name}, I work with health plans and managed care orgs on member engagement "
        "and digital outreach strategy. Would love to connect and share what's working."
    ),
    "followup_message_1": (
        "Hi {first_name}, thanks for connecting. We help {industry_type} teams improve member "
        "engagement rates — happy to share a short case study if relevant."
    ),
    "followup_message_2": (
        "Hi {first_name}, following up one last time — open to a 15-min call to explore if "
        "there's a fit? No pressure either way. Happy to send a resource instead."
    ),
}


def _get_email_angles(persona: str) -> tuple[str, str, str]:
    return EMAIL_ANGLES.get(persona, DEFAULT_ANGLES)


def create_email_sequence_export(contacts: list[dict]) -> list[dict]:
    rows = []
    for ct in contacts:
        if ct.get("final_validation_status") != "approved":
            continue
        a1, a2, a3 = _get_email_angles(ct.get("persona_type", ""))
        rows.append({
            "first_name": ct.get("first_name"),
            "last_name": ct.get("last_name"),
            "email": ct.get("email"),
            "title": ct.get("title"),
            "company_name": ct.get("company_name", ""),
            "persona_type": ct.get("persona_type"),
            "icp_tier": ct.get("icp_tier"),
            "campaign_name": CAMPAIGN_NAME,
            "sequence_status": "Ready for Outreach",
            "email_step_1_angle": a1,
            "email_step_2_angle": a2,
            "email_step_3_angle": a3,
        })
    return rows


def create_linkedin_sequence_export(contacts: list[dict]) -> list[dict]:
    rows = []
    for ct in contacts:
        if ct.get("final_validation_status") != "approved":
            continue
        first = ct.get("first_name", "")
        industry_type = "health plan and managed care"
        rows.append({
            "first_name": first,
            "last_name": ct.get("last_name"),
            "linkedin_url": ct.get("linkedin_url"),
            "title": ct.get("title"),
            "company_name": ct.get("company_name", ""),
            "persona_type": ct.get("persona_type"),
            "icp_tier": ct.get("icp_tier"),
            "campaign_name": CAMPAIGN_NAME,
            "connection_message": LINKEDIN_TEMPLATES["connection_message"].format(
                first_name=first
            ),
            "followup_message_1": LINKEDIN_TEMPLATES["followup_message_1"].format(
                first_name=first, industry_type=industry_type
            ),
            "followup_message_2": LINKEDIN_TEMPLATES["followup_message_2"].format(
                first_name=first
            ),
            "linkedin_sequence_status": "Ready for Outreach",
        })
    return rows
