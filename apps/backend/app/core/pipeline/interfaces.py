"""Provider contracts for the video pipeline's external services.

The pipeline needs four things it cannot do itself: turn a script into speech,
turn assets into a video file, publish to a platform, and read back how the
published video performed. Each is a Protocol with a deterministic mock, exactly
as the LLM framework does — so the whole pipeline runs offline, and real
providers slot in without the pipeline code knowing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from typing import Any, Protocol, runtime_checkable


class ProviderKind(StrEnum):
    """The external capabilities the pipeline depends on."""

    SPEECH = "speech"
    RENDER = "render"
    PUBLISH = "publish"
    ANALYTICS = "analytics"


@dataclass(slots=True, frozen=True)
class SpeechResult:
    """Synthesised narration, already written to storage."""

    storage_key: str
    duration_seconds: float
    voice: str
    size_bytes: int


@dataclass(slots=True, frozen=True)
class RenderResult:
    """A rendered video file, already written to storage."""

    storage_key: str
    duration_seconds: float
    width: int
    height: int
    size_bytes: int


@dataclass(slots=True, frozen=True)
class PublishResult:
    """The outcome of publishing to a platform."""

    external_id: str
    url: str
    published_at: str


@dataclass(slots=True, frozen=True)
class AnalyticsSnapshot:
    """One day's metrics for a published video."""

    measured_on: date
    views: int = 0
    likes: int = 0
    comments: int = 0
    watch_time_seconds: int = 0
    impressions: int = 0
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def click_through_rate(self) -> float:
        """Views per impression. Zero impressions means no data, not zero rate."""
        return self.views / self.impressions if self.impressions else 0.0


@runtime_checkable
class SpeechProvider(Protocol):
    """Text to narration audio."""

    slug: str

    async def synthesize(
        self, text: str, *, voice: str = "default", storage_key: str
    ) -> SpeechResult: ...


@runtime_checkable
class RenderProvider(Protocol):
    """Assets to a finished video file."""

    slug: str

    async def render(
        self,
        *,
        script: str,
        audio_key: str | None,
        storage_key: str,
        options: dict[str, Any] | None = None,
    ) -> RenderResult: ...


@runtime_checkable
class PublishProvider(Protocol):
    """Upload to a destination platform."""

    slug: str

    async def publish(
        self,
        *,
        video_key: str,
        title: str,
        description: str | None,
        tags: list[str] | None = None,
        options: dict[str, Any] | None = None,
    ) -> PublishResult: ...


@runtime_checkable
class AnalyticsProvider(Protocol):
    """Read performance back from the platform."""

    slug: str

    async def fetch(
        self, *, external_id: str, on: date | None = None
    ) -> AnalyticsSnapshot: ...
