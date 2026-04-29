"""
API key validator — lightweight smoke tests for each integration.
Each validator makes the cheapest possible authenticated request to confirm the
key is valid without consuming quota or triggering side effects.
"""
from __future__ import annotations

from typing import Tuple

import requests


def validate_key(provider: str, key: str) -> Tuple[bool, str]:
    """
    Test an API key for the given provider.
    Returns (is_valid, message).
    """
    if not key or not key.strip():
        return False, "Key is empty"

    validator = _VALIDATORS.get(provider.lower())
    if validator is None:
        return False, f"No validator registered for provider '{provider}'"

    try:
        return validator(key.strip())
    except requests.Timeout:
        return False, "Request timed out — check your network connection"
    except requests.ConnectionError:
        return False, "Connection error — check your network connection"
    except requests.RequestException as exc:
        return False, f"Request failed: {exc}"


# ── Provider validators ───────────────────────────────────────────────────────

def _validate_apollo(key: str) -> Tuple[bool, str]:
    resp = requests.post(
        "https://api.apollo.io/v1/auth/health",
        json={"api_key": key},
        timeout=10,
    )
    if resp.status_code == 200:
        return True, "Apollo key is valid"
    if resp.status_code == 401:
        return False, "Apollo key is invalid (401 Unauthorized)"
    return False, f"Apollo returned unexpected status {resp.status_code}"


def _validate_clay(key: str) -> Tuple[bool, str]:
    resp = requests.get(
        "https://api.clay.com/v1/tables",
        headers={"Authorization": f"Bearer {key}"},
        timeout=10,
    )
    if resp.status_code in (200, 404):
        return True, "Clay key is valid"
    if resp.status_code == 401:
        return False, "Clay key is invalid (401 Unauthorized)"
    return False, f"Clay returned unexpected status {resp.status_code}"


def _validate_hubspot(key: str) -> Tuple[bool, str]:
    resp = requests.get(
        "https://api.hubapi.com/crm/v3/objects/contacts?limit=1",
        headers={"Authorization": f"Bearer {key}"},
        timeout=10,
    )
    if resp.status_code == 200:
        return True, "HubSpot token is valid"
    if resp.status_code == 401:
        return False, "HubSpot token is invalid (401 Unauthorized)"
    if resp.status_code == 403:
        return False, "HubSpot token lacks required scopes (403 Forbidden)"
    return False, f"HubSpot returned unexpected status {resp.status_code}"


def _validate_zerobounce(key: str) -> Tuple[bool, str]:
    resp = requests.get(
        "https://api.zerobounce.net/v2/getcredits",
        params={"api_key": key},
        timeout=10,
    )
    if resp.status_code == 200:
        data = resp.json()
        credits = data.get("Credits", -1)
        if credits == -1:
            return False, "ZeroBounce key is invalid (returned -1 credits)"
        return True, f"ZeroBounce key is valid ({credits} credits remaining)"
    return False, f"ZeroBounce returned unexpected status {resp.status_code}"


def _validate_neverbounce(key: str) -> Tuple[bool, str]:
    resp = requests.get(
        "https://api.neverbounce.com/v4/account/info",
        params={"key": key},
        timeout=10,
    )
    if resp.status_code == 200:
        data = resp.json()
        if data.get("status") == "success":
            return True, "NeverBounce key is valid"
        return False, f"NeverBounce error: {data.get('message', 'unknown')}"
    if resp.status_code == 401:
        return False, "NeverBounce key is invalid (401 Unauthorized)"
    return False, f"NeverBounce returned unexpected status {resp.status_code}"


def _validate_validity(key: str) -> Tuple[bool, str]:
    resp = requests.get(
        "https://api.senderscore.com/v1/campaigns",
        headers={"Authorization": f"Bearer {key}"},
        timeout=10,
    )
    if resp.status_code in (200, 404):
        return True, "Validity key is valid"
    if resp.status_code == 401:
        return False, "Validity key is invalid (401 Unauthorized)"
    return False, f"Validity returned unexpected status {resp.status_code}"


_VALIDATORS = {
    "apollo": _validate_apollo,
    "clay": _validate_clay,
    "hubspot": _validate_hubspot,
    "zerobounce": _validate_zerobounce,
    "neverbounce": _validate_neverbounce,
    "validity": _validate_validity,
}
