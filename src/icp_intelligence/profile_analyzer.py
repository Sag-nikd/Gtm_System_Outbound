from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import List, Optional

from src.schemas.icp_profile import (
    ICPProfile, IndustrySegment, SizeSegment, GeoSegment,
    VolumeSegment, TechSegment, LossReason,
)
from src.utils.logger import get_logger

log = get_logger(__name__)

_TERMINAL_WON = {"closed_won"}
_TERMINAL_LOST = {"closed_lost", "disqualified"}

_SIZE_BANDS = [
    ("<100", 0, 99),
    ("100-499", 100, 499),
    ("500-1999", 500, 1999),
    ("2000-9999", 2000, 9999),
    ("10000+", 10000, 10 ** 9),
]

_MEMBER_BANDS = [
    ("0", 0, 0),
    ("1-49999", 1, 49999),
    ("50000-249999", 50000, 249999),
    ("250000-749999", 250000, 749999),
    ("750000+", 750000, 10 ** 9),
]


def _safe_div(num: float, denom: float) -> float:
    return num / denom if denom else 0.0


def _overall_conversion(deals: List[dict]) -> float:
    won = sum(1 for d in deals if d.get("deal_stage") in _TERMINAL_WON)
    closed = sum(1 for d in deals if d.get("deal_stage") in _TERMINAL_WON | _TERMINAL_LOST)
    return _safe_div(won, closed)


def _build_segments(deals: List[dict], key_fn, names, overall_cr: float):
    """Generic segment builder. names is either a list of (label, ...) tuples or None for dynamic."""
    buckets = defaultdict(lambda: {"won": 0, "lost": 0, "total": 0, "values": []})

    for d in deals:
        label = key_fn(d)
        if label is None:
            continue
        stage = d.get("deal_stage", "")
        buckets[label]["total"] += 1
        if stage in _TERMINAL_WON:
            buckets[label]["won"] += 1
            val = d.get("deal_value")
            if val is not None:
                try:
                    buckets[label]["values"].append(float(val))
                except (TypeError, ValueError):
                    pass
        elif stage in _TERMINAL_LOST:
            buckets[label]["lost"] += 1

    segments = []
    for label, b in buckets.items():
        cr = _safe_div(b["won"], b["won"] + b["lost"])
        avg_val = _safe_div(sum(b["values"]), len(b["values"])) if b["values"] else 0.0
        idx = _safe_div(cr, overall_cr)
        segments.append({
            "name": label,
            "deal_count": b["total"],
            "win_count": b["won"],
            "loss_count": b["lost"],
            "conversion_rate": cr,
            "avg_deal_value": avg_val,
            "index": idx,
        })
    return sorted(segments, key=lambda s: s["index"], reverse=True)


def _size_band(emp: int) -> str:
    for label, lo, hi in _SIZE_BANDS:
        if lo <= emp <= hi:
            return label
    return "Unknown"


def _member_band(total_members: int) -> str:
    for label, lo, hi in _MEMBER_BANDS:
        if lo <= total_members <= hi:
            return label
    return "750000+"


def analyze_icp(
    deals: List[dict],
    pipeline: Optional[List[dict]] = None,
    tam: Optional[List[dict]] = None,
) -> ICPProfile:
    overall_cr = _overall_conversion(deals)
    won_deals = [d for d in deals if d.get("deal_stage") in _TERMINAL_WON]

    # avg deal value (won only)
    won_values = [float(d["deal_value"]) for d in won_deals
                  if d.get("deal_value") is not None]
    avg_deal_value = _safe_div(sum(won_values), len(won_values)) if won_values else 0.0

    # avg deal cycle (won only)
    won_cycles = [int(d["deal_cycle_days"]) for d in won_deals
                  if d.get("deal_cycle_days") is not None]
    avg_cycle = _safe_div(sum(won_cycles), len(won_cycles)) if won_cycles else 0.0

    # industry breakdown
    industry_raw = _build_segments(deals, lambda d: d.get("industry"), None, overall_cr)
    industry_breakdown = [IndustrySegment(**s) for s in industry_raw]

    # employee size breakdown
    def emp_key(d):
        v = d.get("employee_count")
        if v is None:
            return None
        try:
            return _size_band(int(v))
        except (TypeError, ValueError):
            return None

    size_raw = _build_segments(deals, emp_key, None, overall_cr)
    employee_size_breakdown = [SizeSegment(**s) for s in size_raw]

    # geo breakdown
    geo_raw = _build_segments(deals, lambda d: d.get("state") or None, None, overall_cr)
    geo_breakdown = [GeoSegment(**s) for s in geo_raw]

    # volume breakdown — only if any record has volume data
    has_volume_data = any(
        d.get("primary_volume_metric") is not None or d.get("secondary_volume_metric") is not None
        for d in deals
    )
    volume_breakdown = []
    if has_volume_data:
        def member_key(d):
            pv = d.get("primary_volume_metric") or 0
            sv = d.get("secondary_volume_metric") or 0
            try:
                return _member_band(int(pv) + int(sv))
            except (TypeError, ValueError):
                return None
        vol_raw = _build_segments(deals, member_key, None, overall_cr)
        volume_breakdown = [VolumeSegment(**s) for s in vol_raw]

    # tech stack breakdown
    tech_raw = _build_segments(deals, lambda d: d.get("tech_stack") or None, None, overall_cr)
    tech_stack_breakdown = [TechSegment(**s) for s in tech_raw]

    # top converting persona
    persona_raw = _build_segments(deals, lambda d: d.get("contact_persona") or None, None, overall_cr)
    top_converting_persona = persona_raw[0]["name"] if persona_raw else ""

    # best source channel
    channel_raw = _build_segments(deals, lambda d: d.get("source_channel") or None, None, overall_cr)
    best_source_channel = channel_raw[0]["name"] if channel_raw else ""

    # loss reasons
    loss_counts: dict = defaultdict(int)
    for d in deals:
        if d.get("deal_stage") in _TERMINAL_LOST and d.get("loss_reason"):
            loss_counts[d["loss_reason"]] += 1
    total_losses = sum(loss_counts.values())
    loss_reasons = sorted(
        [
            LossReason(reason=r, count=c, percentage=_safe_div(c, total_losses) * 100)
            for r, c in loss_counts.items()
        ],
        key=lambda x: x.count,
        reverse=True,
    )

    # confidence level
    won_count = len(won_deals)
    if won_count <= 10:
        confidence_level = "low" if len(deals) < 10 else "medium"
    elif len(deals) > 30:
        confidence_level = "high"
    else:
        confidence_level = "medium"

    # fix edge: <10 total deals always low
    if len(deals) < 10:
        confidence_level = "low"
    elif len(deals) <= 30:
        confidence_level = "medium"
    else:
        confidence_level = "high"

    # icp summary
    top_ind = industry_breakdown[0].name if industry_breakdown else "unknown"
    top_size = employee_size_breakdown[0].name if employee_size_breakdown else "unknown"
    icp_summary = (
        f"Your strongest ICP is {top_ind} organizations with {top_size} employees. "
        f"Overall conversion rate is {overall_cr:.0%} with an average deal value of "
        f"${avg_deal_value:,.0f} and {avg_cycle:.0f}-day sales cycle. "
        f"Confidence: {confidence_level} ({len(deals)} deals analyzed)."
    )

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    return ICPProfile(
        total_deals_analyzed=len(deals),
        conversion_rate=overall_cr,
        avg_deal_value=avg_deal_value,
        avg_deal_cycle_days=avg_cycle,
        industry_breakdown=industry_breakdown,
        employee_size_breakdown=employee_size_breakdown,
        geo_breakdown=geo_breakdown,
        volume_breakdown=volume_breakdown,
        tech_stack_breakdown=tech_stack_breakdown,
        top_converting_persona=top_converting_persona,
        best_source_channel=best_source_channel,
        loss_reasons=loss_reasons,
        icp_summary=icp_summary,
        confidence_level=confidence_level,
        generated_at=generated_at,
    )
