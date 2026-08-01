"""Tests for the video pipeline: research through publish, analytics, learning.

Everything runs against the deterministic mock providers and the local storage
backend, so the whole product path is exercised without a TTS key, a renderer,
or a YouTube account.
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import Any

import pytest
from app.core.pipeline import (
    ProviderKind,
    get_provider,
    register_provider,
    reset_providers,
)
from app.core.storage import get_storage
from app.exceptions.base import ConflictError, NotFoundError, ValidationError
from app.models.domain_enums import (
    PipelineStage,
    PublicationStatus,
    VideoStatus,
)
from app.models.video import Video
from app.services.pipeline import VideoPipelineService
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
def _clean_providers() -> Any:
    """Each test starts from the built-in mocks."""
    reset_providers()
    yield
    reset_providers()


async def _make_video(session: AsyncSession, title: str = "Episode 1") -> Video:
    video = Video(project_id=uuid.uuid4(), title=title, description="A test video")
    session.add(video)
    await session.flush()
    return video


# -- Providers ----------------------------------------------------------------
async def test_mock_providers_are_registered_for_every_capability() -> None:
    for kind in ProviderKind:
        assert get_provider(kind) is not None


async def test_mock_speech_is_deterministic() -> None:
    provider = get_provider(ProviderKind.SPEECH)
    a = await provider.synthesize("hello world", storage_key="t/a.mp3")
    b = await provider.synthesize("hello world", storage_key="t/b.mp3")
    assert a.duration_seconds == b.duration_seconds


async def test_mock_publish_id_is_stable_for_a_key() -> None:
    provider = get_provider(ProviderKind.PUBLISH)
    a = await provider.publish(video_key="v/1.mp4", title="T", description=None)
    b = await provider.publish(video_key="v/1.mp4", title="Different", description=None)
    c = await provider.publish(video_key="v/2.mp4", title="T", description=None)
    assert a.external_id == b.external_id
    assert a.external_id != c.external_id


async def test_a_custom_provider_can_replace_the_mock() -> None:
    """The point of the registry: swap in a real implementation."""

    class StubPublish:
        slug = "stub"

        async def publish(self, **kwargs: Any) -> Any:
            from app.core.pipeline import PublishResult

            return PublishResult(
                external_id="stub-1", url="https://stub/1", published_at="now"
            )

    register_provider(ProviderKind.PUBLISH, "stub", StubPublish)
    provider = get_provider(ProviderKind.PUBLISH, "stub")
    result = await provider.publish(video_key="k", title="t", description=None)
    assert result.external_id == "stub-1"


async def test_an_unknown_provider_slug_is_a_clear_error() -> None:
    from app.exceptions.base import ServiceUnavailableError

    with pytest.raises(ServiceUnavailableError, match="No publish provider"):
        get_provider(ProviderKind.PUBLISH, "nope")


# -- Stages -------------------------------------------------------------------
async def test_start_refuses_a_second_concurrent_run(session: AsyncSession) -> None:
    video = await _make_video(session)
    service = VideoPipelineService(session)
    await service.start(video.id)

    with pytest.raises(ConflictError):
        await service.start(video.id)


async def test_start_on_a_missing_video_raises(session: AsyncSession) -> None:
    with pytest.raises(NotFoundError):
        await VideoPipelineService(session).start(uuid.uuid4())


async def test_research_notes_are_recorded_and_counted(session: AsyncSession) -> None:
    video = await _make_video(session)
    service = VideoPipelineService(session)
    run = await service.start(video.id)

    await service.add_research(
        video.id,
        [
            {"summary": "Topic is trending", "relevance": 0.9},
            {"summary": "Competitor covered it", "source_url": "https://x.invalid"},
        ],
    )
    await service.research(run)

    assert run.stage == PipelineStage.SCRIPT.value
    assert run.artifacts["research"]["note_count"] == 2


async def test_a_research_note_needs_a_summary(session: AsyncSession) -> None:
    video = await _make_video(session)
    with pytest.raises(ValidationError):
        await VideoPipelineService(session).add_research(video.id, [{"summary": "  "}])


async def test_script_creates_a_version_and_becomes_current(
    session: AsyncSession,
) -> None:
    video = await _make_video(session)
    service = VideoPipelineService(session)
    run = await service.start(video.id)
    await service.research(run)

    version = await service.script(run, "Hello and welcome to the channel.")

    assert version.version_number == 1
    assert video.current_version_id == version.id
    assert video.status == VideoStatus.SCRIPTING.value
    assert run.stage == PipelineStage.VOICEOVER.value


async def test_an_empty_script_is_rejected(session: AsyncSession) -> None:
    video = await _make_video(session)
    service = VideoPipelineService(session)
    run = await service.start(video.id)
    with pytest.raises(ValidationError):
        await service.script(run, "   ")


async def test_voiceover_writes_real_bytes_to_storage(session: AsyncSession) -> None:
    """The mock exercises the storage path rather than stubbing it out."""
    video = await _make_video(session)
    service = VideoPipelineService(session)
    run = await service.start(video.id)
    await service.script(run, "One two three four five.")

    artifact = await service.voiceover(run)

    assert artifact["duration_seconds"] > 0
    stored = await get_storage().get(artifact["storage_key"])
    assert b"MOCK-AUDIO" in stored
    assert run.stage == PipelineStage.RENDER.value


async def test_voiceover_without_a_script_is_rejected(session: AsyncSession) -> None:
    video = await _make_video(session)
    service = VideoPipelineService(session)
    run = await service.start(video.id)
    with pytest.raises(ValidationError, match="no script"):
        await service.voiceover(run)


async def test_render_uses_the_narration_and_honours_options(
    session: AsyncSession,
) -> None:
    video = await _make_video(session)
    service = VideoPipelineService(session)
    run = await service.start(video.id)
    await service.script(run, "A short script.")
    audio = await service.voiceover(run)

    artifact = await service.render(run, options={"width": 1280, "height": 720})

    assert artifact["width"] == 1280 and artifact["height"] == 720
    body = await get_storage().get(artifact["storage_key"])
    assert audio["storage_key"].encode() in body  # the audio was passed through
    assert video.status == VideoStatus.RENDERING.value


async def test_publish_requires_something_rendered(session: AsyncSession) -> None:
    video = await _make_video(session)
    service = VideoPipelineService(session)
    run = await service.start(video.id)
    with pytest.raises(ValidationError, match="rendered"):
        await service.publish(run)


async def test_publish_records_the_platform_result(session: AsyncSession) -> None:
    video = await _make_video(session)
    service = VideoPipelineService(session)
    run = await service.start(video.id)
    await service.script(run, "Script body.")
    await service.voiceover(run)
    await service.render(run)

    publication = await service.publish(run, tags=["ai", "test"])

    assert publication.status == PublicationStatus.PUBLISHED.value
    assert publication.external_id and publication.url
    assert publication.published_at is not None
    assert video.status == VideoStatus.PUBLISHED.value
    assert run.stage == PipelineStage.ANALYTICS.value


async def test_a_failing_publish_is_recorded_on_the_publication(
    session: AsyncSession,
) -> None:
    class BrokenPublish:
        slug = "broken"

        async def publish(self, **kwargs: Any) -> Any:
            raise RuntimeError("platform rejected the upload")

    register_provider(ProviderKind.PUBLISH, "mock", BrokenPublish)

    video = await _make_video(session)
    service = VideoPipelineService(session)
    run = await service.start(video.id)
    await service.script(run, "Script body.")
    await service.voiceover(run)
    await service.render(run)

    with pytest.raises(RuntimeError):
        await service.publish(run)

    publication = await service.publications.for_video(video.id)
    assert publication is not None
    assert publication.status == PublicationStatus.FAILED.value
    assert "rejected" in (publication.error or "")


# -- Analytics ----------------------------------------------------------------
async def test_analytics_are_stored_and_refetching_updates_in_place(
    session: AsyncSession,
) -> None:
    video = await _make_video(session)
    service = VideoPipelineService(session)
    run = await service.start(video.id)
    await service.script(run, "Script body.")
    await service.voiceover(run)
    await service.render(run)
    publication = await service.publish(run)

    today = date.today()
    first = await service.collect_analytics(publication.id, on=today)
    second = await service.collect_analytics(publication.id, on=today)

    assert first.id == second.id  # updated, not duplicated
    assert first.views >= 0
    assert 0.0 <= first.click_through_rate <= 1.0


async def test_analytics_for_different_days_are_separate_rows(
    session: AsyncSession,
) -> None:
    video = await _make_video(session)
    service = VideoPipelineService(session)
    run = await service.start(video.id)
    await service.script(run, "Script body.")
    await service.voiceover(run)
    await service.render(run)
    publication = await service.publish(run)

    today = date.today()
    a = await service.collect_analytics(publication.id, on=today)
    b = await service.collect_analytics(publication.id, on=today - timedelta(days=1))
    assert a.id != b.id


async def test_analytics_before_publishing_is_rejected(session: AsyncSession) -> None:
    from app.models.pipeline import Publication

    video = await _make_video(session)
    publication = Publication(video_id=video.id, title="Unpublished")
    session.add(publication)
    await session.flush()

    with pytest.raises(ValidationError, match="not been published"):
        await VideoPipelineService(session).collect_analytics(publication.id)


def test_click_through_rate_handles_zero_impressions() -> None:
    from app.core.pipeline import AnalyticsSnapshot

    snapshot = AnalyticsSnapshot(measured_on=date.today(), views=0, impressions=0)
    assert snapshot.click_through_rate == 0.0


# -- Learning -----------------------------------------------------------------
async def test_low_click_through_produces_a_lesson(session: AsyncSession) -> None:
    video = await _make_video(session)
    service = VideoPipelineService(session)
    run = await service.start(video.id)
    await service.script(run, "Script body.")
    await service.voiceover(run)
    await service.render(run)
    publication = await service.publish(run)
    await service.collect_analytics(publication.id)

    # The mock yields ~12.5% CTR, so a 50% target guarantees the lesson fires.
    lessons = await service.learn(run, ctr_target=0.5)

    dimensions = {lesson.dimension for lesson in lessons}
    assert "thumbnail_or_title" in dimensions
    assert run.stage == PipelineStage.DONE.value
    assert run.finished_at is not None


async def test_learning_closes_the_run_even_without_analytics(
    session: AsyncSession,
) -> None:
    video = await _make_video(session)
    service = VideoPipelineService(session)
    run = await service.start(video.id)

    lessons = await service.learn(run)
    assert lessons == []
    assert run.stage == PipelineStage.DONE.value


# -- End to end ---------------------------------------------------------------
async def test_a_video_goes_from_idea_to_published_with_lessons(
    session: AsyncSession,
) -> None:
    """The whole product path, offline."""
    video = await _make_video(session, title="How transformers work")
    service = VideoPipelineService(session)

    run = await service.run_to_completion(
        video.id,
        script="Today we explain attention, step by step.",
        research_notes=[
            {"summary": "Attention explainers perform well", "relevance": 0.8}
        ],
        tags=["ml", "explainer"],
    )

    assert run.stage == PipelineStage.DONE.value
    assert run.finished_at is not None
    # Every stage left an artefact behind.
    assert {"research", "script", "voiceover", "render", "publish", "learning"} <= set(
        run.artifacts
    )

    publication = await service.publications.for_video(video.id)
    assert publication is not None
    assert publication.status == PublicationStatus.PUBLISHED.value
    assert video.status == VideoStatus.PUBLISHED.value

    # The rendered artefact is retrievable through storage.
    url = await service.artifact_url(run, "render")
    assert url is not None


async def test_artifact_url_is_none_for_a_stage_with_no_artifact(
    session: AsyncSession,
) -> None:
    video = await _make_video(session)
    service = VideoPipelineService(session)
    run = await service.start(video.id)
    assert await service.artifact_url(run, "render") is None


async def test_a_failed_run_records_why(session: AsyncSession) -> None:
    video = await _make_video(session)
    service = VideoPipelineService(session)
    run = await service.start(video.id)

    await service.fail(run.id, "renderer ran out of disk")
    assert run.stage == PipelineStage.FAILED.value
    assert run.error == "renderer ran out of disk"
    assert run.finished_at is not None
