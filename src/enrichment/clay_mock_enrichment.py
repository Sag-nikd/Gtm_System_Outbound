"""
Clay-style enrichment mock module.
# Future: Replace this mock enrichment logic with Clay enrichment workflows and waterfall enrichment.
"""

from __future__ import annotations

import json
import os

_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "config", "persona_map.json",
)

with open(_CONFIG_PATH) as _f:
    _persona_config = json.load(_f)

PERSONA_MAP: dict = _persona_config["industry_personas"]
DEFAULT_PERSONAS: list = _persona_config["default_personas"]

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
