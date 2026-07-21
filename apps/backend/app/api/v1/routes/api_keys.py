"""API key routes."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, status

from app.dependencies.auth import CurrentUser, DbSession
from app.schemas.organization import (
    ApiKeyCreatedResponse,
    ApiKeyCreateRequest,
    ApiKeyResponse,
)
from app.services.api_key import ApiKeyService

router = APIRouter(prefix="/api-keys", tags=["api-keys"])


@router.post(
    "", response_model=ApiKeyCreatedResponse, status_code=status.HTTP_201_CREATED
)
async def create_api_key(
    body: ApiKeyCreateRequest, user: CurrentUser, session: DbSession
) -> ApiKeyCreatedResponse:
    """Create an API key. The raw key is returned exactly once."""
    created = await ApiKeyService(session).create(
        user_id=user.id,
        name=body.name,
        scopes=body.scopes,
        expires_in_days=body.expires_in_days,
    )
    return ApiKeyCreatedResponse(
        **ApiKeyResponse.model_validate(created.api_key).model_dump(),
        key=created.raw_key,
    )


@router.get("", response_model=list[ApiKeyResponse])
async def list_api_keys(user: CurrentUser, session: DbSession) -> list[ApiKeyResponse]:
    """List the current user's API keys (secrets never included)."""
    keys = await ApiKeyService(session).list_for_user(user.id)
    return [ApiKeyResponse.model_validate(k) for k in keys]


@router.delete("/{key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    key_id: uuid.UUID, user: CurrentUser, session: DbSession
) -> None:
    """Revoke an API key."""
    await ApiKeyService(session).revoke(user_id=user.id, key_id=key_id)
