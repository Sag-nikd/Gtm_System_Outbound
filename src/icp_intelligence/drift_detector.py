from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from src.schemas.icp_drift import ICPDriftReport, DimensionDrift
from src.schemas.icp_profile import ICPProfile
from src.utils.logger import get_logger

log = get_logger(__name__)

_STABLE_THRESHOLD = 3.0   # weight delta < 3 points = stable
_INDUSTRY_SCORE_THRESHOLD = 0.2  # score delta > 0.2 = significant


def _safe_div(n: float, d: float) -> float:
    return n / d if d else 0.0


def _direction(delta: float) -> str:
    if abs(delta) < _STABLE_THRESHOLD:
        return "stable"
    return "increase" if delta > 0 else "decrease"


def _weight_drifts(current_rules: dict, recommended_rules: dict) -> List[DimensionDrift]:
    cur_w = current_rules.get("weights", {})
    rec_w = recommended_rules.get("weights", {})
    all_dims = set(cur_w.keys()) | set(rec_w.keys())
    drifts = []
    for dim in sorted(all_dims):
        cur = float(cur_w.get(dim, 0))
        rec = float(rec_w.get(dim, 0))
        delta = abs(rec - cur)
        direction = _direction(rec - cur)
        explanation = "{} weight moved from {} to {} ({}{:.1f} pts)".format(
            dim, cur, rec,
            "+" if rec > cur else "",
            rec - cur,
        )
        drifts.append(DimensionDrift(
            dimension=dim,
            current_weight=cur,
            recommended_weight=rec,
            weight_delta=delta,
            drift_direction=direction,
            explanation=explanation,
        ))
    return drifts


def _industry_changes(current_rules: dict, recommended_rules: dict) -> List[dict]:
    cur_scores = current_rules.get("industry_scores", {})
    rec_scores = recommended_rules.get("industry_scores", {})
    all_industries = set(cur_scores.keys()) | set(rec_scores.keys())
    changes = []
    for ind in sorted(all_industries):
        if ind == "default":
            continue
        cur = float(cur_scores.get(ind, 0.0))
        rec = float(rec_scores.get(ind, 0.0))
        delta = abs(rec - cur)
        if delta > _INDUSTRY_SCORE_THRESHOLD:
            changes.append({
                "industry": ind,
                "current_score": cur,
                "recommended_score": rec,
                "delta": round(delta, 4),
            })
    return changes


def _threshold_changes(current_rules: dict, recommended_rules: dict) -> List[dict]:
    changes = []
    for key in ("member_volume_thresholds", "employee_count_thresholds"):
        cur_t = current_rules.get(key, {})
        rec_t = recommended_rules.get(key, {})
        for band in ("high", "mid", "low"):
            cur_min = cur_t.get(band, {}).get("min", 0)
            rec_min = rec_t.get(band, {}).get("min", 0)
            if cur_min != rec_min:
                changes.append({
                    "threshold": key,
                    "band": band,
                    "current_min": cur_min,
                    "recommended_min": rec_min,
                })
    return changes


def _is_critical_industry_change(industry_changes: List[dict], current_rules: dict) -> bool:
    """Critical if the TOP industry (score=1.0 in current) has a large score drop."""
    top_industries = [
        ind for ind, score in current_rules.get("industry_scores", {}).items()
        if ind != "default" and float(score) >= 1.0
    ]
    for change in industry_changes:
        if change["industry"] in top_industries and change["delta"] > _INDUSTRY_SCORE_THRESHOLD:
            return True
    return False


def detect_drift(
    current_rules: dict,
    recommended_rules: dict,
    profile: ICPProfile,
) -> ICPDriftReport:
    dim_drifts = _weight_drifts(current_rules, recommended_rules)
    ind_changes = _industry_changes(current_rules, recommended_rules)
    thr_changes = _threshold_changes(current_rules, recommended_rules)

    # Count shifted dimensions (weight delta >= stable threshold)
    shifted_dims = [d for d in dim_drifts if d.drift_direction != "stable"]
    num_shifted = len(shifted_dims)

    # Determine severity
    is_critical_ind = _is_critical_industry_change(ind_changes, current_rules)
    if is_critical_ind:
        severity = "critical"
    elif num_shifted >= 3:
        severity = "major"
    elif num_shifted >= 1:
        severity = "minor"
    else:
        severity = "none"

    drift_detected = severity != "none"

    # Build action items
    action_items = []
    for change in ind_changes:
        action_items.append(
            "Review industry score for '{}': {:.2f} → {:.2f}".format(
                change["industry"], change["current_score"], change["recommended_score"]
            )
        )
    for d in shifted_dims:
        action_items.append(
            "Update {} weight: {} → {} ({})".format(
                d.dimension, int(d.current_weight), int(d.recommended_weight), d.drift_direction
            )
        )
    for thr in thr_changes:
        action_items.append(
            "Recalibrate {} {} band: min {} → {}".format(
                thr["threshold"], thr["band"], thr["current_min"], thr["recommended_min"]
            )
        )
    if not action_items and drift_detected:
        action_items.append("Review recommended rules against current targeting.")

    # should_auto_update: only minor + high confidence
    should_auto_update = (severity == "minor" and profile.confidence_level == "high")

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    report = ICPDriftReport(
        drift_detected=drift_detected,
        drift_severity=severity,
        dimension_drifts=dim_drifts,
        industry_changes=ind_changes,
        threshold_changes=thr_changes,
        action_items=action_items,
        should_auto_update=should_auto_update,
        generated_at=generated_at,
    )
    log.info("Drift detection complete — severity=%s, shifted_dims=%d", severity, num_shifted)
    return report
