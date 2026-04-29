from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import List, Optional

from src.schemas.icp_profile import ICPProfile
from src.utils.logger import get_logger

log = get_logger(__name__)

_DEFAULT_WEIGHTS = {
    "industry_fit": 25,
    "member_volume": 25,
    "employee_count": 15,
    "growth_signal": 15,
    "hiring_signal": 10,
    "tech_stack_signal": 10,
}

_DEFAULT_TIERS = {
    "tier_1": {"min": 80, "max": 100, "label": "Tier 1"},
    "tier_2": {"min": 60, "max": 79, "label": "Tier 2"},
    "tier_3": {"min": 40, "max": 59, "label": "Tier 3"},
    "disqualified": {"min": 0, "max": 39, "label": "Disqualified"},
}

_WEIGHT_KEYS = list(_DEFAULT_WEIGHTS.keys())


def _safe_div(n: float, d: float) -> float:
    return n / d if d else 0.0


def _industry_scores(profile: ICPProfile) -> dict:
    if not profile.industry_breakdown:
        return {"default": 0.0}
    top_index = max(s.index for s in profile.industry_breakdown) or 1.0
    scores = {}
    for seg in profile.industry_breakdown:
        score = round(min(_safe_div(seg.index, top_index), 1.0), 4)
        scores[seg.name] = score
    scores["default"] = 0.0
    return scores


def _percentile(values: List[float], p: float) -> float:
    if not values:
        return 0.0
    sorted_v = sorted(values)
    idx = (p / 100) * (len(sorted_v) - 1)
    lo = int(idx)
    hi = lo + 1
    if hi >= len(sorted_v):
        return sorted_v[-1]
    frac = idx - lo
    return sorted_v[lo] + frac * (sorted_v[hi] - sorted_v[lo])


def _member_volume_thresholds(profile: ICPProfile) -> dict:
    if not profile.member_volume_breakdown:
        return {
            "high": {"min": 750000, "multiplier": 1.0},
            "mid": {"min": 250000, "multiplier": 0.7},
            "low": {"min": 50000, "multiplier": 0.4},
            "none": {"min": 0, "multiplier": 0.0},
        }

    # Use index as proxy for multiplier, ordered by min threshold
    segs = sorted(profile.member_volume_breakdown, key=lambda s: s.index, reverse=True)
    top_index = segs[0].index if segs else 1.0

    # Extract band mins from segment names
    def _band_min(name: str) -> int:
        try:
            return int(name.split("-")[0].replace("+", ""))
        except (ValueError, AttributeError):
            return 0

    # Build thresholds from top 3 bands (high/mid/low)
    candidate_mins = sorted({_band_min(s.name) for s in segs}, reverse=True)
    high_min = candidate_mins[0] if len(candidate_mins) > 0 else 750000
    mid_min = candidate_mins[1] if len(candidate_mins) > 1 else 250000
    low_min = candidate_mins[2] if len(candidate_mins) > 2 else 50000

    def _mult(band_min: int) -> float:
        seg = next((s for s in segs if _band_min(s.name) == band_min), None)
        if seg is None:
            return 0.0
        return round(min(_safe_div(seg.index, top_index), 1.0), 2) if top_index else 0.0

    return {
        "high": {"min": max(high_min, mid_min + 1), "multiplier": 1.0},
        "mid": {"min": max(mid_min, low_min + 1), "multiplier": max(_mult(mid_min), 0.3)},
        "low": {"min": max(low_min, 1), "multiplier": max(_mult(low_min), 0.1)},
        "none": {"min": 0, "multiplier": 0.0},
    }


def _employee_count_thresholds(profile: ICPProfile) -> dict:
    if not profile.employee_size_breakdown:
        return {
            "high": {"min": 1000, "multiplier": 1.0},
            "mid": {"min": 250, "multiplier": 0.7},
            "low": {"min": 100, "multiplier": 0.4},
            "none": {"min": 0, "multiplier": 0.0},
        }

    band_map = {
        "<100": 0, "100-499": 100, "500-1999": 500,
        "2000-9999": 2000, "10000+": 10000,
    }
    segs = sorted(profile.employee_size_breakdown, key=lambda s: s.index, reverse=True)
    top_index = segs[0].index if segs else 1.0

    def _mult(seg_name: str) -> float:
        seg = next((s for s in segs if s.name == seg_name), None)
        if seg is None:
            return 0.0
        return round(min(_safe_div(seg.index, top_index), 1.0), 2) if top_index else 0.0

    # Sort existing bands by min threshold descending to assign high/mid/low
    present_bands = sorted(
        [(name, mn) for name, mn in band_map.items()
         if any(s.name == name for s in profile.employee_size_breakdown)],
        key=lambda x: x[1], reverse=True,
    )
    high_name = present_bands[0][0] if len(present_bands) > 0 else "2000-9999"
    mid_name = present_bands[1][0] if len(present_bands) > 1 else "500-1999"
    low_name = present_bands[2][0] if len(present_bands) > 2 else "100-499"

    return {
        "high": {"min": band_map.get(high_name, 1000), "multiplier": 1.0},
        "mid": {"min": band_map.get(mid_name, 250), "multiplier": max(_mult(mid_name), 0.3)},
        "low": {"min": band_map.get(low_name, 100), "multiplier": max(_mult(low_name), 0.1)},
        "none": {"min": 0, "multiplier": 0.0},
    }


def _tech_stack_scores(profile: ICPProfile) -> dict:
    won_stacks = {s.name for s in profile.tech_stack_breakdown if s.win_count > 0}
    lost_only_stacks = {s.name for s in profile.tech_stack_breakdown
                        if s.win_count == 0 and s.loss_count > 0}
    full_list = sorted(won_stacks)
    none_list = sorted(lost_only_stacks - won_stacks)
    return {
        "full": full_list,
        "partial_multiplier": 0.5,
        "none": none_list if none_list else ["Unknown"],
    }


def _calculate_weights(profile: ICPProfile) -> dict:
    base = dict(_DEFAULT_WEIGHTS)

    # If no member volume data, zero out member_volume weight
    if not profile.member_volume_breakdown:
        zeroed = base.pop("member_volume")
        # redistribute proportionally
        remaining_total = sum(base.values())
        for k in base:
            base[k] = round(base[k] + zeroed * _safe_div(base[k], remaining_total), 4)
        base["member_volume"] = 0

    # Normalize to exactly 100
    total = sum(base.values())
    if abs(total - 100) > 0.01:
        # Add/subtract from the largest non-zero key
        largest = max((k for k in base if base[k] > 0), key=lambda k: base[k])
        base[largest] = round(base[largest] + (100 - total), 4)

    return base


def generate_icp_rules(
    profile: ICPProfile,
    existing_rules: Optional[dict] = None,
) -> dict:
    weights = _calculate_weights(profile)
    # Round weights to integers (sum must still = 100)
    int_weights = {k: int(round(v)) for k, v in weights.items()}
    diff = 100 - sum(int_weights.values())
    if diff != 0:
        largest = max((k for k in int_weights if int_weights[k] > 0), key=lambda k: int_weights[k])
        int_weights[largest] += diff

    rules = {
        "weights": int_weights,
        "tiers": _DEFAULT_TIERS,
        "industry_scores": _industry_scores(profile),
        "member_volume_thresholds": _member_volume_thresholds(profile),
        "employee_count_thresholds": _employee_count_thresholds(profile),
        "tech_stack_scores": _tech_stack_scores(profile),
    }
    log.info("Generated ICP rules from profile (confidence=%s)", profile.confidence_level)
    return rules


def save_icp_rules(rules: dict, output_path: str) -> None:
    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(rules, f, indent=2)
    log.info("Saved ICP rules to %s", output_path)


def save_icp_rules_with_history(rules: dict, config_dir: str) -> None:
    current_path = os.path.join(config_dir, "icp_rules.json")
    save_icp_rules(rules, current_path)

    history_dir = os.path.join(config_dir, "icp_history")
    os.makedirs(history_dir, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    history_path = os.path.join(history_dir, f"icp_rules_{ts}.json")
    save_icp_rules(rules, history_path)
    log.info("Saved ICP rules history to %s", history_path)
