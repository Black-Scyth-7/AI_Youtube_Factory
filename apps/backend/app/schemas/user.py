"""User and profile schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    username: str
    display_name: str | None
    avatar_url: str | None
    is_active: bool
    is_verified: bool
    is_superuser: bool
    timezone: str
    locale: str
    last_login: datetime | None
    created_at: datetime


class UserUpdateRequest(BaseModel):
    display_name: str | None = Field(default=None, max_length=128)
    avatar_url: str | None = Field(default=None, max_length=1024)
    timezone: str | None = Field(default=None, max_length=64)
    locale: str | None = Field(default=None, max_length=16)


class ProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    bio: str | None
    company: str | None
    website: str | None
    location: str | None


class ProfileUpdateRequest(BaseModel):
    bio: str | None = Field(default=None, max_length=2048)
    company: str | None = Field(default=None, max_length=255)
    website: str | None = Field(default=None, max_length=1024)
    location: str | None = Field(default=None, max_length=255)
