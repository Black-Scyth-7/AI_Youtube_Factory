"""JWT access-token encoding and decoding.

Access tokens are short-lived, signed JWTs (HS256 by default). Refresh tokens are
*not* JWTs — they are opaque, hashed, and rotated in the database (see
``app.security.tokens`` and the token service). This module handles only the
stateless access token.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from app.config import settings
from app.exceptions.base import UnauthorizedError


@dataclass(slots=True, frozen=True)
class AccessTokenClaims:
    """Decoded, validated access-token claims."""

    subject: uuid.UUID
    session_id: uuid.UUID
    jti: uuid.UUID
    expires_at: datetime


def create_access_token(*, user_id: uuid.UUID, session_id: uuid.UUID) -> str:
    """Create a signed access token for ``user_id`` bound to ``session_id``."""
    now = datetime.now(UTC)
    expire = now + timedelta(minutes=settings.access_token_expire_minutes)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "sid": str(session_id),
        "jti": str(uuid.uuid4()),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "iss": settings.jwt_issuer,
        "type": "access",
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> AccessTokenClaims:
    """Decode and validate an access token.

    Raises:
        UnauthorizedError: If the token is expired, malformed, or the wrong type.
    """
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            issuer=settings.jwt_issuer,
            options={"require": ["exp", "sub", "sid", "jti"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise UnauthorizedError("Access token has expired.") from exc
    except jwt.InvalidTokenError as exc:
        raise UnauthorizedError("Invalid access token.") from exc

    if payload.get("type") != "access":
        raise UnauthorizedError("Invalid token type.")

    try:
        return AccessTokenClaims(
            subject=uuid.UUID(payload["sub"]),
            session_id=uuid.UUID(payload["sid"]),
            jti=uuid.UUID(payload["jti"]),
            expires_at=datetime.fromtimestamp(payload["exp"], tz=UTC),
        )
    except (KeyError, ValueError) as exc:
        raise UnauthorizedError("Malformed token claims.") from exc
