"""
Clay-style enrichment mock module.
# Future: Replace this mock enrichment logic with Clay enrichment workflows and waterfall enrichment.
"""

from __future__ import annotations

PERSONA_MAP = {
    "Managed Care": [
        "VP Member Engagement",
        "Director Medicaid Operations",
        "Chief Digital Officer",
        "Director Member Services",
    ],
    "Health Plan": [
        "VP Member Engagement",
        "Director Medicaid Operations",
        "Chief Digital Officer",
        "Director Member Services",
    ],
    "Provider": [
        "VP Population Health",
        "Director Patient Engagement",
        "Chief Digital Officer",
    ],
    "Healthcare Technology": [
        "Revenue Operations Manager",
        "VP Customer Experience",
        "Chief Digital Officer",
    ],
}

DEFAULT_PERSONAS = ["Revenue Operations Manager", "VP Customer Experience"]

APPROVED_TIERS = {"Tier 1", "Tier 2"}


def _get_enriched_signal_summary(company: dict) -> str:
    signals = []
    if company.get("growth_signal"):
        signals.append("growth hiring detected")
    if company.get("hiring_signal"):
        signals.append("active hiring")
    tech = company.get("tech_stack_signal", "Unknown")
    if tech and tech != "Unknown":
        signals.append(f"tech: {tech}")
    return "; ".join(signals) if signals else "no strong signals"


def enrich_accounts(companies: list) -> list:
    from src.utils.logger import get_logger
    log = get_logger(__name__)
    enriched = []
    failures = 0
    for company in companies:
        try:
            industry = company.get("industry", "")
            tier = company.get("icp_tier", "Disqualified")
            approved = tier in APPROVED_TIERS

            personas = PERSONA_MAP.get(industry, DEFAULT_PERSONAS)

            company["enrichment_status"] = "enriched"
            company["enrichment_source"] = "clay_mock"
            company["recommended_personas"] = ", ".join(personas)
            company["enriched_signal_summary"] = _get_enriched_signal_summary(company)
            company["contact_discovery_approved"] = approved

            enriched.append(company)
        except Exception as exc:
            failures += 1
            cid = company.get("company_id", "?") if isinstance(company, dict) else "?"
            log.warning("Enrichment failed for %s: %s", cid, exc)
    log.info("Enriched %d/%d companies, %d failures", len(enriched), len(companies), failures)
    return enriched
