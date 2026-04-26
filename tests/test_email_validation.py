import pytest
from src.validation.email_validation_mock import (
    _mock_zerobounce,
    _mock_neverbounce,
    _final_decision,
    validate_contact_email,
    validate_contacts,
    filter_contacts_for_approved_accounts,
)


# ── ZeroBounce ────────────────────────────────────────────────────────────────

def test_valid_email_zerobounce():
    status, reason = _mock_zerobounce("angela.morrison@healthplan.com")
    assert status == "valid"
    assert reason == "deliverable"


def test_invalid_email_zerobounce():
    status, _ = _mock_zerobounce("invalid_user@example.com")
    assert status == "invalid"


def test_risky_email_zerobounce():
    status, _ = _mock_zerobounce("tom.risky@example.com")
    assert status == "risky"


# ── NeverBounce ───────────────────────────────────────────────────────────────

def test_valid_email_neverbounce():
    status, _ = _mock_neverbounce("angela.morrison@healthplan.com")
    assert status == "valid"


def test_invalid_email_neverbounce():
    status, _ = _mock_neverbounce("invalid_user@example.com")
    assert status == "invalid"


def test_risky_email_neverbounce_returns_valid():
    # NeverBounce accepts catch-all addresses that ZeroBounce flags as risky
    status, _ = _mock_neverbounce("tom.risky@example.com")
    assert status == "valid"


# ── Final decision ────────────────────────────────────────────────────────────

def test_final_decision_both_valid_approved():
    status, _ = _final_decision("valid", "valid")
    assert status == "approved"


def test_final_decision_zb_invalid_suppressed():
    status, _ = _final_decision("invalid", "valid")
    assert status == "suppressed"


def test_final_decision_nb_invalid_suppressed():
    status, _ = _final_decision("valid", "invalid")
    assert status == "suppressed"


def test_final_decision_both_invalid_suppressed():
    status, _ = _final_decision("invalid", "invalid")
    assert status == "suppressed"


def test_final_decision_zb_risky_review():
    status, _ = _final_decision("risky", "valid")
    assert status == "review"


def test_final_decision_nb_risky_review():
    status, _ = _final_decision("valid", "risky")
    assert status == "review"


def test_final_decision_invalid_overrides_risky():
    status, _ = _final_decision("invalid", "risky")
    assert status == "suppressed"


# ── validate_contact_email ────────────────────────────────────────────────────

def test_validate_contact_approved():
    contact = {"email": "valid@example.com", "first_name": "A", "last_name": "B"}
    result = validate_contact_email(contact)
    assert result["final_validation_status"] == "approved"
    assert result["zerobounce_status"] == "valid"
    assert result["neverbounce_status"] == "valid"


def test_validate_contact_suppressed():
    contact = {"email": "invalid_user@example.com"}
    result = validate_contact_email(contact)
    assert result["final_validation_status"] == "suppressed"


def test_validate_contact_review():
    contact = {"email": "tom.risky@example.com"}
    result = validate_contact_email(contact)
    assert result["final_validation_status"] == "review"


def test_validate_contacts_list():
    contacts = [
        {"email": "valid@example.com"},
        {"email": "invalid_user@example.com"},
        {"email": "tom.risky@example.com"},
    ]
    results = validate_contacts(contacts)
    assert len(results) == 3
    assert results[0]["final_validation_status"] == "approved"
    assert results[1]["final_validation_status"] == "suppressed"
    assert results[2]["final_validation_status"] == "review"


# ── filter_contacts_for_approved_accounts ────────────────────────────────────

def test_filter_keeps_approved_account_contacts():
    approved = [{"company_id": "C001", "contact_discovery_approved": True}]
    contacts = [
        {"contact_id": "K001", "company_id": "C001"},
        {"contact_id": "K002", "company_id": "C002"},
    ]
    result = filter_contacts_for_approved_accounts(contacts, approved)
    assert len(result) == 1
    assert result[0]["contact_id"] == "K001"


def test_filter_excludes_non_approved_accounts():
    not_approved = [{"company_id": "C003", "contact_discovery_approved": False}]
    contacts = [{"contact_id": "K005", "company_id": "C003"}]
    result = filter_contacts_for_approved_accounts(contacts, not_approved)
    assert len(result) == 0


def test_filter_empty_approved_list():
    contacts = [{"contact_id": "K001", "company_id": "C001"}]
    result = filter_contacts_for_approved_accounts(contacts, [])
    assert len(result) == 0
