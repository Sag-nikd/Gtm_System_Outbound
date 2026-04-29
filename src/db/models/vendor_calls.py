from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.db.models.base import Base, _now, _uuid


class VendorName(str, enum.Enum):
    apollo = "apollo"
    zerobounce = "zerobounce"
    instantly = "instantly"
    hubspot = "hubspot"
    gong = "gong"
    granola = "granola"
    notion = "notion"
    anthropic = "anthropic"
    voyage = "voyage"
    sendgrid = "sendgrid"
    slack = "slack"


class VendorCall(Base):
    __tablename__ = "vendor_calls"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    run_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("pipeline_runs.id"), nullable=True
    )
    vendor: Mapped[VendorName] = mapped_column(Enum(VendorName), nullable=False)
    endpoint: Mapped[str] = mapped_column(String(255), nullable=False)
    units_consumed: Mapped[float | None] = mapped_column(Float)
    credit_cost: Mapped[float | None] = mapped_column(Float)
    dollar_cost: Mapped[float | None] = mapped_column(Float)
    success: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text)
    called_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    latency_ms: Mapped[int | None] = mapped_column(Integer)
