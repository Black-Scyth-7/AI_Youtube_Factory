"""Aggregate router for API version 1."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.routes import health, meta

api_v1_router = APIRouter()
api_v1_router.include_router(meta.router)
api_v1_router.include_router(health.router)
