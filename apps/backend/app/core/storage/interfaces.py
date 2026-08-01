"""Storage provider abstraction — interfaces.

Provider-agnostic object storage contract. Backends: local filesystem, any
S3-compatible service (AWS S3, MinIO, Cloudflare R2), Google Cloud Storage and
Azure Blob Storage.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, runtime_checkable


class StorageProvider(StrEnum):
    """Known storage backend identifiers.

    Must stay in step with ``Settings.storage_backend``: a value accepted there
    but missing here passes configuration validation and then fails at the point
    the client is constructed.
    """

    S3 = "s3"
    MINIO = "minio"
    R2 = "r2"
    GCS = "gcs"
    AZURE = "azure"
    LOCAL = "local"


#: Providers that speak the S3 API and share one implementation.
S3_COMPATIBLE = frozenset({StorageProvider.S3, StorageProvider.MINIO, StorageProvider.R2})


@dataclass(slots=True, frozen=True)
class StoredObject:
    """Metadata describing a stored object."""

    key: str
    size_bytes: int
    content_type: str
    url: str | None = None


@runtime_checkable
class StorageClient(Protocol):
    """The contract all concrete storage providers implement."""

    provider: StorageProvider

    async def put(self, key: str, data: bytes, content_type: str) -> StoredObject:
        """Store ``data`` under ``key`` and return its metadata."""
        ...

    async def get(self, key: str) -> bytes:
        """Return the bytes stored under ``key``."""
        ...

    async def delete(self, key: str) -> None:
        """Delete the object at ``key``."""
        ...

    async def presign_url(self, key: str, expires_in: int = 3600) -> str:
        """Return a temporary download URL for ``key``."""
        ...

    async def health_check(self) -> bool:
        """Return ``True`` if the backend is reachable and configured."""
        ...
