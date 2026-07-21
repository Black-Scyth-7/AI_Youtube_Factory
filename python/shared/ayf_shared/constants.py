"""Shared constants and the canonical content-pipeline stage order."""

from __future__ import annotations

from enum import StrEnum
from typing import Final

SERVICE_NAMES: Final[tuple[str, ...]] = (
    "backend",
    "worker",
    "frontend",
    "admin",
)


class ContentStage(StrEnum):
    """Ordered stages of the AI video production pipeline.

    Mirrors the platform's end-to-end flow. Implemented incrementally in later
    phases; defined here so all services share one source of truth.
    """

    RESEARCH = "research"
    IDEA = "idea"
    OUTLINE = "outline"
    SCRIPT = "script"
    FACT_CHECK = "fact_check"
    STORYBOARD = "storyboard"
    SCENE_PLANNING = "scene_planning"
    IMAGE_GENERATION = "image_generation"
    VIDEO_GENERATION = "video_generation"
    VOICE_GENERATION = "voice_generation"
    EDITING = "editing"
    CAPTIONS = "captions"
    THUMBNAIL = "thumbnail"
    SEO = "seo"
    PUBLISHING = "publishing"
    ANALYTICS = "analytics"
    LEARNING = "learning"
