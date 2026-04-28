"""
Email validation mock module — simulates ZeroBounce and NeverBounce two-step validation.
# Future: Replace zerobounce_status with real ZeroBounce API response.
# Future: Replace neverbounce_status with real NeverBounce API response.
"""

from __future__ import annotations
import json

from pydantic import ValidationError

from src.schemas.contact import Contact
from src.utils.logger import get_logger

log = get_logger(__name__)


def load_contacts(file_path: str) -> list[dict]:
    with open(file_path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    contacts = []
    seen_emails: set = set()
    for record in raw:
        try:
            Contact(**record)
        except ValidationError as exc:
            log.warning(
                "Skipping contact %s: schema validation failed — %s",
                record.get("contact_id", "?"), exc.error_count()
            )
            continue
        email = record.get("email", "")
        if email and email in seen_emails:
            log.warning("Skipping duplicate email '%s'", email)
            continue
        if email:
            seen_emails.add(email)
        contacts.append(record)
    return contacts


def filter_contacts_for_approved_accounts(
    contacts: list[dict], approved_companies: list[dict]
) -> list[dict]:
    approved_ids = {c["company_id"] for c in approved_companies if c.get("contact_discovery_approved")}
    return [c for c in contacts if c.get("company_id") in approved_ids]


def _mock_zerobounce(email: str) -> tuple[str, str]:
    # Future: Replace with real ZeroBounce API response.
    email_lower = email.lower()
    if "invalid" in email_lower:
        return "invalid", "mailbox does not exist"
    if "risky" in email_lower:
        return "risky", "catch-all domain detected"
    return "valid", "deliverable"


def _mock_neverbounce(email: str) -> tuple[str, str]:
    # Future: Replace with real NeverBounce API response.
    email_lower = email.lower()
    if "invalid" in email_lower:
        return "invalid", "undeliverable address"
    if "risky" in email_lower:
        return "valid", "accepted but unverifiable"
    return "valid", "verified deliverable"


def _final_decision(zb_status: str, nb_status: str) -> tuple[str, str]:
    if zb_status == "invalid" or nb_status == "invalid":
        return "suppressed", "one or both validators returned invalid"
    if zb_status == "risky" or nb_status == "risky":
        return "review", "one validator flagged as risky"
    return "approved", "both validators confirmed valid"


def validate_contact_email(contact: dict) -> dict:
    email = contact.get("email", "")

    zb_status, zb_reason = _mock_zerobounce(email)
    nb_status, nb_reason = _mock_neverbounce(email)
    final_status, final_reason = _final_decision(zb_status, nb_status)

    contact["zerobounce_status"] = zb_status
    contact["zerobounce_reason"] = zb_reason
    contact["neverbounce_status"] = nb_status
    contact["neverbounce_reason"] = nb_reason
    contact["final_validation_status"] = final_status
    contact["final_validation_reason"] = final_reason

    return contact


def validate_contacts(contacts: list[dict]) -> list[dict]:
    return [validate_contact_email(c) for c in contacts]
