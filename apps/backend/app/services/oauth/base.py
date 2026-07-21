"""OAuth provider abstraction.

Each provider builds an authorization URL, exchanges an authorization code for an
access token, and returns a normalized :class:`OAuthProfile`. Application code
depends only on :class:`OAuthClient`.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.models.enums import OAuthProvider


@dataclass(slots=True, frozen=True)
class OAuthProfile:
    """A normalized external identity."""

    provider: OAuthProvider
    account_id: str
    email: str | None
    name: str | None
    avatar_url: str | None
    access_token: str


class OAuthClient(ABC):
    """Base class for OAuth 2.0 identity providers."""

    provider: OAuthProvider

    @abstractmethod
    def authorization_url(self, state: str) -> str:
        """Return the provider authorization URL for the given ``state``."""

    @abstractmethod
    async def exchange_code(self, code: str) -> OAuthProfile:
        """Exchange an authorization ``code`` for a normalized profile."""
