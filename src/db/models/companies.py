from __future__ import annotations

from sqlalchemy import Float, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from src.db.models.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPrimaryKey


class Company(Base, UUIDPrimaryKey, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "companies"

    domain: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str | None] = mapped_column(String(255))
    country: Mapped[str | None] = mapped_column(String(100))
    employee_count: Mapped[int | None] = mapped_column(Integer)
    revenue_band: Mapped[str | None] = mapped_column(String(50))
    industry: Mapped[str | None] = mapped_column(String(100))
    source: Mapped[str | None] = mapped_column(String(50))

    # ICP scoring — populated by stage 02_score
    icp_score: Mapped[float | None] = mapped_column(Float)
    icp_tier: Mapped[str | None] = mapped_column(String(20))
    fit_reason: Mapped[str | None] = mapped_column(String(1000))

    # Pipeline state
    pipeline_state: Mapped[str | None] = mapped_column(String(50))
