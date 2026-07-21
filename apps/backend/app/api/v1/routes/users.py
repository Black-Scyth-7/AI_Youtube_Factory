"""Current-user and profile routes."""

from __future__ import annotations

from fastapi import APIRouter

from app.dependencies.auth import CurrentUser, DbSession
from app.schemas.user import (
    ProfileResponse,
    ProfileUpdateRequest,
    UserResponse,
    UserUpdateRequest,
)
from app.services.user import UserService

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserResponse)
async def get_me(user: CurrentUser) -> UserResponse:
    """Return the authenticated user."""
    return UserResponse.model_validate(user)


@router.patch("/me", response_model=UserResponse)
async def update_me(
    body: UserUpdateRequest, user: CurrentUser, session: DbSession
) -> UserResponse:
    """Update the authenticated user's basic fields."""
    updated = await UserService(session).update_user(
        user, **body.model_dump(exclude_unset=True)
    )
    return UserResponse.model_validate(updated)


@router.get("/profile", response_model=ProfileResponse)
async def get_profile(user: CurrentUser, session: DbSession) -> ProfileResponse:
    """Return (creating if needed) the authenticated user's profile."""
    profile = await UserService(session).get_or_create_profile(user.id)
    return ProfileResponse.model_validate(profile)


@router.patch("/profile", response_model=ProfileResponse)
async def update_profile(
    body: ProfileUpdateRequest, user: CurrentUser, session: DbSession
) -> ProfileResponse:
    """Update the authenticated user's profile."""
    profile = await UserService(session).update_profile(
        user.id, **body.model_dump(exclude_unset=True)
    )
    return ProfileResponse.model_validate(profile)
