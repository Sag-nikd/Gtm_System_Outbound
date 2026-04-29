from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.db.models.base import Base, TimestampMixin, UUIDPrimaryKey, _now, _uuid


class RunStatus(str, enum.Enum):
    running = "running"
    completed = "completed"
    failed = "failed"
    aborted = "aborted"


class PipelineRun(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "pipeline_runs"

    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[RunStatus] = mapped_column(
        Enum(RunStatus), default=RunStatus.running, nullable=False
    )
    config_snapshot: Mapped[str | None] = mapped_column(Text)  # JSON blob
    summary: Mapped[str | None] = mapped_column(Text)          # JSON blob


class RunEvent(Base):
    __tablename__ = "run_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    run_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("pipeline_runs.id"), nullable=False
    )
    stage: Mapped[str | None] = mapped_column(String(100))
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[str | None] = mapped_column(Text)  # JSON blob
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
