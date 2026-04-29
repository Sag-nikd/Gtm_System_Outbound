"""Tests for the async repository layer."""
from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.runs import RunStatus
from src.db.repository.companies import CompanyRepository
from src.db.repository.contacts import ContactRepository
from src.db.repository.runs import PipelineRunRepository


@pytest.mark.asyncio
async def test_company_upsert_creates(db_session: AsyncSession) -> None:
    repo = CompanyRepository(db_session)
    company, created = await repo.upsert("acme.com", name="Acme")
    assert created is True
    assert company.domain == "acme.com"


@pytest.mark.asyncio
async def test_company_upsert_normalises_domain(db_session: AsyncSession) -> None:
    repo = CompanyRepository(db_session)
    c1, created1 = await repo.upsert("ACME.COM", name="Acme")
    c2, created2 = await repo.upsert("acme.com", name="Acme Updated")
    assert created1 is True
    assert created2 is False
    assert c1.id == c2.id
    assert c2.name == "Acme Updated"


@pytest.mark.asyncio
async def test_company_get_by_domain(db_session: AsyncSession) -> None:
    repo = CompanyRepository(db_session)
    await repo.upsert("example.com", name="Example")
    found = await repo.get_by_domain("example.com")
    assert found is not None
    assert found.name == "Example"

    missing = await repo.get_by_domain("missing.com")
    assert missing is None


@pytest.mark.asyncio
async def test_contact_upsert_normalises_email(db_session: AsyncSession) -> None:
    repo = ContactRepository(db_session)
    c1, created1 = await repo.upsert("Alice@Example.COM", first_name="Alice")
    c2, created2 = await repo.upsert("alice@example.com", first_name="AliceUpdated")
    assert created1 is True
    assert created2 is False
    assert c1.id == c2.id
    assert c2.first_name == "AliceUpdated"


@pytest.mark.asyncio
async def test_pipeline_run_complete(db_session: AsyncSession) -> None:
    repo = PipelineRunRepository(db_session)
    from src.db.models.runs import PipelineRun
    run = PipelineRun(status=RunStatus.running)
    db_session.add(run)
    await db_session.flush()

    updated = await repo.complete(run.id, RunStatus.completed, summary={"companies": 10})
    assert updated is not None
    assert updated.status == RunStatus.completed
    assert updated.completed_at is not None


@pytest.mark.asyncio
async def test_pipeline_run_add_event(db_session: AsyncSession) -> None:
    repo = PipelineRunRepository(db_session)
    from src.db.models.runs import PipelineRun
    run = PipelineRun(status=RunStatus.running)
    db_session.add(run)
    await db_session.flush()

    await repo.add_event(run.id, "stage_started", stage="ingest", payload={"count": 5})
    events = await repo.events_for_run(run.id)
    assert len(events) == 1
    assert events[0].stage == "ingest"


@pytest.mark.asyncio
async def test_repository_count(db_session: AsyncSession) -> None:
    repo = CompanyRepository(db_session)
    assert await repo.count() == 0
    await repo.upsert("a.com")
    await repo.upsert("b.com")
    assert await repo.count() == 2
