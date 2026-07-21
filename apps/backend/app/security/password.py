"""Password hashing and policy enforcement.

Hashes use **Argon2id** via ``argon2-cffi``. Plaintext is never stored. The
policy enforces length and character-class requirements and rejects a small set
of common passwords. ``needs_rehash`` lets callers transparently upgrade hashes
when parameters change.
"""

from __future__ import annotations

import re

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from app.exceptions.base import ValidationError

# Argon2id with sensible interactive-login parameters.
_hasher = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)

MIN_LENGTH = 10
MAX_LENGTH = 128

# A minimal embedded denylist; production deployments layer a larger list.
_COMMON_PASSWORDS = frozenset(
    {
        "password",
        "password1",
        "password123",
        "12345678",
        "123456789",
        "qwerty123",
        "letmein123",
        "welcome123",
        "admin1234",
        "iloveyou1",
        "changeme123",
    }
)

_UPPER = re.compile(r"[A-Z]")
_LOWER = re.compile(r"[a-z]")
_DIGIT = re.compile(r"\d")
_SPECIAL = re.compile(r"[^A-Za-z0-9]")


def validate_password_policy(password: str) -> None:
    """Validate ``password`` against the policy, raising on failure.

    Raises:
        ValidationError: If the password violates any policy rule.
    """
    problems: list[str] = []
    if len(password) < MIN_LENGTH:
        problems.append(f"at least {MIN_LENGTH} characters")
    if len(password) > MAX_LENGTH:
        problems.append(f"at most {MAX_LENGTH} characters")
    if not _UPPER.search(password):
        problems.append("an uppercase letter")
    if not _LOWER.search(password):
        problems.append("a lowercase letter")
    if not _DIGIT.search(password):
        problems.append("a number")
    if not _SPECIAL.search(password):
        problems.append("a special character")
    if password.lower() in _COMMON_PASSWORDS:
        problems.append("a value that is not a common password")

    if problems:
        raise ValidationError(
            "Password does not meet the security policy.",
            details={"requirements": problems},
        )


def hash_password(password: str) -> str:
    """Validate the policy and return an Argon2id hash of ``password``."""
    validate_password_policy(password)
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Return ``True`` if ``password`` matches ``password_hash``.

    Verification is constant-time within Argon2 and never raises on mismatch.
    """
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    """Return ``True`` if ``password_hash`` should be re-hashed with current params."""
    try:
        return _hasher.check_needs_rehash(password_hash)
    except InvalidHashError:
        return True
