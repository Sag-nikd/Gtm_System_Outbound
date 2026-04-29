import pytest
from src.scoring.icp_scoring import score_company, score_companies, _assign_tier


def test_tier1_managed_care_high_volume(icp_rules, managed_care_company):
    result = score_company(managed_care_company, icp_rules)
    assert result["icp_tier"] == "Tier 1"
    assert result["icp_score"] == 100.0


def test_disqualified_retail(icp_rules, retail_company):
    result = score_company(retail_company, icp_rules)
    assert result["icp_tier"] == "Disqualified"
    assert result["icp_score"] == 0.0


def test_growth_signal_adds_15_points(icp_rules, managed_care_company):
    managed_care_company["growth_signal"] = False
    result_no = score_company({**managed_care_company}, icp_rules)
    managed_care_company["growth_signal"] = True
    result_yes = score_company({**managed_care_company}, icp_rules)
    assert result_yes["growth_signal_score"] == 15.0
    assert result_no["growth_signal_score"] == 0.0


def test_hiring_signal_adds_10_points(icp_rules, managed_care_company):
    managed_care_company["hiring_signal"] = False
    result = score_company(managed_care_company, icp_rules)
    assert result["hiring_signal_score"] == 0.0


def test_total_volume_calculated(icp_rules, managed_care_company):
    result = score_company(managed_care_company, icp_rules)
    assert result["total_volume"] == 900_000


def test_tech_stack_full_points(icp_rules, managed_care_company):
    managed_care_company["tech_stack_signal"] = "Salesforce"
    result = score_company(managed_care_company, icp_rules)
    assert result["tech_stack_score"] == 10.0


def test_tech_stack_no_points(icp_rules, managed_care_company):
    managed_care_company["tech_stack_signal"] = "Unknown"
    result = score_company(managed_care_company, icp_rules)
    assert result["tech_stack_score"] == 0.0


def test_tech_stack_partial_points(icp_rules, managed_care_company):
    managed_care_company["tech_stack_signal"] = "Zendesk"
    result = score_company(managed_care_company, icp_rules)
    assert result["tech_stack_score"] == 5.0


def test_assign_tier_boundaries(icp_rules):
    assert _assign_tier(100, icp_rules) == "Tier 1"
    assert _assign_tier(80, icp_rules) == "Tier 1"
    assert _assign_tier(79, icp_rules) == "Tier 2"
    assert _assign_tier(60, icp_rules) == "Tier 2"
    assert _assign_tier(59, icp_rules) == "Tier 3"
    assert _assign_tier(40, icp_rules) == "Tier 3"
    assert _assign_tier(39, icp_rules) == "Disqualified"
    assert _assign_tier(0,  icp_rules) == "Disqualified"


def test_score_companies_processes_list(icp_rules, managed_care_company, retail_company):
    results = score_companies([managed_care_company, retail_company], icp_rules)
    assert len(results) == 2
    assert results[0]["icp_tier"] == "Tier 1"
    assert results[1]["icp_tier"] == "Disqualified"


def test_score_reason_populated(icp_rules, managed_care_company):
    result = score_company(managed_care_company, icp_rules)
    assert "industry=" in result["score_reason"]
    assert "total_volume=" in result["score_reason"]


def test_tier_reason_populated(icp_rules, managed_care_company):
    result = score_company(managed_care_company, icp_rules)
    assert "Tier 1" in result["tier_reason"]


def test_mid_volume_metric_tier2(icp_rules):
    # Managed Care(25) + mid volume 300k(17.5) + mid employees 500(10.5) + growth(15) = 68 -> Tier 2
    company = {
        "company_id": "C002",
        "industry": "Managed Care",
        "employee_count": 500,
        "primary_volume_metric": 300_000,
        "secondary_volume_metric": 0,
        "growth_signal": True,
        "hiring_signal": False,
        "tech_stack_signal": "Unknown",
    }
    result = score_company(company, icp_rules)
    assert result["icp_tier"] == "Tier 2"
