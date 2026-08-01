"""Public API payloads.

Deliberately separate from the internal ``app/schemas`` models. These are a
published contract: once a third party depends on them, a field cannot be
renamed because an internal model was refactored. Sharing the internal schemas
would make every internal rename a breaking change nobody noticed making.

The trade is duplication, which is the cheaper mistake.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PublicMeta(BaseModel):
    """Pagination metadata."""

    total: int
    page: int
    size: int
    has_next: bool


class PublicList[T](BaseModel):
    """A page of results.

    Always an object, never a bare array: a top-level array cannot grow a
    field, so adding pagination later would be a breaking change.
    """

    data: list[T]
    meta: PublicMeta


class KeyInfo(BaseModel):
    """Who the presented key belongs to and what it may do."""

    key_id: uuid.UUID
    name: str
    organization_id: uuid.UUID | None
    scopes: list[str]


class PublicChannel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    youtube_channel_id: str | None = None
    handle: str | None = None
    is_connected: bool
    created_at: datetime


class PublicVideo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    channel_id: uuid.UUID | None = None
    title: str
    description: str | None = None
    status: str
    created_at: datetime
    updated_at: datetime


class PublicVideoCreate(BaseModel):
    """Create a video."""

    project_id: uuid.UUID
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=5000)
    channel_id: uuid.UUID | None = None


class PublicPipelineRun(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    video_id: uuid.UUID
    stage: str
    error: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    #: Artifact metadata by stage. Storage keys are omitted — they are internal
    #: addresses, and a signed URL is issued separately.
    artifacts: dict[str, dict[str, object]] = Field(default_factory=dict)


class PublicUsage(BaseModel):
    metric: str
    used: float
    limit: int | None = None
    remaining: int | None = None
    exceeded: bool = False


class PublicError(BaseModel):
    """The error envelope, documented so clients can rely on its shape."""

    code: str
    message: str
    details: dict[str, object] | None = None
