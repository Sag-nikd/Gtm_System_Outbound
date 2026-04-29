"""Tests for cost tracker decorator and VendorCallService."""
from __future__ import annotations

import pytest

from src.cost.tracker import VendorCallService, _compute_dollar_cost


def test_compute_dollar_cost_zerobounce() -> None:
    cost = _compute_dollar_cost("zerobounce", "validate_email", 100.0)
    assert cost == pytest.approx(0.8, abs=1e-4)


def test_compute_dollar_cost_unknown_vendor() -> None:
    cost = _compute_dollar_cost("unknown_vendor", "some_endpoint", 10.0)
    assert cost is None


def test_compute_dollar_cost_no_units() -> None:
    cost = _compute_dollar_cost("zerobounce", "validate_email", None)
    assert cost is None


def test_forecast_returns_dict() -> None:
    result = VendorCallService.forecast(1000)
    assert "zerobounce_validation" in result
    assert "total_estimated_usd" in result
    assert result["zerobounce_validation"] == pytest.approx(8.0, abs=0.01)


def test_forecast_scales_linearly() -> None:
    r1 = VendorCallService.forecast(1000)
    r2 = VendorCallService.forecast(2000)
    assert r2["total_estimated_usd"] == pytest.approx(r1["total_estimated_usd"] * 2, abs=0.01)
