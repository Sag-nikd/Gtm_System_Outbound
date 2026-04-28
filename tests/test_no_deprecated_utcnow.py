"""Verify that CRM setup modules use timezone-aware datetime instead of deprecated utcnow()."""
from __future__ import annotations

import pathlib


_SETUP_FILES = [
    "src/crm/hubspot/setup.py",
    "src/crm/salesforce/setup.py",
    "src/crm/setup_generator.py",
]


def test_hubspot_setup_no_utcnow():
    src = pathlib.Path("src/crm/hubspot/setup.py").read_text(encoding="utf-8")
    assert "utcnow()" not in src, "src/crm/hubspot/setup.py uses deprecated datetime.utcnow()"


def test_salesforce_setup_no_utcnow():
    src = pathlib.Path("src/crm/salesforce/setup.py").read_text(encoding="utf-8")
    assert "utcnow()" not in src, "src/crm/salesforce/setup.py uses deprecated datetime.utcnow()"


def test_setup_generator_no_utcnow():
    src = pathlib.Path("src/crm/setup_generator.py").read_text(encoding="utf-8")
    assert "utcnow()" not in src, "src/crm/setup_generator.py uses deprecated datetime.utcnow()"
