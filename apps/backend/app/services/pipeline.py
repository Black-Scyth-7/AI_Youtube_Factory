"""The video pipeline: research → script → voiceover → render → publish →
analytics → learning.

Each stage is a separate method rather than one long function, so a run can be
resumed at the stage that failed instead of starting over — rendering is the
expensive step and repeating it because publishing failed would be wasteful.

External work goes through the Phase 08 provider layer, so the whole pipeline
runs offline against the deterministic mocks.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import UploadCompleted, get_event_bus
from app.core.pipeline import ProviderKind, get_provider
from app.core.plugins import HookName, dispatch
from app.core.storage import get_storage
from app.exceptions.base import ConflictError, NotFoundError, ValidationError
from app.models.domain_enums import (
    PipelineStage,
    PublicationStatus,
    UsageMetric,
    VideoStatus,
)
from app.models.pipeline import (
    AnalyticsRecord,
    PerformanceLesson,
    PipelineRun,
    Publication,
    ResearchNote,
)
from app.models.video import Video, VideoVersion
from app.observability.stages import record_artifact_size, track_stage
from app.repositories.base import BaseRepository
from app.services.billing import UsageService

#: Stages in the order the pipeline performs them.
STAGE_ORDER: tuple[str, ...] = (
    PipelineStage.RESEARCH.value,
    PipelineStage.SCRIPT.value,
    PipelineStage.VOICEOVER.value,
    PipelineStage.RENDER.value,
    PipelineStage.PUBLISH.value,
    PipelineStage.ANALYTICS.value,
    PipelineStage.LEARNING.value,
)


class PipelineRunRepository(BaseRepository[PipelineRun]):
    model = PipelineRun

    async def latest_for_video(self, video_id: uuid.UUID) -> PipelineRun | None:
        stmt = (
            self._base_query()
            .where(PipelineRun.video_id == video_id)
            .order_by(PipelineRun.created_at.desc())
        )
        return (await self.session.execute(stmt)).scalars().first()


class PublicationRepository(BaseRepository[Publication]):
    model = Publication

    async def for_video(
        self, video_id: uuid.UUID, platform: str = "youtube"
    ) -> Publication | None:
        return await self.find_by(video_id=video_id, platform=platform)


class VideoPipelineService:
    """Drives a video through the pipeline, one stage at a time."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.runs = PipelineRunRepository(session)
        self.publications = PublicationRepository(session)
        self.events = get_event_bus()

    # -- helpers ----------------------------------------------------------
    async def _video(self, video_id: uuid.UUID) -> Video:
        video = await self.session.get(Video, video_id)
        if video is None or video.deleted_at is not None:
            raise NotFoundError("Video not found.", details={"video_id": str(video_id)})
        return video

    async def _current_version(self, video: Video) -> VideoVersion | None:
        if video.current_version_id is None:
            return None
        return await self.session.get(VideoVersion, video.current_version_id)

    async def start(self, video_id: uuid.UUID) -> PipelineRun:
        """Begin a run. Only one may be in flight per video."""
        await self._video(video_id)
        existing = await self.runs.latest_for_video(video_id)
        if existing is not None and existing.finished_at is None:
            raise ConflictError(
                "A pipeline run is already in progress for this video.",
                details={"run_id": str(existing.id)},
            )
        run = PipelineRun(
            video_id=video_id,
            stage=PipelineStage.RESEARCH.value,
            started_at=datetime.now(UTC),
        )
        return await self.runs.add(run)

    async def _advance(self, run: PipelineRun, stage: str, **artifacts: Any) -> None:
        run.stage = stage
        run.error = None
        if artifacts:
            # Reassigned rather than mutated: SQLAlchemy does not track in-place
            # changes to a JSON dict.
            run.artifacts = {**run.artifacts, **artifacts}
            # Every stage funnels its artifact through here, so sizes are
            # recorded once instead of in each stage that happens to remember.
            for name, artifact in artifacts.items():
                if isinstance(artifact, dict):
                    record_artifact_size(name, artifact.get("size_bytes"))
        if stage in (PipelineStage.DONE.value, PipelineStage.FAILED.value):
            run.finished_at = datetime.now(UTC)
        await self.session.flush()

    async def fail(self, run_id: uuid.UUID, error: str) -> PipelineRun:
        run = await self.runs.get(run_id)
        if run is None:
            raise NotFoundError("Pipeline run not found.")
        run.stage = PipelineStage.FAILED.value
        run.error = error
        run.finished_at = datetime.now(UTC)
        await self.session.flush()
        return run

    # -- stages -----------------------------------------------------------
    async def add_research(
        self,
        video_id: uuid.UUID,
        notes: list[dict[str, Any]],
    ) -> list[ResearchNote]:
        """Record research findings for a video."""
        await self._video(video_id)
        created: list[ResearchNote] = []
        for item in notes:
            summary = (item.get("summary") or "").strip()
            if not summary:
                raise ValidationError("A research note needs a summary.")
            note = ResearchNote(
                video_id=video_id,
                source_url=item.get("source_url"),
                title=item.get("title"),
                summary=summary,
                relevance=float(item.get("relevance", 0.0)),
            )
            self.session.add(note)
            created.append(note)
        await self.session.flush()
        return created

    @track_stage("research")
    async def research(self, run: PipelineRun) -> PipelineRun:
        """Close the research stage, recording how much was gathered."""
        stmt = select(ResearchNote).where(
            ResearchNote.video_id == run.video_id, ResearchNote.deleted_at.is_(None)
        )
        notes = (await self.session.execute(stmt)).scalars().all()
        await self._advance(
            run, PipelineStage.SCRIPT.value, research={"note_count": len(notes)}
        )
        return run

    @track_stage("script")
    async def script(self, run: PipelineRun, script: str) -> VideoVersion:
        """Attach a script as a new version and make it current."""
        if not script.strip():
            raise ValidationError("Script cannot be empty.")
        video = await self._video(run.video_id)

        stmt = select(VideoVersion).where(VideoVersion.video_id == video.id)
        existing = (await self.session.execute(stmt)).scalars().all()
        version = VideoVersion(
            video_id=video.id,
            version_number=len(existing) + 1,
            script=script,
        )
        self.session.add(version)
        await self.session.flush()

        video.current_version_id = version.id
        video.status = VideoStatus.SCRIPTING.value
        await self._advance(
            run,
            PipelineStage.VOICEOVER.value,
            script={"version_id": str(version.id), "characters": len(script)},
        )
        return version

    @track_stage("voiceover")
    async def voiceover(
        self, run: PipelineRun, *, voice: str | None = None
    ) -> dict[str, Any]:
        """Synthesise narration for the current script."""
        video = await self._video(run.video_id)
        version = await self._current_version(video)
        if version is None or not version.script:
            raise ValidationError("The video has no script to narrate.")

        provider = get_provider(ProviderKind.SPEECH)
        key = f"videos/{video.id}/audio/v{version.version_number}.mp3"
        result = await provider.synthesize(
            version.script, voice=voice or "default", storage_key=key
        )
        artifact = {
            "storage_key": result.storage_key,
            "duration_seconds": result.duration_seconds,
            "voice": result.voice,
            "size_bytes": result.size_bytes,
        }
        await self._advance(run, PipelineStage.RENDER.value, voiceover=artifact)
        return artifact

    @track_stage("render")
    async def render(
        self, run: PipelineRun, *, options: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Render the video from its script and narration."""
        video = await self._video(run.video_id)
        version = await self._current_version(video)
        if version is None or not version.script:
            raise ValidationError("The video has no script to render.")

        audio_key = (run.artifacts.get("voiceover") or {}).get("storage_key")
        provider = get_provider(ProviderKind.RENDER)
        key = f"videos/{video.id}/render/v{version.version_number}.mp4"
        result = await provider.render(
            script=version.script,
            audio_key=audio_key,
            storage_key=key,
            options=options,
        )
        video.status = VideoStatus.RENDERING.value
        artifact = {
            "storage_key": result.storage_key,
            "duration_seconds": result.duration_seconds,
            "width": result.width,
            "height": result.height,
            "size_bytes": result.size_bytes,
        }
        await self._advance(run, PipelineStage.PUBLISH.value, render=artifact)

        # Metered so a plan's render quota is enforced against real work.
        if video.project_id is not None:
            await UsageService(self.session).record(
                video.project_id,
                UsageMetric.VIDEO_RENDER.value,
                1,
                source_type="video",
                source_id=video.id,
            )
        return artifact

    @track_stage("publish")
    async def publish(
        self,
        run: PipelineRun,
        *,
        platform: str = "youtube",
        tags: list[str] | None = None,
        options: dict[str, Any] | None = None,
    ) -> Publication:
        """Upload the rendered video to a platform."""
        video = await self._video(run.video_id)
        render = run.artifacts.get("render") or {}
        video_key = render.get("storage_key")
        if not video_key:
            raise ValidationError("Nothing has been rendered for this run yet.")

        # Plugins get to shape the listing before it goes out. Dispatch never
        # raises: a third-party plugin failing must not fail a publish, so a
        # broken one is recorded and the original values are used.
        listing, _ = await dispatch(
            HookName.BEFORE_PUBLISH,
            {
                "title": video.title,
                "description": video.description,
                "tags": list(tags or []),
                "platform": platform,
            },
        )
        title = listing.get("title") or video.title
        description = listing.get("description") if "description" in listing else None
        final_tags = listing.get("tags")
        if not isinstance(final_tags, list):
            final_tags = list(tags or [])

        publication = await self.publications.for_video(video.id, platform)
        if publication is None:
            publication = Publication(
                video_id=video.id,
                platform=platform,
                title=title,
                description=description if description is not None else video.description,
                tags=final_tags,
            )
            self.session.add(publication)
            await self.session.flush()

        publication.status = PublicationStatus.PUBLISHING.value
        await self.session.flush()

        provider = get_provider(ProviderKind.PUBLISH)
        try:
            result = await provider.publish(
                video_key=video_key,
                title=video.title,
                description=video.description,
                tags=tags or publication.tags,
                options=options,
            )
        except Exception as exc:
            publication.status = PublicationStatus.FAILED.value
            publication.error = str(exc)
            await self.session.flush()
            raise

        publication.status = PublicationStatus.PUBLISHED.value
        publication.external_id = result.external_id
        publication.url = result.url
        publication.published_at = datetime.now(UTC)
        publication.error = None
        video.status = VideoStatus.PUBLISHED.value

        await self._advance(
            run,
            PipelineStage.ANALYTICS.value,
            publish={"external_id": result.external_id, "url": result.url},
        )
        # UploadCompleted describes the stored object, not the video.
        await self.events.publish(
            UploadCompleted(
                storage_key=video_key, size_bytes=int(render.get("size_bytes") or 0)
            )
        )
        return publication

    @track_stage("analytics")
    async def collect_analytics(
        self, publication_id: uuid.UUID, *, on: date | None = None
    ) -> AnalyticsRecord:
        """Fetch and store one day's metrics, updating rather than duplicating."""
        publication = await self.publications.get(publication_id)
        if publication is None:
            raise NotFoundError("Publication not found.")
        if not publication.external_id:
            raise ValidationError("That publication has not been published yet.")

        provider = get_provider(ProviderKind.ANALYTICS)
        snapshot = await provider.fetch(external_id=publication.external_id, on=on)

        stmt = select(AnalyticsRecord).where(
            AnalyticsRecord.publication_id == publication.id,
            AnalyticsRecord.measured_on == snapshot.measured_on,
        )
        record = (await self.session.execute(stmt)).scalars().first()
        if record is None:
            record = AnalyticsRecord(
                publication_id=publication.id, measured_on=snapshot.measured_on
            )
            self.session.add(record)

        record.views = snapshot.views
        record.likes = snapshot.likes
        record.comments = snapshot.comments
        record.watch_time_seconds = snapshot.watch_time_seconds
        record.impressions = snapshot.impressions
        record.extra = dict(snapshot.extra)
        await self.session.flush()
        return record

    @track_stage("learn")
    async def learn(
        self, run: PipelineRun, *, ctr_target: float = 0.05
    ) -> list[PerformanceLesson]:
        """Derive lessons from the latest analytics and close the run.

        Deliberately simple and explainable: an agent can consult these, and a
        human can see why each was recorded.
        """
        publication = await self.publications.for_video(run.video_id)
        lessons: list[PerformanceLesson] = []

        if publication is not None:
            stmt = (
                select(AnalyticsRecord)
                .where(AnalyticsRecord.publication_id == publication.id)
                .order_by(AnalyticsRecord.measured_on.desc())
            )
            latest = (await self.session.execute(stmt)).scalars().first()
            if latest is not None:
                ctr = latest.click_through_rate
                if ctr < ctr_target:
                    lessons.append(
                        PerformanceLesson(
                            video_id=run.video_id,
                            dimension="thumbnail_or_title",
                            observation=(
                                f"Click-through rate {ctr:.2%} is below the "
                                f"{ctr_target:.0%} target; the title or thumbnail "
                                "is likely the limiting factor."
                            ),
                            confidence=0.6,
                            evidence={
                                "views": latest.views,
                                "impressions": latest.impressions,
                                "ctr": ctr,
                            },
                        )
                    )
                render = run.artifacts.get("render") or {}
                duration = float(render.get("duration_seconds") or 0)
                if duration and latest.views:
                    retention = latest.watch_time_seconds / (duration * latest.views)
                    lessons.append(
                        PerformanceLesson(
                            video_id=run.video_id,
                            dimension="retention",
                            observation=(
                                f"Average retention is {retention:.0%} of a "
                                f"{duration:.0f}s video."
                            ),
                            confidence=0.5,
                            evidence={
                                "watch_time_seconds": latest.watch_time_seconds,
                                "duration_seconds": duration,
                                "retention": retention,
                            },
                        )
                    )

        for lesson in lessons:
            self.session.add(lesson)
        await self._advance(
            run, PipelineStage.DONE.value, learning={"lesson_count": len(lessons)}
        )
        return lessons

    # -- convenience ------------------------------------------------------
    async def run_to_completion(
        self,
        video_id: uuid.UUID,
        *,
        script: str,
        research_notes: list[dict[str, Any]] | None = None,
        tags: list[str] | None = None,
    ) -> PipelineRun:
        """Take a video through every stage in one call.

        Useful for tests and for a workflow node that owns the whole pipeline;
        production runs drive the stages individually so each can be retried.
        """
        run = await self.start(video_id)
        if research_notes:
            await self.add_research(video_id, research_notes)
        await self.research(run)
        await self.script(run, script)
        await self.voiceover(run)
        await self.render(run)
        publication = await self.publish(run, tags=tags)
        await self.collect_analytics(publication.id)
        await self.learn(run)
        return run

    async def artifact_url(self, run: PipelineRun, stage: str) -> str | None:
        """A temporary link to a stage's artefact, if it produced one."""
        artifact = run.artifacts.get(stage) or {}
        key = artifact.get("storage_key")
        if not key:
            return None
        return await get_storage().presign_url(key)
