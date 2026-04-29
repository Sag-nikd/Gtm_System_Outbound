from __future__ import annotations

import json
import os
from typing import List, Optional

from src.schemas.icp_profile import ICPProfile
from src.schemas.apollo_query import ApolloQueryConfig
from src.utils.logger import get_logger

log = get_logger(__name__)

_SIZE_BAND_RANGES = {
    "<100": {"min": 1, "max": 99},
    "100-499": {"min": 100, "max": 499},
    "500-1999": {"min": 500, "max": 1999},
    "2000-9999": {"min": 2000, "max": 9999},
    "10000+": {"min": 10000, "max": 999999},
}

_ADJACENT_BANDS = {
    "<100": ["<100", "100-499"],
    "100-499": ["<100", "100-499", "500-1999"],
    "500-1999": ["100-499", "500-1999", "2000-9999"],
    "2000-9999": ["500-1999", "2000-9999", "10000+"],
    "10000+": ["2000-9999", "10000+"],
}

_DEFAULT_PERSONA_TITLES = [
    "VP Member Engagement",
    "Director Medicaid Operations",
    "Chief Digital Officer",
    "Director Member Services",
    "VP Population Health",
]

_DEFAULT_SENIORITY = ["VP", "Director", "C-Suite"]


def _employee_ranges(profile: ICPProfile) -> List[dict]:
    if not profile.employee_size_breakdown:
        return [{"min": 250, "max": 9999}]
    top_band = profile.employee_size_breakdown[0].name
    adjacent = _ADJACENT_BANDS.get(top_band, [top_band])
    ranges = []
    for band in adjacent:
        rng = _SIZE_BAND_RANGES.get(band)
        if rng:
            ranges.append(dict(rng))
    if not ranges:
        ranges = [{"min": 250, "max": 9999}]
    return ranges


def _top_industries(profile: ICPProfile, rules: dict, min_index: float = 0.5) -> List[str]:
    return [
        seg.name for seg in profile.industry_breakdown
        if seg.index >= min_index
    ]


def _location_states(profile: ICPProfile) -> List[str]:
    if not profile.geo_breakdown:
        return []
    overall_cr = profile.conversion_rate
    return [
        seg.name for seg in profile.geo_breakdown
        if seg.conversion_rate >= overall_cr and seg.name
    ]


def _technology_names(rules: dict) -> List[str]:
    return list(rules.get("tech_stack_scores", {}).get("full", []))


def _exclusion_domains(deals: Optional[List[dict]]) -> List[str]:
    if not deals:
        return []
    return [
        d.get("domain", "").strip().lower()
        for d in deals
        if d.get("deal_stage") == "closed_won" and d.get("domain")
    ]


def _exclusion_industries(profile: ICPProfile) -> List[str]:
    excluded = []
    for seg in profile.industry_breakdown:
        if seg.conversion_rate == 0.0 and seg.deal_count > 3:
            excluded.append(seg.name)
    return excluded


def _persona_titles(profile: ICPProfile) -> List[str]:
    titles = []
    if profile.top_converting_persona:
        titles.append(profile.top_converting_persona)
    for t in _DEFAULT_PERSONA_TITLES:
        if t not in titles:
            titles.append(t)
    return titles


def build_apollo_query(
    profile: ICPProfile,
    rules: dict,
    deals: Optional[List[dict]] = None,
    tam: Optional[List[dict]] = None,
) -> ApolloQueryConfig:
    industries = _top_industries(profile, rules)
    emp_ranges = _employee_ranges(profile)
    states = _location_states(profile)
    tech = _technology_names(rules)
    excl_domains = _exclusion_domains(deals)
    excl_industries = _exclusion_industries(profile)
    persona_titles = _persona_titles(profile)

    # estimated TAM size from TAM data matching filters
    tam_size = 0
    if tam:
        ind_set = set(industries)
        for company in tam:
            if company.get("industry") in ind_set:
                tam_size += 1

    top_ind = industries[0] if industries else "your target market"
    top_size = profile.employee_size_breakdown[0].name if profile.employee_size_breakdown else "mid-market"
    cr_pct = "{:.0%}".format(profile.conversion_rate)
    rationale = (
        "{} organizations are your highest-converting segment ({}% conversion). "
        "Targeting {} employee count band based on win patterns. "
        "Excluding {} industries with 0% conversion and {} existing customers."
    ).format(
        top_ind, cr_pct.replace("%", ""),
        top_size,
        len(excl_industries),
        len(excl_domains),
    )

    config = ApolloQueryConfig(
        organization_search={
            "industry_keywords": industries,
            "employee_ranges": emp_ranges,
            "location_states": states,
            "technology_names": tech,
        },
        contact_search={
            "persona_titles": persona_titles,
            "seniority_levels": list(_DEFAULT_SENIORITY),
        },
        exclusions={
            "domains": excl_domains,
            "industries": excl_industries,
        },
        estimated_tam_size=tam_size,
        query_rationale=rationale,
    )
    log.info("Built Apollo query config — %d industries, %d exclusions",
             len(industries), len(excl_domains))
    return config


def save_apollo_config(config: ApolloQueryConfig, output_path: str) -> None:
    config.save(output_path)
    log.info("Saved Apollo query config to %s", output_path)
