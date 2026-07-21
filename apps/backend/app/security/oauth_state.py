"""Signed OAuth ``state`` values for CSRF protection.

The state is an itsdangerous-signed, time-limited token binding the provider to
a random nonce. The callback verifies the signature before exchanging the code,
preventing forged authorization responses.
"""

from __future__ import annotations

import secrets

from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer

from app.config import settings
from app.exceptions.base import UnauthorizedError

_serializer = URLSafeTimedSerializer(settings.secret_key, salt="oauth-state")
_MAX_AGE_SECONDS = 600


def issue_state(provider: str) -> str:
    """Return a signed state token for ``provider``."""
    return _serializer.dumps({"provider": provider, "nonce": secrets.token_hex(8)})


def verify_state(state: str, provider: str) -> None:
    """Validate ``state`` for ``provider``; raise on mismatch or expiry."""
    try:
        data = _serializer.loads(state, max_age=_MAX_AGE_SECONDS)
    except SignatureExpired as exc:
        raise UnauthorizedError("OAuth state has expired.") from exc
    except BadSignature as exc:
        raise UnauthorizedError("Invalid OAuth state.") from exc
    if data.get("provider") != provider:
        raise UnauthorizedError("OAuth state provider mismatch.")
