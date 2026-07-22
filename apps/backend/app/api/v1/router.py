"""Aggregate router for API version 1."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.routes import (
    api_keys,
    auth,
    content,
    feature_flags,
    health,
    invitations,
    llm,
    meta,
    organizations,
    sessions,
    users,
)

api_v1_router = APIRouter()
api_v1_router.include_router(meta.router)
api_v1_router.include_router(health.router)
api_v1_router.include_router(auth.router)
api_v1_router.include_router(users.router)
api_v1_router.include_router(organizations.router)
api_v1_router.include_router(invitations.router)
api_v1_router.include_router(api_keys.router)
api_v1_router.include_router(sessions.router)
api_v1_router.include_router(content.router)
api_v1_router.include_router(feature_flags.router)
api_v1_router.include_router(llm.router)
