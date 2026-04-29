"""Story 3: ICP Rules Generator tests."""
from __future__ import annotations

import json
import os

import pytest

from src.config.settings import settings


def _make_profile(industries=None, won_employee_counts=None, won_tech_stacks=None,
                  lost_tech_stacks=None, won_member_volumes=None):
    """Build a minimal ICPProfile for testing rules generation."""
    from src.icp_intelligence.data_ingestion import load_deal_data
    from src.icp_intelligence.profile_analyzer import analyze_icp

    path = os.path.join(settings.DATA_DIR, "icp_intelligence", "mock_deal_history.json")
    deals = load_deal_data(path)
    return analyze_icp(deals)


def _make_simple_profile():
    """Controlled profile: 2 Managed Care wins, 1 Financial Services loss."""
    from src.icp_intelligence.profile_analyzer import analyze_icp
    deals = [
        {"company_name": "A", "industry": "Managed Care", "employee_count": 2000, "deal_stage": "closed_won",
         "domain": "a.com", "deal_value": 100000, "tech_stack": "Salesforce",
         "medicaid_members": 500000, "medicare_members": 50000},
        {"company_name": "B", "industry": "Managed Care", "employee_count": 1500, "deal_stage": "closed_won",
         "domain": "b.com", "deal_value": 120000, "tech_stack": "HubSpot",
         "medicaid_members": 300000, "medicare_members": 30000},
        {"company_name": "C", "industry": "Financial Services", "employee_count": 200, "deal_stage": "closed_lost",
         "domain": "c.com", "loss_reason": "not_our_market", "tech_stack": "Unknown",
         "medicaid_members": 0, "medicare_members": 0},
    ]
    return analyze_icp(deals)


# ── (a) Output has all required keys ──────────────────────────────────────────

def test_generate_rules_has_all_required_keys():
    from src.icp_intelligence.rules_generator import generate_icp_rules
    profile = _make_profile()
    rules = generate_icp_rules(profile)
    for key in ("weights", "tiers", "industry_scores",
                 "member_volume_thresholds", "employee_count_thresholds", "tech_stack_scores"):
        assert key in rules, f"Missing key: {key}"


# ── (b) Weights sum to 100 ────────────────────────────────────────────────────

def test_generate_rules_weights_sum_to_100():
    from src.icp_intelligence.rules_generator import generate_icp_rules
    profile = _make_profile()
    rules = generate_icp_rules(profile)
    total = sum(rules["weights"].values())
    assert abs(total - 100) < 0.01, f"Weights sum to {total}, expected 100"


# ── (c) Top-index industry gets score 1.0 ────────────────────────────────────

def test_top_industry_gets_score_1_0():
    from src.icp_intelligence.rules_generator import generate_icp_rules
    profile = _make_simple_profile()
    rules = generate_icp_rules(profile)
    top_industry = profile.industry_breakdown[0].name
    assert rules["industry_scores"][top_industry] == 1.0


# ── (d) Industry not in deal data gets score 0.0 ─────────────────────────────

def test_unknown_industry_gets_default_score_0():
    from src.icp_intelligence.rules_generator import generate_icp_rules
    profile = _make_simple_profile()
    rules = generate_icp_rules(profile)
    assert rules["industry_scores"].get("default", 0.0) == 0.0


# ── (e) member_volume_thresholds high >= mid >= low ──────────────────────────

def test_member_volume_thresholds_ordered():
    from src.icp_intelligence.rules_generator import generate_icp_rules
    profile = _make_profile()
    rules = generate_icp_rules(profile)
    thresholds = rules["member_volume_thresholds"]
    assert thresholds["high"]["min"] >= thresholds["mid"]["min"] >= thresholds["low"]["min"]


# ── (f) Closed-won tech stack in "full" list ─────────────────────────────────

def test_won_tech_stack_in_full_list():
    from src.icp_intelligence.rules_generator import generate_icp_rules
    profile = _make_simple_profile()
    rules = generate_icp_rules(profile)
    # Salesforce and HubSpot are in closed_won deals
    full_list = rules["tech_stack_scores"]["full"]
    assert "Salesforce" in full_list


# ── (g) Generated rules loadable by load_icp_rules ───────────────────────────

def test_generated_rules_loadable_by_load_icp_rules(tmp_path):
    from src.icp_intelligence.rules_generator import generate_icp_rules, save_icp_rules
    from src.scoring.icp_scoring import load_icp_rules
    profile = _make_profile()
    rules = generate_icp_rules(profile)
    path = str(tmp_path / "icp_rules.json")
    save_icp_rules(rules, path)
    loaded = load_icp_rules(path)
    assert "weights" in loaded


# ── (h) Generated rules can be fed to score_company without error ─────────────

def test_generated_rules_work_with_score_company(tmp_path):
    from src.icp_intelligence.rules_generator import generate_icp_rules, save_icp_rules
    from src.scoring.icp_scoring import load_icp_rules, score_company
    profile = _make_profile()
    rules = generate_icp_rules(profile)
    path = str(tmp_path / "icp_rules.json")
    save_icp_rules(rules, path)
    loaded = load_icp_rules(path)
    company = {
        "company_id": "T001", "company_name": "Test Co", "industry": "Managed Care",
        "employee_count": 1000, "medicaid_members": 300000, "medicare_members": 50000,
        "growth_signal": True, "hiring_signal": True, "tech_stack_signal": "Salesforce",
    }
    result = score_company(company, loaded)
    assert "icp_score" in result
    assert "icp_tier" in result


# ── (i) save_icp_rules_with_history creates current + timestamped copy ────────

def test_save_icp_rules_with_history_creates_both_files(tmp_path):
    from src.icp_intelligence.rules_generator import generate_icp_rules, save_icp_rules_with_history
    import os
    profile = _make_profile()
    rules = generate_icp_rules(profile)
    save_icp_rules_with_history(rules, str(tmp_path))
    assert os.path.exists(str(tmp_path / "icp_rules.json"))
    history_dir = tmp_path / "icp_history"
    assert history_dir.exists()
    history_files = list(history_dir.glob("icp_rules_*.json"))
    assert len(history_files) == 1


# ── (j) No member data → member_volume weight=0, others sum to 100 ───────────

def test_no_member_data_weight_redistributed():
    from src.icp_intelligence.rules_generator import generate_icp_rules
    from src.icp_intelligence.profile_analyzer import analyze_icp
    deals = [
        {"company_name": "A", "industry": "Managed Care", "employee_count": 1000,
         "deal_stage": "closed_won", "domain": "a.com"},
    ]
    profile = analyze_icp(deals)
    assert profile.member_volume_breakdown == []
    rules = generate_icp_rules(profile)
    assert rules["weights"].get("member_volume", 0) == 0
    total = sum(rules["weights"].values())
    assert abs(total - 100) < 0.01
