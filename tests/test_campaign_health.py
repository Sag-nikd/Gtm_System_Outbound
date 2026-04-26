import pytest
from src.monitoring.campaign_health import evaluate_campaign_health, evaluate_all_campaigns


def _campaign(**kwargs):
    base = {
        "campaign_name": "Test Campaign",
        "bounce_rate": 0.01,
        "open_rate": 0.40,
        "reply_rate": 0.05,
        "spam_rate": 0.001,
        "domain_health_score": 90,
    }
    base.update(kwargs)
    return base


# ── Health status thresholds ──────────────────────────────────────────────────

def test_healthy_campaign():
    result = evaluate_campaign_health(_campaign())
    assert result["health_status"] == "healthy"
    assert result["primary_issue"] == "none"


def test_spam_rate_triggers_critical():
    result = evaluate_campaign_health(_campaign(spam_rate=0.005))
    assert result["health_status"] == "critical"
    assert "spam" in result["primary_issue"]


def test_spam_at_threshold_is_critical():
    result = evaluate_campaign_health(_campaign(spam_rate=0.0031))
    assert result["health_status"] == "critical"


def test_bounce_rate_triggers_warning():
    result = evaluate_campaign_health(_campaign(bounce_rate=0.05))
    assert result["health_status"] == "warning"
    assert "bounce" in result["primary_issue"]


def test_low_domain_score_triggers_warning():
    result = evaluate_campaign_health(_campaign(domain_health_score=60))
    assert result["health_status"] == "warning"
    assert "domain" in result["primary_issue"]


def test_low_open_rate_needs_attention():
    result = evaluate_campaign_health(_campaign(open_rate=0.20))
    assert result["health_status"] == "needs_attention"
    assert "open_rate" in result["primary_issue"]


def test_low_reply_rate_needs_attention():
    result = evaluate_campaign_health(_campaign(reply_rate=0.01))
    assert result["health_status"] == "needs_attention"
    assert "reply_rate" in result["primary_issue"]


# ── Priority ordering ─────────────────────────────────────────────────────────

def test_spam_overrides_bounce():
    result = evaluate_campaign_health(_campaign(spam_rate=0.005, bounce_rate=0.05))
    assert result["health_status"] == "critical"


def test_bounce_overrides_low_open_rate():
    result = evaluate_campaign_health(_campaign(bounce_rate=0.05, open_rate=0.10))
    assert result["health_status"] == "warning"
    assert "bounce" in result["primary_issue"]


# ── Output fields ─────────────────────────────────────────────────────────────

def test_campaign_name_preserved():
    result = evaluate_campaign_health(_campaign(campaign_name="My Campaign"))
    assert result["campaign_name"] == "My Campaign"


def test_recommended_action_populated():
    result = evaluate_campaign_health(_campaign(spam_rate=0.005))
    assert len(result["recommended_action"]) > 0


def test_all_metric_fields_in_output():
    result = evaluate_campaign_health(_campaign())
    for field in ("open_rate", "reply_rate", "bounce_rate", "spam_rate", "domain_health_score"):
        assert field in result


# ── evaluate_all_campaigns ────────────────────────────────────────────────────

def test_evaluate_all_campaigns_returns_all():
    campaigns = [_campaign(), _campaign(spam_rate=0.005)]
    results = evaluate_all_campaigns(campaigns)
    assert len(results) == 2


def test_evaluate_all_campaigns_correct_statuses():
    campaigns = [_campaign(), _campaign(spam_rate=0.005)]
    results = evaluate_all_campaigns(campaigns)
    assert results[0]["health_status"] == "healthy"
    assert results[1]["health_status"] == "critical"


def test_evaluate_empty_list():
    assert evaluate_all_campaigns([]) == []
