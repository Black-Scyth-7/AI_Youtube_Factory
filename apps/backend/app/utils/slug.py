"""Slug generation helpers."""

from __future__ import annotations

import re
import secrets

_NON_SLUG = re.compile(r"[^a-z0-9]+")


def slugify(value: str) -> str:
    """Return a lowercase, hyphenated slug derived from ``value``."""
    slug = _NON_SLUG.sub("-", value.strip().lower()).strip("-")
    return slug or "org"


def unique_suffix(length: int = 6) -> str:
    """Return a short random suffix for disambiguating slugs."""
    return secrets.token_hex(length // 2)
