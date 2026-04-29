"""Story 5: ICP Drift Detector tests."""
from __future__ import annotations

import pytest


def _make_rules(industry_fit=25, member_volume=25, employee_count=15,
                growth_signal=15, hiring_signal=10, tech_stack_signal=10,
                managed_care_score=1.0):
    return {
        "weights": {
            "industry_fit": industry_fit,
            "member_volume": member_volume,
            "employee_count": employee_count,
            "growth_signal": growth_signal,
            "hiring_signal": hiring_signal,
            "tech_stack_signal": tech_stack_signal,
        },
        "tiers": {
            "tier_1": {"min": 80, "max": 100, "label": "Tier 1"},
            "tier_2": {"min": 60, "max": 79, "label": "Tier 2"},
            "tier_3": {"min": 40, "max": 59, "label": "Tier 3"},
            "disqualified": {"min": 0, "max": 39, "label": "Disqualified"},
        },
        "industry_scores": {
            "Managed Care": managed_care_score,
            "Health Plan": 0.8,
            "default": 0.0,
        },
        "member_volume_thresholds": {
            "high": {"min": 750000, "multiplier": 1.0},
            "mid": {"min": 250000, "multiplier": 0.7},
            "low": {"min": 50000, "multiplier": 0.4},
            "none": {"min": 0, "multiplier": 0.0},
        },
        "employee_count_thresholds": {
            "high": {"min": 1000, "multiplier": 1.0},
            "mid": {"min": 250, "multiplier": 0.7},
            "low": {"min": 100, "multiplier": 0.4},
            "none": {"min": 0, "multiplier": 0.0},
        },
        "tech_stack_scores": {
            "full": ["Salesforce", "HubSpot"],
            "partial_multiplier": 0.5,
            "none": ["Unknown"],
        },
    }


def _mock_profile(confidence_level="medium"):
    from src.icp_intelligence.profile_analyzer import analyze_icp
    deals = [
        {"company_name": "A{}".format(i), "industry": "Managed Care", "employee_count": 1000,
         "deal_stage": "closed_won" if i < 15 else "closed_lost", "domain": "a{}.com".format(i),
         "loss_reason": "budget" if i >= 15 else None}
        for i in range(20)
    ]
    if confidence_level == "high":
        deals = deals * 2  # 40 deals → high confidence
    elif confidence_level == "low":
        deals = deals[:5]
    return analyze_icp(deals)


# ── (a) Identical rules → no drift ───────────────────────────────────────────

def test_identical_rules_no_drift():
    from src.icp_intelligence.drift_detector import detect_drift
    rules = _make_rules()
    profile = _mock_profile()
    report = detect_drift(rules, rules, profile)
    assert report.drift_detected is False
    assert report.drift_severity == "none"


# ── (b) One weight changed by 5 → minor ──────────────────────────────────────

def test_one_weight_changed_minor_drift():
    from src.icp_intelligence.drift_detector import detect_drift
    current = _make_rules(industry_fit=25)
    recommended = _make_rules(industry_fit=30, member_volume=20)
    profile = _mock_profile()
    report = detect_drift(current, recommended, profile)
    assert report.drift_detected is True
    assert report.drift_severity == "minor"


# ── (c) Top industry score changed from 1.0 to 0.3 → critical ────────────────

def test_top_industry_score_change_critical():
    from src.icp_intelligence.drift_detector import detect_drift
    current = _make_rules(managed_care_score=1.0)
    recommended = _make_rules(managed_care_score=0.3)
    profile = _mock_profile()
    # Ensure Managed Care is the top industry in the profile's breakdown
    report = detect_drift(current, recommended, profile)
    assert report.drift_detected is True
    assert report.drift_severity == "critical"


# ── (d) Three weights changed → major ────────────────────────────────────────

def test_three_weights_changed_major_drift():
    from src.icp_intelligence.drift_detector import detect_drift
    current = _make_rules(industry_fit=25, member_volume=25, employee_count=15,
                          growth_signal=15, hiring_signal=10, tech_stack_signal=10)
    recommended = _make_rules(industry_fit=35, member_volume=15, employee_count=25,
                               growth_signal=15, hiring_signal=5, tech_stack_signal=5)
    profile = _mock_profile()
    report = detect_drift(current, recommended, profile)
    assert report.drift_detected is True
    assert report.drift_severity in ("major", "critical")


# ── (e) action_items non-empty when drift detected ────────────────────────────

def test_action_items_non_empty_when_drift():
    from src.icp_intelligence.drift_detector import detect_drift
    current = _make_rules(industry_fit=25)
    recommended = _make_rules(industry_fit=30, member_volume=20)
    profile = _mock_profile()
    report = detect_drift(current, recommended, profile)
    assert isinstance(report.action_items, list)
    assert len(report.action_items) > 0


# ── (f) should_auto_update true only for minor + high confidence ──────────────

def test_should_auto_update_true_for_minor_high_confidence():
    from src.icp_intelligence.drift_detector import detect_drift
    current = _make_rules(industry_fit=25)
    recommended = _make_rules(industry_fit=30, member_volume=20)
    profile = _mock_profile(confidence_level="high")
    report = detect_drift(current, recommended, profile)
    assert report.drift_severity == "minor"
    assert report.should_auto_update is True


# ── (g) should_auto_update false for major drift even with high confidence ────

def test_should_auto_update_false_for_major_high_confidence():
    from src.icp_intelligence.drift_detector import detect_drift
    current = _make_rules(industry_fit=25, member_volume=25, employee_count=15,
                          growth_signal=15, hiring_signal=10, tech_stack_signal=10)
    recommended = _make_rules(industry_fit=35, member_volume=15, employee_count=25,
                               growth_signal=15, hiring_signal=5, tech_stack_signal=5)
    profile = _mock_profile(confidence_level="high")
    report = detect_drift(current, recommended, profile)
    assert report.should_auto_update is False
