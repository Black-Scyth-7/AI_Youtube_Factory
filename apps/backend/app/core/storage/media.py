"""Media file utilities: hashing, MIME detection, and validation.

Provides content hashing for deduplication, MIME-type guessing, and an allowlist
validator. Preview/thumbnail generation is defined as an interface for future
media-processing implementations.
"""

from __future__ import annotations

import hashlib
import mimetypes
from typing import Protocol

from app.exceptions.base import ValidationError

# Allowed upload MIME types by category (extended in later phases).
ALLOWED_MIME_TYPES: frozenset[str] = frozenset(
    {
        "image/png",
        "image/jpeg",
        "image/webp",
        "image/gif",
        "video/mp4",
        "video/webm",
        "audio/mpeg",
        "audio/wav",
        "audio/webm",
        "application/pdf",
        "text/plain",
        "application/json",
    }
)


def compute_sha256(data: bytes) -> str:
    """Return the hex SHA-256 of ``data`` (used for deduplication)."""
    return hashlib.sha256(data).hexdigest()


def guess_mime_type(filename: str, fallback: str = "application/octet-stream") -> str:
    """Guess a MIME type from a filename."""
    mime, _ = mimetypes.guess_type(filename)
    return mime or fallback


def validate_mime_type(mime: str) -> None:
    """Raise if ``mime`` is not in the upload allowlist."""
    if mime not in ALLOWED_MIME_TYPES:
        raise ValidationError(
            "Unsupported file type.",
            details={"mime": mime, "allowed": sorted(ALLOWED_MIME_TYPES)},
        )


class PreviewGenerator(Protocol):
    """Interface for future preview/thumbnail generators."""

    async def generate_preview(self, key: str, mime: str) -> str | None:
        """Return a preview object key, or ``None`` if unsupported."""
        ...
