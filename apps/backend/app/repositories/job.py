"""Repositories for background jobs and media renders."""

from __future__ import annotations

import uuid
from datetime import datetime

from app.models.domain_enums import JobStatus
from app.models.job import QueueJob, RenderJob
from app.repositories.base import BaseRepository


class QueueJobRepository(BaseRepository[QueueJob]):
    model = QueueJob

    async def get_by_external_id(self, external_id: str) -> QueueJob | None:
        return await self.find_by(external_id=external_id)

    async def list_ready(self, now: datetime, limit: int = 50) -> list[QueueJob]:
        """Queued jobs whose scheduled time has arrived, highest priority first."""
        stmt = (
            self._base_query()
            .where(
                QueueJob.status == JobStatus.QUEUED.value,
                (QueueJob.scheduled_for.is_(None)) | (QueueJob.scheduled_for <= now),
            )
            .order_by(QueueJob.priority.desc(), QueueJob.created_at)
            .limit(limit)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def list_retryable(self, limit: int = 50) -> list[QueueJob]:
        stmt = (
            self._base_query()
            .where(
                QueueJob.status == JobStatus.FAILED.value,
                QueueJob.attempts < QueueJob.max_attempts,
            )
            .limit(limit)
        )
        return list((await self.session.execute(stmt)).scalars().all())


class RenderJobRepository(BaseRepository[RenderJob]):
    model = RenderJob

    async def list_for_video(self, video_id: uuid.UUID) -> list[RenderJob]:
        stmt = (
            self._base_query()
            .where(RenderJob.video_id == video_id)
            .order_by(RenderJob.created_at)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def list_active(self, limit: int = 100) -> list[RenderJob]:
        stmt = (
            self._base_query()
            .where(
                RenderJob.status.in_([JobStatus.QUEUED.value, JobStatus.RUNNING.value])
            )
            .limit(limit)
        )
        return list((await self.session.execute(stmt)).scalars().all())
