"""Public API, version 1.

A small, stable surface for third-party integrations, authenticated by API key
and scoped by that key. Versioned in the path (``/api/public/v1``) and separate
from the internal ``/api/v1``, which changes whenever the product does.

**Tenancy is checked explicitly on every request.** A key names an
organization, and every object reached through these routes is verified to
belong to it before anything is returned. Relying on an unguessable id instead
is how one customer reads another's data.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select

from app.api.public.schemas import (
    KeyInfo,
    PublicChannel,
    PublicList,
    PublicMeta,
    PublicPipelineRun,
    PublicUsage,
    PublicVideo,
    PublicVideoCreate,
)
from app.core.api.pagination import FilterSpec, PageParams
from app.dependencies.api_auth import (
    ApiKeyPrincipal,
    ApiPrincipal,
    require_organization,
    require_scope,
)
from app.dependencies.auth import DbSession
from app.exceptions.base import NotFoundError
from app.models.billing import Subscription
from app.models.pipeline import PipelineRun
from app.models.video import Video
from app.models.workspace import Project, Workspace
from app.repositories.billing import PlanRepository, SubscriptionRepository
from app.repositories.content import ChannelRepository, VideoRepository
from app.services.billing import UsageService

router = APIRouter(prefix="/api/public/v1", tags=["public-api"])

PageQuery = Annotated[int, Query(ge=1, description="1-based page number")]
SizeQuery = Annotated[int, Query(ge=1, le=100, description="Items per page")]


def _meta(total: int, params: PageParams) -> PublicMeta:
    return PublicMeta(
        total=total,
        page=params.page,
        size=params.limit,
        has_next=params.page * params.limit < total,
    )


async def _project_ids_for_org(session: DbSession, org_id: uuid.UUID) -> list[uuid.UUID]:
    """Every project belonging to ``org_id``.

    Projects hang off workspaces, which hold the organization, so the link is a
    join rather than a column. Resolving it once here keeps the tenancy check in
    a single place instead of repeated (and eventually forgotten) per route.
    """
    result = await session.execute(
        select(Project.id)
        .join(Workspace, Project.workspace_id == Workspace.id)
        .where(Workspace.organization_id == org_id, Project.deleted_at.is_(None))
    )
    return list(result.scalars().all())


async def _owned_video(
    session: DbSession, video_id: uuid.UUID, org_id: uuid.UUID
) -> Video:
    """Load a video, or 404 if it is not this organization's.

    Deliberately 404 and not 403: telling an unauthorized caller that an id
    exists is itself a disclosure.
    """
    video = await VideoRepository(session).get(video_id)
    if video is None:
        raise NotFoundError("Video not found.")
    if video.project_id not in set(await _project_ids_for_org(session, org_id)):
        raise NotFoundError("Video not found.")
    return video


# -- Identity -----------------------------------------------------------------
@router.get("/me", response_model=KeyInfo, summary="Describe the presented key")
async def whoami(principal: ApiKeyPrincipal) -> KeyInfo:
    """What this key is and what it can do.

    Requires authentication but no scope. It is how a client discovers which
    scopes it holds, so gating it behind one of them means a key that lacks
    that scope cannot even find out what it can do — and cannot tell a
    revoked key from a missing grant.
    """
    return KeyInfo(
        key_id=principal.key_id,
        name=principal.name,
        organization_id=principal.organization_id,
        scopes=sorted(principal.scopes),
    )


# -- Channels -----------------------------------------------------------------
@router.get(
    "/channels", response_model=PublicList[PublicChannel], summary="List channels"
)
async def list_channels(
    session: DbSession,
    principal: Annotated[ApiPrincipal, Depends(require_scope("channel:read"))],
    page: PageQuery = 1,
    size: SizeQuery = 20,
) -> PublicList[PublicChannel]:
    """Channels across every project in the key's organization."""
    org_id = require_organization(principal)
    params = PageParams(page=page, size=size)
    project_ids = await _project_ids_for_org(session, org_id)
    if not project_ids:
        return PublicList[PublicChannel](data=[], meta=_meta(0, params))

    result = await ChannelRepository(session).paginate(
        params, filters=[FilterSpec("project_id", "in", project_ids)]
    )
    return PublicList[PublicChannel](
        data=[PublicChannel.model_validate(c) for c in result.items],
        meta=_meta(result.total, params),
    )


# -- Videos -------------------------------------------------------------------
@router.get("/videos", response_model=PublicList[PublicVideo], summary="List videos")
async def list_videos(
    session: DbSession,
    principal: Annotated[ApiPrincipal, Depends(require_scope("video:read"))],
    page: PageQuery = 1,
    size: SizeQuery = 20,
    project_id: uuid.UUID | None = None,
    video_status: Annotated[str | None, Query(alias="status", max_length=32)] = None,
) -> PublicList[PublicVideo]:
    """Videos in the key's organization, newest first."""
    org_id = require_organization(principal)
    params = PageParams(page=page, size=size)

    project_ids = await _project_ids_for_org(session, org_id)
    if project_id is not None:
        # Intersected rather than trusted: a project id from the request that
        # is not this organization's must narrow to nothing, not widen.
        project_ids = [p for p in project_ids if p == project_id]
    if not project_ids:
        return PublicList[PublicVideo](data=[], meta=_meta(0, params))

    filters = [FilterSpec("project_id", "in", project_ids)]
    if video_status:
        filters.append(FilterSpec("status", "eq", video_status))

    result = await VideoRepository(session).paginate(params, filters=filters)
    return PublicList[PublicVideo](
        data=[PublicVideo.model_validate(v) for v in result.items],
        meta=_meta(result.total, params),
    )


@router.get("/videos/{video_id}", response_model=PublicVideo, summary="Get a video")
async def get_video(
    video_id: uuid.UUID,
    session: DbSession,
    principal: Annotated[ApiPrincipal, Depends(require_scope("video:read"))],
) -> PublicVideo:
    org_id = require_organization(principal)
    return PublicVideo.model_validate(await _owned_video(session, video_id, org_id))


@router.post(
    "/videos", response_model=PublicVideo, status_code=201, summary="Create a video"
)
async def create_video(
    body: PublicVideoCreate,
    session: DbSession,
    principal: Annotated[ApiPrincipal, Depends(require_scope("video:write"))],
) -> PublicVideo:
    """Create a video in one of the organization's projects."""
    org_id = require_organization(principal)
    if body.project_id not in set(await _project_ids_for_org(session, org_id)):
        raise NotFoundError("Project not found.")

    video = Video(
        project_id=body.project_id,
        channel_id=body.channel_id,
        title=body.title,
        description=body.description,
    )
    await VideoRepository(session).add(video)
    return PublicVideo.model_validate(video)


# -- Pipeline -----------------------------------------------------------------
@router.get(
    "/videos/{video_id}/pipeline-runs",
    response_model=PublicList[PublicPipelineRun],
    summary="List pipeline runs for a video",
)
async def list_pipeline_runs(
    video_id: uuid.UUID,
    session: DbSession,
    principal: Annotated[ApiPrincipal, Depends(require_scope("pipeline:read"))],
    page: PageQuery = 1,
    size: SizeQuery = 20,
) -> PublicList[PublicPipelineRun]:
    org_id = require_organization(principal)
    await _owned_video(session, video_id, org_id)

    params = PageParams(page=page, size=size)
    total = int(
        await session.scalar(
            select(func.count())
            .select_from(PipelineRun)
            .where(PipelineRun.video_id == video_id)
        )
        or 0
    )
    rows = await session.execute(
        select(PipelineRun)
        .where(PipelineRun.video_id == video_id)
        .order_by(PipelineRun.created_at.desc())
        .limit(params.limit)
        .offset(params.offset)
    )
    runs = list(rows.scalars().all())
    return PublicList[PublicPipelineRun](
        data=[_public_run(r) for r in runs], meta=_meta(total, params)
    )


def _public_run(run: PipelineRun) -> PublicPipelineRun:
    """Strip internal storage addresses out of artifact metadata."""
    artifacts = {
        stage: {k: v for k, v in (data or {}).items() if k != "storage_key"}
        for stage, data in (run.artifacts or {}).items()
        if isinstance(data, dict)
    }
    return PublicPipelineRun(
        id=run.id,
        video_id=run.video_id,
        stage=run.stage,
        error=run.error,
        started_at=run.started_at,
        finished_at=run.finished_at,
        artifacts=artifacts,
    )


# -- Usage --------------------------------------------------------------------
@router.get("/usage", response_model=list[PublicUsage], summary="Usage this period")
async def get_usage(
    session: DbSession,
    principal: Annotated[ApiPrincipal, Depends(require_scope("usage:read"))],
) -> list[PublicUsage]:
    """Consumption against the plan's quotas for the current billing period."""
    org_id = require_organization(principal)
    subscription: Subscription | None = await SubscriptionRepository(
        session
    ).get_active_for_organization(org_id)
    if subscription is None:
        return []

    plan = await PlanRepository(session).get(subscription.plan_id)
    if plan is None:
        return []

    usage = UsageService(session)
    out: list[PublicUsage] = []
    for metric, limit in sorted(plan.quotas.items()):
        used = float(
            await usage.repo.total_for_metric(
                org_id, metric, subscription.current_period_start.date()
            )
        )
        remaining = int(limit) - int(used)
        out.append(
            PublicUsage(
                metric=metric,
                used=used,
                limit=int(limit),
                remaining=max(remaining, 0),
                exceeded=remaining < 0,
            )
        )
    return out


__all__ = ["router"]
