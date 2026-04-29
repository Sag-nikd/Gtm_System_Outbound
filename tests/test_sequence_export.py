"""Tests for outreach sequence export — email angles, filtering, LinkedIn templates."""
from __future__ import annotations

import pytest

from src.outreach.sequence_export import (
    create_email_sequence_export,
    create_linkedin_sequence_export,
    EMAIL_ANGLES,
    DEFAULT_ANGLES,
)


def _approved_contact(
    first_name: str = "Alice",
    last_name: str = "Smith",
    email: str = "alice@acme.com",
    persona_type: str = "VP Sales",
    company_name: str = "Acme Corp",
    industry: str = "B2B Technology",
) -> dict:
    return {
        "first_name": first_name,
        "last_name": last_name,
        "email": email,
        "title": persona_type,
        "persona_type": persona_type,
        "company_name": company_name,
        "industry": industry,
        "icp_tier": "Tier 1",
        "final_validation_status": "approved",
        "linkedin_url": f"https://linkedin.com/in/{first_name.lower()}",
    }


def _suppressed_contact(first_name: str = "Bob", email: str = "bob@acme.com", **kwargs) -> dict:
    ct = _approved_contact(first_name=first_name, email=email, **kwargs)
    ct["final_validation_status"] = "suppressed"
    return ct


# ── Email sequence export ─────────────────────────────────────────────────────

def test_email_export_produces_one_row_per_approved_contact():
    contacts = [_approved_contact("Alice"), _approved_contact("Bob", email="bob@acme.com")]
    result = create_email_sequence_export(contacts)
    assert len(result) == 2


def test_email_export_excludes_suppressed_contacts():
    contacts = [
        _approved_contact("Alice"),
        _suppressed_contact("Bob", email="bob@acme.com"),
    ]
    result = create_email_sequence_export(contacts)
    assert len(result) == 1
    assert result[0]["first_name"] == "Alice"


def test_email_export_populates_all_three_angle_fields():
    contacts = [_approved_contact()]
    result = create_email_sequence_export(contacts)
    row = result[0]
    assert "email_step_1_angle" in row and row["email_step_1_angle"]
    assert "email_step_2_angle" in row and row["email_step_2_angle"]
    assert "email_step_3_angle" in row and row["email_step_3_angle"]


def test_email_export_known_persona_uses_correct_angles():
    # Revenue Operations Manager angles have no {tokens}, so direct comparison is safe
    persona = "Revenue Operations Manager"
    contacts = [_approved_contact(persona_type=persona)]
    result = create_email_sequence_export(contacts)
    expected = EMAIL_ANGLES[persona]
    assert result[0]["email_step_1_angle"] == expected[0]
    assert result[0]["email_step_2_angle"] == expected[1]
    assert result[0]["email_step_3_angle"] == expected[2]


def test_email_export_unknown_persona_falls_back_to_defaults():
    contacts = [_approved_contact(persona_type="Unknown Persona XYZ")]
    result = create_email_sequence_export(contacts)
    # DEFAULT_ANGLES[1] and [2] have no tokens, so formatted output equals raw template
    assert result[0]["email_step_1_angle"]
    assert result[0]["email_step_2_angle"] == DEFAULT_ANGLES[1]
    assert result[0]["email_step_3_angle"] == DEFAULT_ANGLES[2]


def test_email_export_empty_input_returns_empty_list():
    assert create_email_sequence_export([]) == []


def test_email_export_all_suppressed_returns_empty_list():
    contacts = [_suppressed_contact(), _suppressed_contact(email="b@b.com")]
    assert create_email_sequence_export(contacts) == []


# ── LinkedIn sequence export ──────────────────────────────────────────────────

def test_linkedin_export_approved_contact_has_connection_message_with_first_name():
    contacts = [_approved_contact("Charlie")]
    result = create_linkedin_sequence_export(contacts)
    assert len(result) == 1
    assert "Charlie" in result[0]["connection_message"]


def test_linkedin_export_excludes_suppressed_contacts():
    contacts = [
        _approved_contact("Alice"),
        _suppressed_contact("Bob", email="bob@acme.com"),
    ]
    result = create_linkedin_sequence_export(contacts)
    assert len(result) == 1
    assert result[0]["first_name"] == "Alice"


def test_linkedin_export_empty_approved_list_returns_empty():
    contacts = [_suppressed_contact()]
    result = create_linkedin_sequence_export(contacts)
    assert result == []


def test_linkedin_export_row_has_required_fields():
    contacts = [_approved_contact("Dana")]
    result = create_linkedin_sequence_export(contacts)
    row = result[0]
    for field in ["first_name", "last_name", "linkedin_url", "connection_message",
                  "followup_message_1", "followup_message_2", "campaign_name"]:
        assert field in row, f"Missing field: {field}"
