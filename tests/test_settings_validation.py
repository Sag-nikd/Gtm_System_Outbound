"""Tests that Settings.validate() raises EnvironmentError in live mode when keys are missing."""
from __future__ import annotations

import pytest


def _make_settings(monkeypatch, mock_mode: bool, extra_keys: dict = None):
    """Instantiate a fresh Settings object with controlled env vars."""
    from src.config.settings import Settings

    monkeypatch.setenv("MOCK_MODE", "true" if mock_mode else "false")
    monkeypatch.setenv("APOLLO_API_KEY", "")
    monkeypatch.setenv("CLAY_API_KEY", "")
    monkeypatch.setenv("HUBSPOT_PRIVATE_APP_TOKEN", "")
    monkeypatch.setenv("ZEROBOUNCE_API_KEY", "")
    monkeypatch.setenv("NEVERBOUNCE_API_KEY", "")
    monkeypatch.setenv("VALIDITY_API_KEY", "")

    for k, v in (extra_keys or {}).items():
        monkeypatch.setenv(k, v)

    return Settings()


def test_mock_mode_with_empty_keys_no_error(monkeypatch):
    """Mock mode never raises even if all API keys are empty."""
    _make_settings(monkeypatch, mock_mode=True)  # must not raise


def test_live_mode_all_keys_set_no_error(monkeypatch):
    """Live mode with all keys present does not raise."""
    _make_settings(monkeypatch, mock_mode=False, extra_keys={
        "APOLLO_API_KEY": "key1",
        "CLAY_API_KEY": "key2",
        "HUBSPOT_PRIVATE_APP_TOKEN": "token3",
        "ZEROBOUNCE_API_KEY": "key4",
        "NEVERBOUNCE_API_KEY": "key5",
        "VALIDITY_API_KEY": "key6",
    })  # must not raise


def test_live_mode_missing_keys_raises_environment_error(monkeypatch):
    """Live mode with any missing key raises EnvironmentError."""
    with pytest.raises(EnvironmentError):
        _make_settings(monkeypatch, mock_mode=False, extra_keys={
            "APOLLO_API_KEY": "key1",
            # rest are empty
        })


def test_live_mode_error_message_lists_missing_keys(monkeypatch):
    """Error message names every missing key."""
    with pytest.raises(EnvironmentError) as exc_info:
        _make_settings(monkeypatch, mock_mode=False, extra_keys={
            "APOLLO_API_KEY": "key1",
            "CLAY_API_KEY": "key2",
            # HUBSPOT, ZEROBOUNCE, NEVERBOUNCE, VALIDITY missing
        })
    msg = str(exc_info.value)
    assert "HUBSPOT_PRIVATE_APP_TOKEN" in msg
    assert "ZEROBOUNCE_API_KEY" in msg
    assert "NEVERBOUNCE_API_KEY" in msg
    assert "VALIDITY_API_KEY" in msg
    assert "APOLLO_API_KEY" not in msg
    assert "CLAY_API_KEY" not in msg
