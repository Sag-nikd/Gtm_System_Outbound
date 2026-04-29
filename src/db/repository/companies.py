from __future__ import annotations

from sqlalchemy import select

from src.db.models.companies import Company
from src.db.repository.base import BaseRepository


class CompanyRepository(BaseRepository[Company]):
    model = Company

    async def get_by_domain(self, domain: str) -> Company | None:
        result = await self._session.execute(
            select(Company).where(Company.domain == domain.lower())
        )
        return result.scalar_one_or_none()

    async def upsert(self, domain: str, **fields: object) -> tuple[Company, bool]:
        """Return (company, created). Upserts by lower(domain)."""
        domain = domain.lower()
        existing = await self.get_by_domain(domain)
        if existing:
            for k, v in fields.items():
                setattr(existing, k, v)
            await self._session.flush()
            return existing, False
        company = Company(domain=domain, **fields)  # type: ignore[arg-type]
        return await self.add(company), True
