"""Generic async repository — CRUD over a SQLAlchemy model."""
from __future__ import annotations

from typing import Any, Generic, TypeVar

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    model: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, id: str) -> ModelT | None:
        return await self._session.get(self.model, id)

    async def list(self, limit: int = 100, offset: int = 0) -> list[ModelT]:
        result = await self._session.execute(
            select(self.model).limit(limit).offset(offset)
        )
        return list(result.scalars().all())

    async def add(self, obj: ModelT) -> ModelT:
        self._session.add(obj)
        await self._session.flush()
        return obj

    async def delete(self, obj: ModelT) -> None:
        await self._session.delete(obj)
        await self._session.flush()

    async def count(self) -> int:
        result = await self._session.execute(
            select(func.count()).select_from(self.model)
        )
        return result.scalar_one()
