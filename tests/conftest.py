import pytest


@pytest.fixture
def icp_rules():
    return {
        "weights": {
            "industry_fit": 25,
            "volume_metric": 25,
            "employee_count": 15,
            "growth_signal": 15,
            "hiring_signal": 10,
            "tech_stack_signal": 10,
        },
        "tiers": {
            "tier_1": {"min": 80, "max": 100, "label": "Tier 1"},
            "tier_2": {"min": 60, "max": 79,  "label": "Tier 2"},
            "tier_3": {"min": 40, "max": 59,  "label": "Tier 3"},
            "disqualified": {"min": 0, "max": 39, "label": "Disqualified"},
        },
        "industry_scores": {
            "Managed Care": 1.0,
            "Health Plan": 1.0,
            "Healthcare Technology": 0.6,
            "Provider": 0.6,
            "default": 0.0,
        },
        "volume_thresholds": {
            "high": {"min": 750000, "multiplier": 1.0},
            "mid":  {"min": 250000, "multiplier": 0.7},
            "low":  {"min": 50000,  "multiplier": 0.4},
            "none": {"min": 0,      "multiplier": 0.0},
        },
        "employee_count_thresholds": {
            "high": {"min": 1000, "multiplier": 1.0},
            "mid":  {"min": 250,  "multiplier": 0.7},
            "low":  {"min": 100,  "multiplier": 0.4},
            "none": {"min": 0,    "multiplier": 0.0},
        },
        "tech_stack_scores": {
            "full": ["Salesforce", "Microsoft Dynamics 365", "HubSpot", "Twilio"],
            "partial_multiplier": 0.5,
            "none": ["Unknown"],
        },
    }


@pytest.fixture
def managed_care_company():
    return {
        "company_id": "C001",
        "company_name": "Test Health Plan",
        "industry": "Managed Care",
        "employee_count": 5000,
        "primary_volume_metric": 800000,
        "secondary_volume_metric": 100000,
        "growth_signal": True,
        "hiring_signal": True,
        "tech_stack_signal": "Salesforce",
    }


@pytest.fixture
def retail_company():
    return {
        "company_id": "C099",
        "company_name": "Test Retail",
        "industry": "Retail",
        "employee_count": 50,
        "primary_volume_metric": 0,
        "secondary_volume_metric": 0,
        "growth_signal": False,
        "hiring_signal": False,
        "tech_stack_signal": "Unknown",
    }
