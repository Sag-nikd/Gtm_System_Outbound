"""
ICP scoring module — scores and tiers companies based on configurable rules.
"""

from __future__ import annotations
import json


def load_icp_rules(file_path: str) -> dict:
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def _score_industry(company: dict, rules: dict) -> tuple[float, str]:
    industry = company.get("industry", "")
    scores = rules["industry_scores"]
    multiplier = scores.get(industry, scores["default"])
    points = rules["weights"]["industry_fit"] * multiplier
    reason = f"industry={industry} → {int(multiplier*100)}% of industry_fit weight"
    return round(points, 2), reason


def _score_volume(company: dict, rules: dict) -> tuple[float, str]:
    total = company.get("primary_volume_metric", 0) + company.get("secondary_volume_metric", 0)
    weight = rules["weights"]["volume_metric"]
    thresholds = rules["volume_thresholds"]

    if total >= thresholds["high"]["min"]:
        multiplier, band = thresholds["high"]["multiplier"], "high"
    elif total >= thresholds["mid"]["min"]:
        multiplier, band = thresholds["mid"]["multiplier"], "mid"
    elif total >= thresholds["low"]["min"]:
        multiplier, band = thresholds["low"]["multiplier"], "low"
    else:
        multiplier, band = thresholds["none"]["multiplier"], "none"

    points = weight * multiplier
    reason = f"total_volume={total:,} → {band} band ({int(multiplier*100)}%)"
    return round(points, 2), reason


def _score_employee_count(company: dict, rules: dict) -> tuple[float, str]:
    count = company.get("employee_count", 0)
    weight = rules["weights"]["employee_count"]
    thresholds = rules["employee_count_thresholds"]

    if count >= thresholds["high"]["min"]:
        multiplier, band = thresholds["high"]["multiplier"], "high"
    elif count >= thresholds["mid"]["min"]:
        multiplier, band = thresholds["mid"]["multiplier"], "mid"
    elif count >= thresholds["low"]["min"]:
        multiplier, band = thresholds["low"]["multiplier"], "low"
    else:
        multiplier, band = thresholds["none"]["multiplier"], "none"

    points = weight * multiplier
    reason = f"employees={count:,} → {band} band ({int(multiplier*100)}%)"
    return round(points, 2), reason


def _score_growth_signal(company: dict, rules: dict) -> tuple[float, str]:
    signal = company.get("growth_signal", False)
    weight = rules["weights"]["growth_signal"]
    points = weight if signal else 0.0
    return points, f"growth_signal={signal}"


def _score_hiring_signal(company: dict, rules: dict) -> tuple[float, str]:
    signal = company.get("hiring_signal", False)
    weight = rules["weights"]["hiring_signal"]
    points = weight if signal else 0.0
    return points, f"hiring_signal={signal}"


def _score_tech_stack(company: dict, rules: dict) -> tuple[float, str]:
    tech = company.get("tech_stack_signal", "Unknown")
    weight = rules["weights"]["tech_stack_signal"]
    full_list = rules["tech_stack_scores"]["full"]
    none_list = rules["tech_stack_scores"]["none"]

    if tech in full_list:
        points = weight
        reason = f"tech_stack={tech} → full points"
    elif tech in none_list:
        points = 0.0
        reason = f"tech_stack={tech} → 0 points"
    else:
        partial = rules["tech_stack_scores"]["partial_multiplier"]
        points = weight * partial
        reason = f"tech_stack={tech} → partial ({int(partial*100)}%)"

    return round(points, 2), reason


def _assign_tier(score: float, rules: dict) -> str:
    for key in ["tier_1", "tier_2", "tier_3", "disqualified"]:
        t = rules["tiers"][key]
        if t["min"] <= score <= t["max"]:
            return t["label"]
    return "Disqualified"


def score_company(company: dict, rules: dict) -> dict:
    industry_pts, industry_reason = _score_industry(company, rules)
    volume_pts, volume_reason = _score_volume(company, rules)
    employee_pts, employee_reason = _score_employee_count(company, rules)
    growth_pts, growth_reason = _score_growth_signal(company, rules)
    hiring_pts, hiring_reason = _score_hiring_signal(company, rules)
    tech_pts, tech_reason = _score_tech_stack(company, rules)

    total = industry_pts + volume_pts + employee_pts + growth_pts + hiring_pts + tech_pts
    tier = _assign_tier(total, rules)

    company["total_volume"] = (
        company.get("primary_volume_metric", 0) + company.get("secondary_volume_metric", 0)
    )
    company["industry_score"] = industry_pts
    company["volume_score"] = volume_pts
    company["employee_count_score"] = employee_pts
    company["growth_signal_score"] = growth_pts
    company["hiring_signal_score"] = hiring_pts
    company["tech_stack_score"] = tech_pts
    company["icp_score"] = round(total, 2)
    company["icp_tier"] = tier
    company["score_reason"] = " | ".join([
        industry_reason, volume_reason, employee_reason,
        growth_reason, hiring_reason, tech_reason
    ])
    company["tier_reason"] = f"score={total:.1f} → {tier}"

    return company


def score_companies(companies: list, rules: dict) -> list:
    from src.utils.logger import get_logger
    log = get_logger(__name__)
    results = []
    failures = 0
    for company in companies:
        try:
            results.append(score_company(company, rules))
        except (AttributeError, KeyError, TypeError, ValueError) as exc:
            failures += 1
            cid = company.get("company_id", "?") if isinstance(company, dict) else "?"
            log.warning("Scoring failed for %s: %s", cid, exc)
    log.info("Scored %d/%d companies, %d failures", len(results), len(companies), failures)
    return results
