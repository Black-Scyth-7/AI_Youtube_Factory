"""Workspace, project, and video routes (org-scoped, RBAC-guarded).

Demonstrates the reusable API framework: the standardized ``{data, meta}``
envelope with pagination metadata on list endpoints.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, status

from app.core.api import ApiResponse, PageParams, paginated
from app.dependencies.auth import CurrentUser, DbSession, require_permission
from app.models.user import User
from app.schemas.content import (
    ProjectCreateRequest,
    ProjectResponse,
    VideoCreateRequest,
    VideoResponse,
    WorkspaceCreateRequest,
    WorkspaceResponse,
)
from app.services.content import ProjectService, VideoService, WorkspaceService

router = APIRouter(prefix="/organizations/{organization_id}", tags=["content"])


# -- Workspaces ----------------------------------------------------------
@router.post(
    "/workspaces",
    response_model=WorkspaceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_workspace(
    organization_id: uuid.UUID,
    body: WorkspaceCreateRequest,
    user: CurrentUser,
    session: DbSession,
    _: User = Depends(require_permission("project.create")),
) -> WorkspaceResponse:
    workspace = await WorkspaceService(session).create(
        organization_id=organization_id,
        name=body.name,
        actor_id=user.id,
        slug=body.slug,
    )
    return WorkspaceResponse.model_validate(workspace)


@router.get("/workspaces", response_model=ApiResponse[list[WorkspaceResponse]])
async def list_workspaces(
    organization_id: uuid.UUID,
    session: DbSession,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    _: User = Depends(require_permission("analytics.read")),
) -> ApiResponse[list[WorkspaceResponse]]:
    result = await WorkspaceService(session).list(
        organization_id, PageParams(page=page, size=size)
    )
    items = [WorkspaceResponse.model_validate(w) for w in result.items]
    return paginated(items, result)


# -- Projects ------------------------------------------------------------
@router.post(
    "/workspaces/{workspace_id}/projects",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_project(
    organization_id: uuid.UUID,
    workspace_id: uuid.UUID,
    body: ProjectCreateRequest,
    user: CurrentUser,
    session: DbSession,
    _: User = Depends(require_permission("project.create")),
) -> ProjectResponse:
    project = await ProjectService(session).create(
        workspace_id=workspace_id,
        name=body.name,
        actor_id=user.id,
        slug=body.slug,
        description=body.description,
    )
    return ProjectResponse.model_validate(project)


@router.get(
    "/workspaces/{workspace_id}/projects",
    response_model=ApiResponse[list[ProjectResponse]],
)
async def list_projects(
    organization_id: uuid.UUID,
    workspace_id: uuid.UUID,
    session: DbSession,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    _: User = Depends(require_permission("analytics.read")),
) -> ApiResponse[list[ProjectResponse]]:
    result = await ProjectService(session).list(
        workspace_id, PageParams(page=page, size=size)
    )
    items = [ProjectResponse.model_validate(p) for p in result.items]
    return paginated(items, result)


# -- Videos --------------------------------------------------------------
@router.post(
    "/projects/{project_id}/videos",
    response_model=VideoResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_video(
    organization_id: uuid.UUID,
    project_id: uuid.UUID,
    body: VideoCreateRequest,
    user: CurrentUser,
    session: DbSession,
    _: User = Depends(require_permission("video.create")),
) -> VideoResponse:
    video = await VideoService(session).create(
        project_id=project_id,
        title=body.title,
        actor_id=user.id,
        description=body.description,
    )
    return VideoResponse.model_validate(video)


@router.get(
    "/projects/{project_id}/videos",
    response_model=ApiResponse[list[VideoResponse]],
)
async def list_videos(
    organization_id: uuid.UUID,
    project_id: uuid.UUID,
    session: DbSession,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    _: User = Depends(require_permission("analytics.read")),
) -> ApiResponse[list[VideoResponse]]:
    result = await VideoService(session).list(
        project_id, PageParams(page=page, size=size)
    )
    items = [VideoResponse.model_validate(v) for v in result.items]
    return paginated(items, result)
