"""Standardized API response envelope.

All successful list/detail responses can be wrapped in :class:`ApiResponse` so
clients get a consistent ``{data, meta}`` shape. Errors use the separate
``ErrorResponse`` envelope from :mod:`app.schemas.common`.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from app.core.api.pagination import Page, PageMeta


class ResponseMeta(BaseModel):
    """Optional metadata attached to a response (e.g. pagination)."""

    pagination: PageMeta | None = None


class ApiResponse[T](BaseModel):
    """A consistent success envelope: ``{"data": ..., "meta": ...}``."""

    data: T
    meta: ResponseMeta | None = None


def paginated[T](items: list[T], page: Page[Any]) -> ApiResponse[list[T]]:
    """Wrap serialized ``items`` and a :class:`Page` into an API response."""
    return ApiResponse(
        data=items,
        meta=ResponseMeta(
            pagination=PageMeta(
                total=page.total,
                page=page.page,
                size=page.size,
                pages=page.pages,
                has_next=page.has_next,
                has_prev=page.has_prev,
            )
        ),
    )
