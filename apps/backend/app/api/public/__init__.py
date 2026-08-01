"""The public, versioned API for third-party integrations.

Separate from ``app/api/v1``, which serves this product's own frontend and
changes whenever the product does. What is published here is a contract: it is
versioned in the path, has its own payload models, and is authenticated by
scoped API key rather than by session.
"""

from __future__ import annotations

from app.api.public.v1 import router as public_v1_router

__all__ = ["public_v1_router"]
