"""Enumerations for Phase 03 domain models (stored as strings)."""

from __future__ import annotations

from enum import StrEnum


class ProjectStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"
    DRAFT = "draft"


class VideoStatus(StrEnum):
    DRAFT = "draft"
    RESEARCHING = "researching"
    SCRIPTING = "scripting"
    RENDERING = "rendering"
    READY = "ready"
    PUBLISHED = "published"
    FAILED = "failed"


class MediaStatus(StrEnum):
    UPLOADING = "uploading"
    READY = "ready"
    PROCESSING = "processing"
    FAILED = "failed"


class WorkflowExecutionStatus(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class FeatureFlagScope(StrEnum):
    GLOBAL = "global"
    ORGANIZATION = "organization"
    USER = "user"
