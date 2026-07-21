"""Content-domain services: workspaces, projects, channels, and videos.

Business logic lives here (never in repositories or routes). Services publish
domain events on the internal event bus so future AI agents can react.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api.pagination import Page, PageParams
from app.core.events import (
    ProjectCreated,
    VideoCreated,
    WorkspaceCreated,
    get_event_bus,
)
from app.exceptions.base import NotFoundError
from app.models.video import Video, VideoVersion
from app.models.workspace import Channel, Project, Workspace
from app.repositories.content import (
    ChannelRepository,
    ProjectRepository,
    VideoRepository,
    VideoVersionRepository,
    WorkspaceRepository,
)
from app.utils.slug import slugify, unique_suffix


class WorkspaceService:
    """Creates and lists workspaces within an organization."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = WorkspaceRepository(session)
        self.events = get_event_bus()

    async def create(
        self,
        *,
        organization_id: uuid.UUID,
        name: str,
        actor_id: uuid.UUID,
        slug: str | None = None,
    ) -> Workspace:
        slug = slug or slugify(name)
        if await self.repo.get_by_slug(organization_id, slug):
            slug = f"{slug}-{unique_suffix()}"
        workspace = await self.repo.add(
            Workspace(
                organization_id=organization_id,
                name=name,
                slug=slug,
                created_by=actor_id,
                updated_by=actor_id,
            )
        )
        await self.events.publish(
            WorkspaceCreated(workspace_id=workspace.id, organization_id=organization_id)
        )
        return workspace

    async def get_or_404(self, workspace_id: uuid.UUID) -> Workspace:
        workspace = await self.repo.get(workspace_id)
        if workspace is None or workspace.deleted_at is not None:
            raise NotFoundError("Workspace not found.")
        return workspace

    async def list(
        self, organization_id: uuid.UUID, params: PageParams
    ) -> Page[Workspace]:
        from app.core.api.pagination import FilterSpec

        return await self.repo.paginate(
            params, filters=[FilterSpec("organization_id", "eq", organization_id)]
        )


class ProjectService:
    """Creates and lists projects within a workspace."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = ProjectRepository(session)
        self.events = get_event_bus()

    async def create(
        self,
        *,
        workspace_id: uuid.UUID,
        name: str,
        actor_id: uuid.UUID,
        slug: str | None = None,
        description: str | None = None,
    ) -> Project:
        slug = slug or slugify(name)
        if await self.repo.get_by_slug(workspace_id, slug):
            slug = f"{slug}-{unique_suffix()}"
        project = await self.repo.add(
            Project(
                workspace_id=workspace_id,
                name=name,
                slug=slug,
                description=description,
                created_by=actor_id,
                updated_by=actor_id,
            )
        )
        await self.events.publish(
            ProjectCreated(project_id=project.id, workspace_id=workspace_id)
        )
        return project

    async def get_or_404(self, project_id: uuid.UUID) -> Project:
        project = await self.repo.get(project_id)
        if project is None or project.deleted_at is not None:
            raise NotFoundError("Project not found.")
        return project

    async def list(self, workspace_id: uuid.UUID, params: PageParams) -> Page[Project]:
        from app.core.api.pagination import FilterSpec

        return await self.repo.paginate(
            params, filters=[FilterSpec("workspace_id", "eq", workspace_id)]
        )


class ChannelService:
    """Manages YouTube channels within a project."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = ChannelRepository(session)

    async def create(
        self, *, project_id: uuid.UUID, name: str, actor_id: uuid.UUID
    ) -> Channel:
        return await self.repo.add(
            Channel(
                project_id=project_id,
                name=name,
                created_by=actor_id,
                updated_by=actor_id,
            )
        )


class VideoService:
    """Creates videos and manages their versions."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = VideoRepository(session)
        self.versions = VideoVersionRepository(session)
        self.events = get_event_bus()

    async def create(
        self,
        *,
        project_id: uuid.UUID,
        title: str,
        actor_id: uuid.UUID,
        description: str | None = None,
    ) -> Video:
        video = await self.repo.add(
            Video(
                project_id=project_id,
                title=title,
                description=description,
                created_by=actor_id,
                updated_by=actor_id,
            )
        )
        await self.events.publish(VideoCreated(video_id=video.id, project_id=project_id))
        return video

    async def add_version(
        self, *, video_id: uuid.UUID, script: str | None, actor_id: uuid.UUID
    ) -> VideoVersion:
        video = await self.repo.get(video_id)
        if video is None or video.deleted_at is not None:
            raise NotFoundError("Video not found.")
        number = await self.repo.next_version_number(video_id)
        version = await self.versions.add(
            VideoVersion(
                video_id=video_id,
                version_number=number,
                script=script,
                created_by=actor_id,
                updated_by=actor_id,
            )
        )
        video.current_version_id = version.id
        video.updated_by = actor_id
        await self.session.flush()
        return version

    async def list(self, project_id: uuid.UUID, params: PageParams) -> Page[Video]:
        from app.core.api.pagination import FilterSpec

        return await self.repo.paginate(
            params, filters=[FilterSpec("project_id", "eq", project_id)]
        )
