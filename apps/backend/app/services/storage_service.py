"""Storage service — uploads media through the storage provider.

Validates MIME type, hashes content for deduplication, persists a `MediaFile`
record, and stores the bytes via the configured storage provider. Emits an
`UploadCompleted` event.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import UploadCompleted, get_event_bus
from app.core.storage import compute_sha256, get_storage, validate_mime_type
from app.core.storage.media import guess_mime_type
from app.models.media import MediaFile
from app.repositories.content import MediaFileRepository


class StorageService:
    """Uploads and records media assets."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = MediaFileRepository(session)
        self.storage = get_storage()
        self.events = get_event_bus()

    async def upload(
        self,
        *,
        workspace_id: uuid.UUID,
        filename: str,
        data: bytes,
        actor_id: uuid.UUID,
        content_type: str | None = None,
        folder_id: uuid.UUID | None = None,
    ) -> MediaFile:
        """Validate, deduplicate, store, and record an uploaded file."""
        mime = content_type or guess_mime_type(filename)
        validate_mime_type(mime)
        digest = compute_sha256(data)

        # Deduplicate within the workspace by content hash.
        existing = await self.repo.get_by_hash(workspace_id, digest)
        if existing is not None:
            return existing

        key = f"{workspace_id}/{digest[:2]}/{digest}"
        stored = await self.storage.put(key, data, mime)

        media = await self.repo.add(
            MediaFile(
                workspace_id=workspace_id,
                folder_id=folder_id,
                filename=filename,
                storage_key=stored.key,
                mime_type=mime,
                size_bytes=stored.size_bytes,
                sha256=digest,
                created_by=actor_id,
                updated_by=actor_id,
            )
        )
        await self.events.publish(
            UploadCompleted(storage_key=stored.key, size_bytes=stored.size_bytes)
        )
        return media

    async def read(self, media: MediaFile) -> bytes:
        """Return the stored bytes for a media record."""
        return await self.storage.get(media.storage_key)
