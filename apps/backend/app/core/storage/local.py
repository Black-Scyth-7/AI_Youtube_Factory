"""Local filesystem storage provider.

Implements the :class:`StorageClient` contract against a base directory. Keys are
validated to prevent path traversal outside the storage root. Suitable for local
development and single-node deployments; S3/MinIO/R2/GCS/Azure providers plug in
behind the same interface.
"""

from __future__ import annotations

from pathlib import Path

from app.config import settings
from app.core.storage.interfaces import StorageProvider, StoredObject
from app.exceptions.base import NotFoundError, StorageError


class LocalStorageProvider:
    """Stores objects on the local filesystem under a base directory."""

    provider = StorageProvider.LOCAL

    def __init__(
        self, base_path: str | None = None, public_base_url: str | None = None
    ) -> None:
        self._root = Path(base_path or settings.storage_local_path).resolve()
        self._root.mkdir(parents=True, exist_ok=True)
        self._public_base_url = (
            public_base_url or settings.storage_public_base_url
        ).rstrip("/")

    def _resolve(self, key: str) -> Path:
        """Resolve a key to an absolute path, rejecting traversal."""
        candidate = (self._root / key.lstrip("/")).resolve()
        if not candidate.is_relative_to(self._root):
            raise StorageError("Invalid storage key.", details={"key": key})
        return candidate

    async def put(self, key: str, data: bytes, content_type: str) -> StoredObject:
        path = self._resolve(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return StoredObject(
            key=key,
            size_bytes=len(data),
            content_type=content_type,
            url=f"{self._public_base_url}/{key.lstrip('/')}",
        )

    async def get(self, key: str) -> bytes:
        path = self._resolve(key)
        if not path.is_file():
            raise NotFoundError("Stored object not found.", details={"key": key})
        return path.read_bytes()

    async def delete(self, key: str) -> None:
        path = self._resolve(key)
        path.unlink(missing_ok=True)

    async def presign_url(self, key: str, expires_in: int = 3600) -> str:
        # The local provider serves via a stable public URL (no signing).
        return f"{self._public_base_url}/{key.lstrip('/')}"

    async def exists(self, key: str) -> bool:
        return self._resolve(key).is_file()

    async def health_check(self) -> bool:
        return self._root.is_dir()


def create_local_storage() -> LocalStorageProvider:
    """Factory used to register the local provider."""
    return LocalStorageProvider()
