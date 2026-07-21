"""Feature-flag routes: superuser management + per-user evaluation."""

from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.dependencies.auth import CurrentUser, DbSession, require_superuser
from app.models.domain_enums import FeatureFlagScope
from app.models.user import User
from app.schemas.content import (
    FeatureFlagEvaluation,
    FeatureFlagResponse,
    FeatureFlagSetRequest,
)
from app.services.feature_flags import FeatureFlagService

router = APIRouter(prefix="/feature-flags", tags=["feature-flags"])


@router.put("", response_model=FeatureFlagResponse, status_code=status.HTTP_200_OK)
async def set_feature_flag(
    body: FeatureFlagSetRequest,
    session: DbSession,
    _: User = Depends(require_superuser),
) -> FeatureFlagResponse:
    """Create or update a feature flag (superuser only)."""
    flag = await FeatureFlagService(session).set_flag(
        key=body.key,
        enabled=body.enabled,
        scope=FeatureFlagScope(body.scope),
        rollout_percentage=body.rollout_percentage,
        targets=body.targets,
        description=body.description,
    )
    return FeatureFlagResponse.model_validate(flag)


@router.get("/{key}", response_model=FeatureFlagEvaluation)
async def evaluate_feature_flag(
    key: str, user: CurrentUser, session: DbSession
) -> FeatureFlagEvaluation:
    """Evaluate a feature flag for the current user."""
    enabled = await FeatureFlagService(session).is_enabled(key, user_id=user.id)
    return FeatureFlagEvaluation(key=key, enabled=enabled)
