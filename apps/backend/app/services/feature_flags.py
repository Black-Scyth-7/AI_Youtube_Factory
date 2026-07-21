"""Feature-flag service.

Evaluates flags with global/organization/user scope and percentage rollout.
Rollout is deterministic per subject (hash of key+subject), so a subject's
bucket is stable across requests. Results are cached briefly.
"""

from __future__ import annotations

import hashlib
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.cache import get_cache
from app.models.domain_enums import FeatureFlagScope
from app.models.infra import FeatureFlag
from app.repositories.infra import FeatureFlagRepository

_CACHE_NS = "feature_flags"


class FeatureFlagService:
    """Creates and evaluates feature flags."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = FeatureFlagRepository(session)
        self.cache = get_cache()

    async def set_flag(
        self,
        *,
        key: str,
        enabled: bool,
        scope: FeatureFlagScope = FeatureFlagScope.GLOBAL,
        rollout_percentage: int = 100,
        targets: list[str] | None = None,
        description: str | None = None,
    ) -> FeatureFlag:
        """Create or update a feature flag."""
        flag = await self.repo.get_by_key(key)
        if flag is None:
            flag = FeatureFlag(key=key)
            self.session.add(flag)
        flag.enabled = enabled
        flag.scope = scope.value
        flag.rollout_percentage = max(0, min(rollout_percentage, 100))
        flag.targets = targets or []
        flag.description = description
        await self.session.flush()
        await self.cache.delete(_CACHE_NS, key)
        return flag

    async def is_enabled(
        self,
        key: str,
        *,
        organization_id: uuid.UUID | None = None,
        user_id: uuid.UUID | None = None,
    ) -> bool:
        """Evaluate a flag for an optional org/user subject."""
        flag = await self.repo.get_by_key(key)
        if flag is None or not flag.enabled:
            return False

        # Global flags apply to everyone, subject to percentage rollout.
        if flag.scope == FeatureFlagScope.GLOBAL.value:
            return self._in_rollout(key, "global", flag.rollout_percentage)

        # Org/user-scoped flags require a matching subject.
        if flag.scope == FeatureFlagScope.ORGANIZATION.value:
            subject = str(organization_id) if organization_id else None
        else:
            subject = str(user_id) if user_id else None
        if subject is None:
            return False

        # An explicit target list is an allowlist (rollout is ignored).
        if flag.targets:
            return subject in flag.targets
        return self._in_rollout(key, subject, flag.rollout_percentage)

    @staticmethod
    def _in_rollout(key: str, subject: str, percentage: int) -> bool:
        if percentage >= 100:
            return True
        if percentage <= 0:
            return False
        digest = hashlib.sha256(f"{key}:{subject}".encode()).hexdigest()
        bucket = int(digest[:8], 16) % 100
        return bucket < percentage
