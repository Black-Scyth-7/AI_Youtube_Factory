"""Unit tests for password, JWT, and token primitives."""

from __future__ import annotations

import uuid

import pytest
from app.exceptions.base import UnauthorizedError, ValidationError
from app.security.jwt import create_access_token, decode_access_token
from app.security.password import (
    hash_password,
    validate_password_policy,
    verify_password,
)
from app.security.permissions import ALL_PERMISSIONS, DEFAULT_ROLE_PERMISSIONS
from app.security.tokens import generate_api_key, generate_token, hash_token


def test_password_hash_roundtrip() -> None:
    h = hash_password("Str0ng!Passw0rd")
    assert h != "Str0ng!Passw0rd"
    assert verify_password("Str0ng!Passw0rd", h)
    assert not verify_password("wrong", h)


@pytest.mark.parametrize(
    "bad",
    ["short1!A", "alllowercase1!", "ALLUPPERCASE1!", "NoNumbers!!", "NoSpecial123"],
)
def test_password_policy_rejects_weak(bad: str) -> None:
    with pytest.raises(ValidationError):
        validate_password_policy(bad)


def test_password_policy_rejects_common() -> None:
    with pytest.raises(ValidationError):
        validate_password_policy("Password123")


def test_access_token_roundtrip() -> None:
    uid, sid = uuid.uuid4(), uuid.uuid4()
    token = create_access_token(user_id=uid, session_id=sid)
    claims = decode_access_token(token)
    assert claims.subject == uid
    assert claims.session_id == sid


def test_access_token_rejects_tampered() -> None:
    token = create_access_token(user_id=uuid.uuid4(), session_id=uuid.uuid4())
    with pytest.raises(UnauthorizedError):
        decode_access_token(token + "x")


def test_token_hash_is_deterministic() -> None:
    t = generate_token()
    assert hash_token(t) == hash_token(t)
    assert generate_token() != generate_token()


def test_api_key_generation() -> None:
    full, prefix, secret_hash = generate_api_key()
    assert full.startswith(prefix + ".")
    secret = full.split(".", 1)[1]
    assert hash_token(secret) == secret_hash


def test_owner_has_all_permissions() -> None:
    from app.models.enums import SystemRole

    assert DEFAULT_ROLE_PERMISSIONS[SystemRole.OWNER] == ALL_PERMISSIONS
    assert "analytics.read" in DEFAULT_ROLE_PERMISSIONS[SystemRole.VIEWER]
    assert "billing.manage" not in DEFAULT_ROLE_PERMISSIONS[SystemRole.EDITOR]
