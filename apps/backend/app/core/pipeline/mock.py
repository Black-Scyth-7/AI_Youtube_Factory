"""Deterministic mock providers for the video pipeline.

Every value is derived from the input, so the same script always yields the same
duration and the same published id. That makes the pipeline testable end to end
without a TTS key, a renderer, or a YouTube account — the same reason the LLM
framework ships a mock provider.

Mocks write real bytes through the storage layer, so the storage path is
exercised too rather than stubbed out.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, date, datetime
from typing import Any

from app.core.pipeline.interfaces import (
    AnalyticsSnapshot,
    PublishResult,
    RenderResult,
    SpeechResult,
)
from app.core.storage import get_storage

#: Rough speaking pace, used to derive a plausible duration from a script.
WORDS_PER_MINUTE = 150


def _seeded(value: str) -> int:
    """A stable integer derived from ``value``.

    Deterministic across processes, unlike hash(), which is salted per run.
    """
    return int(hashlib.sha256(value.encode("utf-8")).hexdigest()[:8], 16)


def _estimate_duration(text: str) -> float:
    words = max(len(text.split()), 1)
    return round(words / WORDS_PER_MINUTE * 60, 2)


class MockSpeechProvider:
    """Writes a placeholder audio object and reports a plausible duration."""

    slug = "mock"

    async def synthesize(
        self, text: str, *, voice: str = "default", storage_key: str
    ) -> SpeechResult:
        payload = f"MOCK-AUDIO voice={voice}\n{text}".encode()
        storage = get_storage()
        stored = await storage.put(storage_key, payload, "audio/mpeg")
        return SpeechResult(
            storage_key=stored.key,
            duration_seconds=_estimate_duration(text),
            voice=voice,
            size_bytes=len(payload),
        )


class MockRenderProvider:
    """Writes a placeholder video object sized from its inputs."""

    slug = "mock"

    async def render(
        self,
        *,
        script: str,
        audio_key: str | None,
        storage_key: str,
        options: dict[str, Any] | None = None,
    ) -> RenderResult:
        settings = options or {}
        width = int(settings.get("width", 1920))
        height = int(settings.get("height", 1080))
        payload = f"MOCK-VIDEO {width}x{height} audio={audio_key}\n{script}".encode()
        storage = get_storage()
        stored = await storage.put(storage_key, payload, "video/mp4")
        return RenderResult(
            storage_key=stored.key,
            duration_seconds=_estimate_duration(script),
            width=width,
            height=height,
            size_bytes=len(payload),
        )


class MockPublishProvider:
    """Pretends to upload, returning a stable id derived from the video key."""

    slug = "mock"

    async def publish(
        self,
        *,
        video_key: str,
        title: str,
        description: str | None,
        tags: list[str] | None = None,
        options: dict[str, Any] | None = None,
    ) -> PublishResult:
        external_id = f"mock-{_seeded(video_key):08x}"
        return PublishResult(
            external_id=external_id,
            url=f"https://example.invalid/watch?v={external_id}",
            published_at=datetime.now(UTC).isoformat(),
        )


class MockAnalyticsProvider:
    """Returns stable, plausible metrics for a published id."""

    slug = "mock"

    async def fetch(
        self, *, external_id: str, on: date | None = None
    ) -> AnalyticsSnapshot:
        measured_on = on or datetime.now(UTC).date()
        seed = _seeded(f"{external_id}:{measured_on.isoformat()}")
        views = seed % 10_000
        impressions = views * 8 + 1
        return AnalyticsSnapshot(
            measured_on=measured_on,
            views=views,
            likes=views // 20,
            comments=views // 200,
            watch_time_seconds=views * 45,
            impressions=impressions,
        )
