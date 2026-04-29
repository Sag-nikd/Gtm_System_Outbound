from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import desc, select

from src.db.models.runs import PipelineRun, RunEvent, RunStatus
from src.db.repository.base import BaseRepository


class PipelineRunRepository(BaseRepository[PipelineRun]):
    model = PipelineRun

    async def list_recent(self, limit: int = 20) -> list[PipelineRun]:
        result = await self._session.execute(
            select(PipelineRun).order_by(desc(PipelineRun.started_at)).limit(limit)
        )
        return list(result.scalars().all())

    async def complete(
        self, run_id: str, status: RunStatus, summary: dict[str, Any] | None = None
    ) -> PipelineRun | None:
        run = await self.get(run_id)
        if run:
            run.status = status
            run.completed_at = datetime.now(timezone.utc)
            if summary:
                run.summary = json.dumps(summary)
            await self._session.flush()
        return run

    async def add_event(
        self, run_id: str, event_type: str, stage: str | None = None, payload: dict[str, Any] | None = None
    ) -> RunEvent:
        event = RunEvent(
            run_id=run_id,
            event_type=event_type,
            stage=stage,
            payload=json.dumps(payload) if payload else None,
        )
        self._session.add(event)
        await self._session.flush()
        return event

    async def events_for_run(self, run_id: str) -> list[RunEvent]:
        result = await self._session.execute(
            select(RunEvent).where(RunEvent.run_id == run_id).order_by(RunEvent.created_at)
        )
        return list(result.scalars().all())
