"""Pagination primitives shared by the repository and API layers.

Supports offset pagination (page/size) and opaque cursor pagination. The generic
:class:`Page` carries items plus metadata so callers get a consistent shape.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


@dataclass(slots=True, frozen=True)
class PageParams:
    """Offset-pagination request parameters."""

    page: int = 1
    size: int = DEFAULT_PAGE_SIZE

    @property
    def limit(self) -> int:
        return min(max(self.size, 1), MAX_PAGE_SIZE)

    @property
    def offset(self) -> int:
        return (max(self.page, 1) - 1) * self.limit


@dataclass(slots=True, frozen=True)
class SortParam:
    """A single sort instruction."""

    field: str
    descending: bool = False


@dataclass(slots=True)
class Page[T]:
    """A page of results plus pagination metadata."""

    items: list[T]
    total: int
    page: int
    size: int

    @property
    def pages(self) -> int:
        return (self.total + self.size - 1) // self.size if self.size else 0

    @property
    def has_next(self) -> bool:
        return self.page < self.pages

    @property
    def has_prev(self) -> bool:
        return self.page > 1


class PageMeta(BaseModel):
    """Serializable pagination metadata for API responses."""

    total: int
    page: int
    size: int
    pages: int
    has_next: bool
    has_prev: bool


def encode_cursor(payload: dict[str, Any]) -> str:
    """Encode an opaque, URL-safe cursor from a small payload."""
    raw = json.dumps(payload, separators=(",", ":"), default=str).encode()
    return base64.urlsafe_b64encode(raw).decode()


def decode_cursor(cursor: str) -> dict[str, Any]:
    """Decode an opaque cursor produced by :func:`encode_cursor`."""
    raw = base64.urlsafe_b64decode(cursor.encode())
    data: dict[str, Any] = json.loads(raw)
    return data


@dataclass(slots=True, frozen=True)
class FilterSpec:
    """A generic field filter for repository queries."""

    field: str
    op: str = "eq"  # eq | ne | gt | ge | lt | le | like | in
    value: Any = None
