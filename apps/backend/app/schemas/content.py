"""Schemas for content-domain and infrastructure endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class WorkspaceCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    slug: str | None = Field(default=None, max_length=128, pattern=r"^[a-z0-9-]+$")


class WorkspaceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    name: str
    slug: str
    version: int
    created_at: datetime


class ProjectCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    slug: str | None = Field(default=None, max_length=128, pattern=r"^[a-z0-9-]+$")
    description: str | None = Field(default=None, max_length=2048)


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    workspace_id: uuid.UUID
    name: str
    slug: str
    description: str | None
    status: str
    version: int
    created_at: datetime


class VideoCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=512)
    description: str | None = None


class VideoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    channel_id: uuid.UUID | None
    title: str
    description: str | None
    status: str
    version: int
    created_at: datetime


class FeatureFlagSetRequest(BaseModel):
    key: str = Field(min_length=1, max_length=128)
    enabled: bool
    scope: str = "global"
    rollout_percentage: int = Field(default=100, ge=0, le=100)
    targets: list[str] = Field(default_factory=list)
    description: str | None = None


class FeatureFlagResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    key: str
    enabled: bool
    scope: str
    rollout_percentage: int


class FeatureFlagEvaluation(BaseModel):
    key: str
    enabled: bool
