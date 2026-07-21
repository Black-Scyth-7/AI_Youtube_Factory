"""Repositories for content-domain entities."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from app.models.media import Folder, MediaFile, Tag
from app.models.video import Video, VideoVersion
from app.models.workspace import Channel, Project, Workspace
from app.repositories.base import BaseRepository


class WorkspaceRepository(BaseRepository[Workspace]):
    model = Workspace

    async def get_by_slug(
        self, organization_id: uuid.UUID, slug: str
    ) -> Workspace | None:
        return await self.find_by(organization_id=organization_id, slug=slug)


class ProjectRepository(BaseRepository[Project]):
    model = Project

    async def get_by_slug(self, workspace_id: uuid.UUID, slug: str) -> Project | None:
        return await self.find_by(workspace_id=workspace_id, slug=slug)


class ChannelRepository(BaseRepository[Channel]):
    model = Channel


class VideoRepository(BaseRepository[Video]):
    model = Video

    async def next_version_number(self, video_id: uuid.UUID) -> int:
        result = await self.session.execute(
            select(VideoVersion.version_number)
            .where(VideoVersion.video_id == video_id)
            .order_by(VideoVersion.version_number.desc())
            .limit(1)
        )
        last = result.scalar_one_or_none()
        return (last or 0) + 1


class VideoVersionRepository(BaseRepository[VideoVersion]):
    model = VideoVersion


class FolderRepository(BaseRepository[Folder]):
    model = Folder


class MediaFileRepository(BaseRepository[MediaFile]):
    model = MediaFile

    async def get_by_hash(self, workspace_id: uuid.UUID, sha256: str) -> MediaFile | None:
        return await self.find_by(workspace_id=workspace_id, sha256=sha256)


class TagRepository(BaseRepository[Tag]):
    model = Tag
