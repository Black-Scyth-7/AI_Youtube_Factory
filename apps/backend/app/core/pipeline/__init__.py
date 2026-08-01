"""Video pipeline provider layer.

Four external capabilities — speech, render, publish, analytics — each behind a
Protocol with a deterministic mock, so the pipeline runs end to end offline.
"""

from app.core.pipeline.interfaces import (
    AnalyticsProvider,
    AnalyticsSnapshot,
    ProviderKind,
    PublishProvider,
    PublishResult,
    RenderProvider,
    RenderResult,
    SpeechProvider,
    SpeechResult,
)
from app.core.pipeline.mock import (
    MockAnalyticsProvider,
    MockPublishProvider,
    MockRenderProvider,
    MockSpeechProvider,
)
from app.core.pipeline.registry import (
    available_providers,
    get_provider,
    register_provider,
    reset_providers,
)

__all__ = [
    "AnalyticsProvider",
    "AnalyticsSnapshot",
    "MockAnalyticsProvider",
    "MockPublishProvider",
    "MockRenderProvider",
    "MockSpeechProvider",
    "ProviderKind",
    "PublishProvider",
    "PublishResult",
    "RenderProvider",
    "RenderResult",
    "SpeechProvider",
    "SpeechResult",
    "available_providers",
    "get_provider",
    "register_provider",
    "reset_providers",
]
