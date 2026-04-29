"""Async SQLAlchemy engine and session factory."""
from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.config.settings import get_settings

_engine: "sqlalchemy.ext.asyncio.AsyncEngine | None" = None  # type: ignore[name-defined]
_session_factory: "async_sessionmaker[AsyncSession] | None" = None


def get_engine() -> "sqlalchemy.ext.asyncio.AsyncEngine":  # type: ignore[name-defined]
    import sqlalchemy.ext.asyncio as _aio

    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.db_url,
            echo=False,
            connect_args={"check_same_thread": False},
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            expire_on_commit=False,
            autoflush=False,
        )
    return _session_factory


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def dispose_engine() -> None:
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None
