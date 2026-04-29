from __future__ import annotations

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKey


class Contact(Base, UUIDPrimaryKey, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "contacts"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    company_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("companies.id"), nullable=True
    )
    first_name: Mapped[str | None] = mapped_column(String(100))
    last_name: Mapped[str | None] = mapped_column(String(100))
    title: Mapped[str | None] = mapped_column(String(200))
    persona: Mapped[str | None] = mapped_column(String(100))
    linkedin_url: Mapped[str | None] = mapped_column(String(500))

    # Enrichment / validation state
    validation_status: Mapped[str | None] = mapped_column(String(50))
    pipeline_state: Mapped[str | None] = mapped_column(String(50))

    company: Mapped["src.db.models.companies.Company | None"] = relationship(  # type: ignore[name-defined]
        "Company", foreign_keys=[company_id]
    )
