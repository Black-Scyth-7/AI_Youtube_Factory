"""Opaque secret token generation and hashing.

Used for refresh tokens, email verification, password reset, invitations, and
API key secrets. Raw tokens are returned to the caller once; only the SHA-256
hash is persisted, so the database never holds a usable secret.
"""

from __future__ import annotations

import hashlib
import secrets


def generate_token(num_bytes: int = 32) -> str:
    """Return a URL-safe, cryptographically-random opaque token."""
    return secrets.token_urlsafe(num_bytes)


def hash_token(token: str) -> str:
    """Return the hex SHA-256 digest of ``token`` for storage/lookup."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def generate_api_key() -> tuple[str, str, str]:
    """Generate an API key.

    Returns a tuple of ``(full_key, prefix, secret_hash)`` where ``full_key`` is
    shown to the user exactly once, ``prefix`` is a non-secret identifier stored
    for lookup, and ``secret_hash`` is the value persisted.
    """
    prefix = "ayf_" + secrets.token_hex(4)
    secret = secrets.token_urlsafe(32)
    full_key = f"{prefix}.{secret}"
    return full_key, prefix, hash_token(secret)
