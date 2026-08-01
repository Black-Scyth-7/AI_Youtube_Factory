"""Background job services: the durable queue record and media renders.

These own the *state* of work. The broker (Celery/RabbitMQ) owns delivery; a row
here is what survives a broker restart and what the UI and retry logic read.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import RenderFinished, get_event_bus
from app.exceptions.base import ConflictError, NotFoundError, ValidationError
from app.models.domain_enums import JobStatus, RenderJobKind
from app.models.job import QueueJob, RenderJob
from app.repositories.job import QueueJobRepository, RenderJobRepository

#: Statuses a job cannot move out of.
TERMINAL_STATUSES = frozenset({JobStatus.SUCCEEDED.value, JobStatus.CANCELLED.value})


class QueueJobService:
    """Tracks background work through its lifecycle."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = QueueJobRepository(session)

    async def enqueue(
        self,
        task_name: str,
        *,
        payload: dict[str, Any] | None = None,
        queue: str = "default",
        organization_id: uuid.UUID | None = None,
        priority: int = 0,
        max_attempts: int = 3,
        scheduled_for: datetime | None = None,
    ) -> QueueJob:
        if max_attempts < 1:
            raise ValidationError("max_attempts must be at least 1.")
        job = QueueJob(
            organization_id=organization_id,
            queue=queue,
            task_name=task_name,
            payload=payload or {},
            priority=priority,
            max_attempts=max_attempts,
            scheduled_for=scheduled_for,
            status=JobStatus.QUEUED.value,
        )
        return await self.repo.add(job)

    async def mark_running(
        self, job_id: uuid.UUID, external_id: str | None = None
    ) -> QueueJob:
        job = await self._get(job_id)
        if job.status in TERMINAL_STATUSES:
            raise ConflictError(
                "Job has already finished.", details={"status": job.status}
            )
        job.status = JobStatus.RUNNING.value
        job.attempts += 1
        job.started_at = datetime.now(UTC)
        if external_id:
            job.external_id = external_id
        await self.session.flush()
        return job

    async def mark_succeeded(
        self, job_id: uuid.UUID, result: dict[str, Any] | None = None
    ) -> QueueJob:
        job = await self._get(job_id)
        job.status = JobStatus.SUCCEEDED.value
        job.result = result or {}
        job.error = None
        job.finished_at = datetime.now(UTC)
        await self.session.flush()
        return job

    async def mark_failed(self, job_id: uuid.UUID, error: str) -> QueueJob:
        job = await self._get(job_id)
        job.status = JobStatus.FAILED.value
        job.error = error
        job.finished_at = datetime.now(UTC)
        await self.session.flush()
        return job

    async def cancel(self, job_id: uuid.UUID) -> QueueJob:
        job = await self._get(job_id)
        if job.status == JobStatus.SUCCEEDED.value:
            raise ConflictError("Cannot cancel a job that already succeeded.")
        job.status = JobStatus.CANCELLED.value
        job.finished_at = datetime.now(UTC)
        await self.session.flush()
        return job

    async def retry(self, job_id: uuid.UUID) -> QueueJob:
        """Requeue a failed job that still has attempts left."""
        job = await self._get(job_id)
        if not job.can_retry:
            raise ConflictError(
                "Job is not retryable.",
                details={"status": job.status, "attempts": job.attempts},
            )
        job.status = JobStatus.QUEUED.value
        job.error = None
        job.finished_at = None
        await self.session.flush()
        return job

    async def ready(self, limit: int = 50) -> list[QueueJob]:
        return await self.repo.list_ready(datetime.now(UTC), limit=limit)

    async def _get(self, job_id: uuid.UUID) -> QueueJob:
        job = await self.repo.get(job_id)
        if job is None:
            raise NotFoundError("Job not found.")
        return job


class RenderJobService:
    """Tracks media renders for a video and publishes completion events."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = RenderJobRepository(session)
        self.jobs = QueueJobService(session)
        self.events = get_event_bus()

    async def submit(
        self,
        video_id: uuid.UUID,
        kind: str = RenderJobKind.VIDEO.value,
        *,
        organization_id: uuid.UUID | None = None,
        options: dict[str, Any] | None = None,
    ) -> RenderJob:
        """Create a render and the queue job that will carry out the work."""
        queue_job = await self.jobs.enqueue(
            "render.media",
            payload={"video_id": str(video_id), "kind": kind},
            queue="render",
            organization_id=organization_id,
        )
        render = RenderJob(
            video_id=video_id,
            organization_id=organization_id,
            queue_job_id=queue_job.id,
            kind=kind,
            status=JobStatus.QUEUED.value,
            options=options or {},
        )
        return await self.repo.add(render)

    async def update_progress(self, render_id: uuid.UUID, progress: int) -> RenderJob:
        if not 0 <= progress <= 100:
            raise ValidationError("Progress must be between 0 and 100.")
        render = await self._get(render_id)
        render.status = JobStatus.RUNNING.value
        render.progress = progress
        if render.started_at is None:
            render.started_at = datetime.now(UTC)
        await self.session.flush()
        return render

    async def complete(
        self,
        render_id: uuid.UUID,
        *,
        output_key: str,
        output_bytes: int | None = None,
        duration_seconds: int | None = None,
    ) -> RenderJob:
        render = await self._get(render_id)
        render.status = JobStatus.SUCCEEDED.value
        render.progress = 100
        render.output_key = output_key
        render.output_bytes = output_bytes
        render.duration_seconds = duration_seconds
        render.finished_at = datetime.now(UTC)
        render.error = None
        await self.session.flush()

        await self.events.publish(RenderFinished(video_id=render.video_id, success=True))
        return render

    async def fail(self, render_id: uuid.UUID, error: str) -> RenderJob:
        render = await self._get(render_id)
        render.status = JobStatus.FAILED.value
        render.error = error
        render.finished_at = datetime.now(UTC)
        await self.session.flush()

        # Subscribers care that the render ended, not only that it worked.
        await self.events.publish(RenderFinished(video_id=render.video_id, success=False))
        return render

    async def list_for_video(self, video_id: uuid.UUID) -> list[RenderJob]:
        return await self.repo.list_for_video(video_id)

    async def _get(self, render_id: uuid.UUID) -> RenderJob:
        render = await self.repo.get(render_id)
        if render is None:
            raise NotFoundError("Render job not found.")
        return render
