"""OAuth provider abstraction and factory."""

from __future__ import annotations

from app.exceptions.base import ServiceUnavailableError
from app.models.enums import OAuthProvider
from app.services.oauth.base import OAuthClient, OAuthProfile
from app.services.oauth.github import GitHubOAuthClient
from app.services.oauth.google import GoogleOAuthClient

_CLIENTS: dict[OAuthProvider, type[OAuthClient]] = {
    OAuthProvider.GOOGLE: GoogleOAuthClient,
    OAuthProvider.GITHUB: GitHubOAuthClient,
}


def get_oauth_client(provider: OAuthProvider) -> OAuthClient:
    """Return the OAuth client for ``provider``."""
    client_cls = _CLIENTS.get(provider)
    if client_cls is None:
        raise ServiceUnavailableError(f"OAuth provider '{provider}' is not supported.")
    return client_cls()


__all__ = [
    "GitHubOAuthClient",
    "GoogleOAuthClient",
    "OAuthClient",
    "OAuthProfile",
    "get_oauth_client",
]
