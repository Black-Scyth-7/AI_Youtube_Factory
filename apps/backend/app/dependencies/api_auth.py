"""Authentication for the public API.

The public API is authenticated by API key, not by session token. A key is a
long-lived credential held by a machine, so it differs from a session in ways
that matter here:

* It carries **scopes**, which narrow what its owner can do. A key never widens
  them — the owner's RBAC permissions still apply on top.
* It has no refresh cycle, so revocation and expiry are checked on every call.
* It is rate-limited per key rather than per IP: many keys share one NAT
  address, and one noisy integration should not throttle everyone behind it.

``ApiKeyService.authenticate`` already existed and nothing called it; keys could
be created and listed but could not authenticate anything.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.dependencies.auth import DbSession
from app.exceptions.base import ForbiddenError, UnauthorizedError
from app.models.api_key import ApiKey
from app.security.api_scopes import ALL_SCOPES
from app.services.api_key import ApiKeyService

_bearer = HTTPBearer(auto_error=False, description="API key")


@dataclass(frozen=True, slots=True)
class ApiPrincipal:
    """The identity behind a public-API request."""

    key_id: uuid.UUID
    user_id: uuid.UUID
    organization_id: uuid.UUID | None
    scopes: frozenset[str]
    name: str

    def has(self, scope: str) -> bool:
        return scope in self.scopes

    @classmethod
    def from_key(cls, key: ApiKey) -> ApiPrincipal:
        # Unknown scopes are dropped rather than trusted: the catalogue may
        # have changed since the key was issued, and a scope that no longer
        # exists must not act as a wildcard.
        granted = frozenset(s for s in (key.scopes or []) if s in ALL_SCOPES)
        return cls(
            key_id=key.id,
            user_id=key.user_id,
            organization_id=key.organization_id,
            scopes=granted,
            name=key.name,
        )


async def get_api_principal(
    request: Request,
    session: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)] = None,
    x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None,
) -> ApiPrincipal:
    """Resolve the API key presented on the request.

    Accepts ``Authorization: Bearer <key>`` or ``X-API-Key: <key>``. Both are in
    wide use by API clients, and rejecting one of them buys nothing.

    Raises:
        UnauthorizedError: If no key is presented, or it is invalid, revoked, or
            expired.
    """
    raw = credentials.credentials if credentials else x_api_key
    if not raw:
        raise UnauthorizedError(
            "An API key is required. Send it as 'Authorization: Bearer <key>' "
            "or 'X-API-Key: <key>'."
        )

    key = await ApiKeyService(session).authenticate(raw.strip())
    principal = ApiPrincipal.from_key(key)
    # Stashed for the rate limiter, which runs as middleware and has no access
    # to resolved dependencies.
    request.state.api_principal = principal
    return principal


ApiKeyPrincipal = Annotated[ApiPrincipal, Depends(get_api_principal)]


def require_scope(scope: str):  # type: ignore[no-untyped-def]
    """Dependency requiring ``scope`` on the presented key.

    Fails closed on an unknown scope name: a typo in a route would otherwise
    require a scope nothing can hold, or — worse, if it were ignored — require
    nothing at all.
    """
    if scope not in ALL_SCOPES:
        raise ValueError(f"Unknown API scope: {scope!r}")

    async def _dependency(principal: ApiKeyPrincipal) -> ApiPrincipal:
        if not principal.has(scope):
            raise ForbiddenError(
                f"This API key does not have the '{scope}' scope.",
                details={"required": scope, "granted": sorted(principal.scopes)},
            )
        return principal

    return _dependency


def require_organization(principal: ApiPrincipal) -> uuid.UUID:
    """The organization a key is bound to.

    A key without one cannot be used against organization-scoped data: there is
    nothing to scope the query to, and defaulting to "all of them" would turn a
    narrow key into a tenant-wide read.
    """
    if principal.organization_id is None:
        raise ForbiddenError(
            "This API key is not bound to an organization and cannot access "
            "organization data. Create a key with an organization to use these "
            "endpoints."
        )
    return principal.organization_id
