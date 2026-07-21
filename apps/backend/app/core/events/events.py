"""Built-in domain event types."""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from app.core.events.bus import Event


@dataclass(frozen=True, slots=True, kw_only=True)
class UserCreated(Event):
    user_id: uuid.UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class WorkspaceCreated(Event):
    workspace_id: uuid.UUID
    organization_id: uuid.UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class ProjectCreated(Event):
    project_id: uuid.UUID
    workspace_id: uuid.UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class VideoCreated(Event):
    video_id: uuid.UUID
    project_id: uuid.UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class WorkflowStarted(Event):
    execution_id: uuid.UUID
    workflow_id: uuid.UUID


@dataclass(frozen=True, slots=True, kw_only=True)
class RenderFinished(Event):
    video_id: uuid.UUID
    success: bool


@dataclass(frozen=True, slots=True, kw_only=True)
class UploadCompleted(Event):
    storage_key: str
    size_bytes: int
