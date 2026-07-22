"""Symmetric encryption for secrets at rest.

Encrypts provider secrets (e.g. API keys) using Fernet (AES-128-CBC + HMAC). The
key is derived deterministically from ``settings.secret_key`` so no extra key
material is required in development; production should set a strong ``SECRET_KEY``.
"""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings


def _fernet() -> Fernet:
    # Derive a 32-byte urlsafe key from the app secret.
    digest = hashlib.sha256(settings.secret_key.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(plaintext: str) -> str:
    """Encrypt ``plaintext`` and return a urlsafe ciphertext string."""
    return _fernet().encrypt(plaintext.encode()).decode()


def decrypt_secret(ciphertext: str) -> str:
    """Decrypt a ciphertext produced by :func:`encrypt_secret`.

    Raises:
        ValueError: If the ciphertext is invalid or tampered with.
    """
    try:
        return _fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken as exc:
        raise ValueError("Failed to decrypt secret.") from exc
