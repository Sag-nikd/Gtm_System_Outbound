"""Tests for SQLAlchemy models — basic persistence and constraints."""
from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.companies import Company
from src.db.models.contacts import Contact
from src.db.models.runs import PipelineRun, RunEvent, RunStatus
from src.db.models.vendor_calls import VendorCall, VendorName


@pytest.mark.asyncio
async def test_company_roundtrip(db_session: AsyncSession) -> None:
    company = Company(domain="acme.com", name="Acme Corp", industry="SaaS")
    db_session.add(company)
    await db_session.flush()

    fetched = await db_session.get(Company, company.id)
    assert fetched is not None
    assert fetched.domain == "acme.com"
    assert fetched.name == "Acme Corp"


@pytest.mark.asyncio
async def test_contact_roundtrip(db_session: AsyncSession) -> None:
    company = Company(domain="acme.com", name="Acme")
    db_session.add(company)
    await db_session.flush()

    contact = Contact(email="alice@acme.com", company_id=company.id, first_name="Alice")
    db_session.add(contact)
    await db_session.flush()

    fetched = await db_session.get(Contact, contact.id)
    assert fetched is not None
    assert fetched.email == "alice@acme.com"
    assert fetched.company_id == company.id


@pytest.mark.asyncio
async def test_pipeline_run_roundtrip(db_session: AsyncSession) -> None:
    run = PipelineRun(status=RunStatus.running)
    db_session.add(run)
    await db_session.flush()

    fetched = await db_session.get(PipelineRun, run.id)
    assert fetched is not None
    assert fetched.status == RunStatus.running


@pytest.mark.asyncio
async def test_run_event_links_to_run(db_session: AsyncSession) -> None:
    run = PipelineRun(status=RunStatus.running)
    db_session.add(run)
    await db_session.flush()

    event = RunEvent(run_id=run.id, event_type="stage_started", stage="ingest")
    db_session.add(event)
    await db_session.flush()

    fetched = await db_session.get(RunEvent, event.id)
    assert fetched is not None
    assert fetched.run_id == run.id


@pytest.mark.asyncio
async def test_vendor_call_roundtrip(db_session: AsyncSession) -> None:
    call = VendorCall(vendor=VendorName.apollo, endpoint="search_companies", success=True, latency_ms=230)
    db_session.add(call)
    await db_session.flush()

    fetched = await db_session.get(VendorCall, call.id)
    assert fetched is not None
    assert fetched.vendor == VendorName.apollo
    assert fetched.latency_ms == 230
