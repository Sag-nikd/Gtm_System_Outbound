"""Story 4: Apollo Query Builder tests."""
from __future__ import annotations

import json
import os

import pytest

from src.config.settings import settings


def _get_profile_and_rules():
    from src.icp_intelligence.data_ingestion import load_deal_data
    from src.icp_intelligence.profile_analyzer import analyze_icp
    from src.icp_intelligence.rules_generator import generate_icp_rules
    path = os.path.join(settings.DATA_DIR, "icp_intelligence", "mock_deal_history.json")
    deals = load_deal_data(path)
    profile = analyze_icp(deals)
    rules = generate_icp_rules(profile)
    return profile, rules, deals


# ── (a) organization_search has industry_keywords ────────────────────────────

def test_build_query_industry_keywords_populated():
    from src.icp_intelligence.apollo_query_builder import build_apollo_query
    profile, rules, _ = _get_profile_and_rules()
    config = build_apollo_query(profile, rules)
    assert isinstance(config.organization_search["industry_keywords"], list)
    assert len(config.organization_search["industry_keywords"]) > 0


# ── (b) employee_ranges min < max ────────────────────────────────────────────

def test_build_query_employee_ranges_valid():
    from src.icp_intelligence.apollo_query_builder import build_apollo_query
    profile, rules, _ = _get_profile_and_rules()
    config = build_apollo_query(profile, rules)
    for rng in config.organization_search["employee_ranges"]:
        assert rng["min"] < rng["max"], f"Invalid range: {rng}"


# ── (c) Closed-won customer domains in exclusions ────────────────────────────

def test_closed_won_domains_in_exclusions():
    from src.icp_intelligence.apollo_query_builder import build_apollo_query
    from src.icp_intelligence.data_ingestion import load_deal_data
    from src.icp_intelligence.profile_analyzer import analyze_icp
    from src.icp_intelligence.rules_generator import generate_icp_rules
    deals = [
        {"company_name": "Won Co", "domain": "wonco.com", "industry": "Managed Care",
         "employee_count": 1000, "deal_stage": "closed_won"},
        {"company_name": "Lost Co", "domain": "lostco.com", "industry": "Financial Services",
         "employee_count": 200, "deal_stage": "closed_lost", "loss_reason": "not_our_market"},
    ]
    profile = analyze_icp(deals)
    rules = generate_icp_rules(profile)
    config = build_apollo_query(profile, rules, deals=deals)
    assert "wonco.com" in config.exclusions["domains"]
    assert "lostco.com" not in config.exclusions["domains"]


# ── (d) 0% conversion industry with >3 attempts in exclusions ────────────────

def test_zero_conversion_industry_excluded():
    from src.icp_intelligence.apollo_query_builder import build_apollo_query
    from src.icp_intelligence.profile_analyzer import analyze_icp
    from src.icp_intelligence.rules_generator import generate_icp_rules
    lost_deals = [
        {"company_name": "F{}".format(i), "industry": "Financial Services", "employee_count": 200,
         "deal_stage": "closed_lost", "domain": "f{}.com".format(i), "loss_reason": "not_our_market"}
        for i in range(4)
    ]
    deals = [{"company_name": "W1", "industry": "Managed Care", "employee_count": 1000,
              "deal_stage": "closed_won", "domain": "w1.com"}] + lost_deals
    profile = analyze_icp(deals)
    rules = generate_icp_rules(profile)
    config = build_apollo_query(profile, rules, deals=deals)
    assert "Financial Services" in config.exclusions["industries"]


# ── (e) persona_titles non-empty ─────────────────────────────────────────────

def test_persona_titles_non_empty():
    from src.icp_intelligence.apollo_query_builder import build_apollo_query
    profile, rules, _ = _get_profile_and_rules()
    config = build_apollo_query(profile, rules)
    assert isinstance(config.contact_search["persona_titles"], list)
    assert len(config.contact_search["persona_titles"]) > 0


# ── (f) query_rationale non-empty and mentions top industry ──────────────────

def test_query_rationale_mentions_top_industry():
    from src.icp_intelligence.apollo_query_builder import build_apollo_query
    profile, rules, _ = _get_profile_and_rules()
    config = build_apollo_query(profile, rules)
    assert isinstance(config.query_rationale, str)
    assert len(config.query_rationale) > 0
    top_industry = profile.industry_breakdown[0].name
    assert top_industry in config.query_rationale


# ── (g) No geo data → location_states empty ──────────────────────────────────

def test_no_geo_data_empty_location_states():
    from src.icp_intelligence.apollo_query_builder import build_apollo_query
    from src.icp_intelligence.profile_analyzer import analyze_icp
    from src.icp_intelligence.rules_generator import generate_icp_rules
    deals = [
        {"company_name": "A", "industry": "Managed Care", "employee_count": 1000,
         "deal_stage": "closed_won", "domain": "a.com"},
    ]
    profile = analyze_icp(deals)
    assert profile.geo_breakdown == []
    rules = generate_icp_rules(profile)
    config = build_apollo_query(profile, rules, deals=deals)
    assert config.organization_search["location_states"] == []


# ── (h) No tech stack → technology_names empty ───────────────────────────────

def test_no_tech_stack_data_empty_technology_names():
    from src.icp_intelligence.apollo_query_builder import build_apollo_query
    from src.icp_intelligence.profile_analyzer import analyze_icp
    from src.icp_intelligence.rules_generator import generate_icp_rules
    deals = [
        {"company_name": "A", "industry": "Managed Care", "employee_count": 1000,
         "deal_stage": "closed_won", "domain": "a.com"},
    ]
    profile = analyze_icp(deals)
    rules = generate_icp_rules(profile)
    # Patch tech_stack_scores to empty full list
    rules["tech_stack_scores"]["full"] = []
    config = build_apollo_query(profile, rules, deals=deals)
    assert config.organization_search["technology_names"] == []
