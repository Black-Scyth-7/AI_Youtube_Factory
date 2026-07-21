"""Security primitives: password hashing, JWT, opaque tokens, permissions."""

from app.security.jwt import (
    AccessTokenClaims,
    create_access_token,
    decode_access_token,
)
from app.security.password import (
    hash_password,
    needs_rehash,
    validate_password_policy,
    verify_password,
)
from app.security.permissions import (
    ALL_PERMISSIONS,
    DEFAULT_ROLE_PERMISSIONS,
    PERMISSIONS,
)
from app.security.tokens import generate_api_key, generate_token, hash_token

__all__ = [
    "ALL_PERMISSIONS",
    "DEFAULT_ROLE_PERMISSIONS",
    "PERMISSIONS",
    "AccessTokenClaims",
    "create_access_token",
    "decode_access_token",
    "generate_api_key",
    "generate_token",
    "hash_password",
    "hash_token",
    "needs_rehash",
    "validate_password_policy",
    "verify_password",
]
