"""Story 2: ICP Profile Analyzer — conversion pattern detection tests."""
from __future__ import annotations

import os
import pytest

from src.config.settings import settings


def _load_mock_deals():
    from src.icp_intelligence.data_ingestion import load_deal_data
    path = os.path.join(settings.DATA_DIR, "icp_intelligence", "mock_deal_history.json")
    return load_deal_data(path)


# ── (a) Full profile from mock deals ──────────────────────────────────────────

def test_analyze_icp_returns_profile_with_all_breakdowns():
    from src.icp_intelligence.profile_analyzer import analyze_icp
    deals = _load_mock_deals()
    profile = analyze_icp(deals)
    assert profile.total_deals_analyzed == len(deals)
    assert isinstance(profile.industry_breakdown, list) and len(profile.industry_breakdown) > 0
    assert isinstance(profile.employee_size_breakdown, list)
    assert isinstance(profile.geo_breakdown, list)
    assert isinstance(profile.loss_reasons, list)
    assert isinstance(profile.icp_summary, str) and profile.icp_summary


# ── (b) Conversion rate matches manual calculation ────────────────────────────

def test_analyze_icp_conversion_rate_matches_manual():
    from src.icp_intelligence.profile_analyzer import analyze_icp
    deals = [
        {"company_name": "A", "industry": "Managed Care", "employee_count": 1000, "deal_stage": "closed_won", "domain": "a.com"},
        {"company_name": "B", "industry": "Managed Care", "employee_count": 1000, "deal_stage": "closed_won", "domain": "b.com"},
        {"company_name": "C", "industry": "Managed Care", "employee_count": 1000, "deal_stage": "closed_lost", "domain": "c.com"},
        {"company_name": "D", "industry": "Managed Care", "employee_count": 1000, "deal_stage": "disqualified", "domain": "d.com"},
        {"company_name": "E", "industry": "Managed Care", "employee_count": 1000, "deal_stage": "proposal_sent", "domain": "e.com"},
    ]
    profile = analyze_icp(deals)
    # 2 won / (2 won + 1 lost + 1 disq) = 0.5
    assert abs(profile.conversion_rate - 0.5) < 0.001


# ── (c) industry_breakdown sorted by index descending ────────────────────────

def test_industry_breakdown_sorted_by_index_descending():
    from src.icp_intelligence.profile_analyzer import analyze_icp
    deals = _load_mock_deals()
    profile = analyze_icp(deals)
    indexes = [seg.index for seg in profile.industry_breakdown]
    assert indexes == sorted(indexes, reverse=True)


# ── (d) Industry with 0 wins → conversion_rate=0.0, index=0.0 ────────────────

def test_industry_with_no_wins_has_zero_conversion_and_index():
    from src.icp_intelligence.profile_analyzer import analyze_icp
    deals = [
        {"company_name": "WonCo", "industry": "Managed Care", "employee_count": 1000, "deal_stage": "closed_won", "domain": "wonco.com"},
        {"company_name": "LostCo", "industry": "Financial Services", "employee_count": 200, "deal_stage": "closed_lost", "domain": "lostco.com", "loss_reason": "budget"},
    ]
    profile = analyze_icp(deals)
    fs_seg = next((s for s in profile.industry_breakdown if s.name == "Financial Services"), None)
    assert fs_seg is not None
    assert fs_seg.conversion_rate == 0.0
    assert fs_seg.index == 0.0


# ── (e) confidence_level medium for 10–30 deals ──────────────────────────────

def test_confidence_level_medium_for_10_to_30_deals():
    from src.icp_intelligence.profile_analyzer import analyze_icp
    deals = _load_mock_deals()
    assert 10 <= len(deals) <= 30
    profile = analyze_icp(deals)
    assert profile.confidence_level == "medium"


# ── (f) confidence_level low for <10 deals ───────────────────────────────────

def test_confidence_level_low_for_few_deals():
    from src.icp_intelligence.profile_analyzer import analyze_icp
    deals = [
        {"company_name": f"Co{i}", "industry": "Managed Care", "employee_count": 500,
         "deal_stage": "closed_won", "domain": f"co{i}.com"}
        for i in range(5)
    ]
    profile = analyze_icp(deals)
    assert profile.confidence_level == "low"


# ── (g) No deal_value → avg_deal_value=0.0, no crash ─────────────────────────

def test_avg_deal_value_zero_when_no_values():
    from src.icp_intelligence.profile_analyzer import analyze_icp
    deals = [
        {"company_name": "A", "industry": "Managed Care", "employee_count": 1000, "deal_stage": "closed_won", "domain": "a.com"},
        {"company_name": "B", "industry": "Managed Care", "employee_count": 1000, "deal_stage": "closed_won", "domain": "b.com"},
    ]
    profile = analyze_icp(deals)
    assert profile.avg_deal_value == 0.0


# ── (h) No primary_volume_metric → volume_breakdown is empty ───────────────

def test_volume_breakdown_empty_when_no_member_data():
    from src.icp_intelligence.profile_analyzer import analyze_icp
    deals = [
        {"company_name": "A", "industry": "Managed Care", "employee_count": 1000, "deal_stage": "closed_won", "domain": "a.com"},
    ]
    profile = analyze_icp(deals)
    assert profile.volume_breakdown == []


# ── (i) icp_summary mentions top industry name ────────────────────────────────

def test_icp_summary_mentions_top_industry():
    from src.icp_intelligence.profile_analyzer import analyze_icp
    deals = _load_mock_deals()
    profile = analyze_icp(deals)
    top_industry = profile.industry_breakdown[0].name
    assert top_industry in profile.icp_summary


# ── (j) loss_reasons aggregated correctly ─────────────────────────────────────

def test_loss_reasons_aggregated():
    from src.icp_intelligence.profile_analyzer import analyze_icp
    deals = [
        {"company_name": "A", "industry": "Managed Care", "employee_count": 1000, "deal_stage": "closed_won", "domain": "a.com"},
        {"company_name": "B", "industry": "Financial", "employee_count": 200, "deal_stage": "closed_lost", "domain": "b.com", "loss_reason": "budget"},
        {"company_name": "C", "industry": "Financial", "employee_count": 200, "deal_stage": "closed_lost", "domain": "c.com", "loss_reason": "budget"},
        {"company_name": "D", "industry": "Retail", "employee_count": 50, "deal_stage": "closed_lost", "domain": "d.com", "loss_reason": "not_our_market"},
    ]
    profile = analyze_icp(deals)
    budget_reason = next((r for r in profile.loss_reasons if r.reason == "budget"), None)
    assert budget_reason is not None
    assert budget_reason.count == 2
