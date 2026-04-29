from __future__ import annotations

from sqlalchemy import select

from src.db.models.contacts import Contact
from src.db.repository.base import BaseRepository


class ContactRepository(BaseRepository[Contact]):
    model = Contact

    async def get_by_email(self, email: str) -> Contact | None:
        result = await self._session.execute(
            select(Contact).where(Contact.email == email.lower())
        )
        return result.scalar_one_or_none()

    async def upsert(self, email: str, **fields: object) -> tuple[Contact, bool]:
        """Return (contact, created). Upserts by lower(email)."""
        email = email.lower()
        existing = await self.get_by_email(email)
        if existing:
            for k, v in fields.items():
                setattr(existing, k, v)
            await self._session.flush()
            return existing, False
        contact = Contact(email=email, **fields)  # type: ignore[arg-type]
        return await self.add(contact), True

    async def list_by_company(self, company_id: str) -> list[Contact]:
        result = await self._session.execute(
            select(Contact).where(Contact.company_id == company_id)
        )
        return list(result.scalars().all())
