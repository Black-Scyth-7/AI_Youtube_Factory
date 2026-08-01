"""Google Cloud Storage provider.

``google-cloud-storage`` is synchronous, so every call is dispatched to a worker
thread — the event loop must never block on network I/O. Optional dependency:
``pip install -e ".[gcs]"``.
"""

from __future__ import annotations

import asyncio
from datetime import timedelta
from typing import Any

from app.config import settings
from app.core.storage.interfaces import StorageProvider, StoredObject
from app.exceptions.base import NotFoundError, StorageError


def _require_gcs() -> Any:
    """Import the GCS client, translating absence into an actionable error."""
    try:
        from google.cloud import storage as gcs_storage
    except ModuleNotFoundError as exc:  # pragma: no cover - import guard
        raise StorageError(
            "The GCS storage backend needs the 'gcs' extra. "
            'Install it with: pip install -e ".[gcs]"',
            details={"missing": "google-cloud-storage"},
        ) from exc
    return gcs_storage


class GCSStorageProvider:
    """Object storage backed by a Google Cloud Storage bucket."""

    provider = StorageProvider.GCS

    def __init__(
        self,
        *,
        bucket: str | None = None,
        project: str | None = None,
        credentials_path: str | None = None,
    ) -> None:
        self._bucket_name = bucket or settings.storage_bucket
        self._project = project or settings.storage_gcs_project
        self._credentials_path = (
            credentials_path
            if credentials_path is not None
            else settings.storage_gcs_credentials_path
        )
        self._client: Any | None = None

    def _get_bucket(self) -> Any:
        """Return the bucket handle, creating the client on first use."""
        if self._client is None:
            gcs_storage = _require_gcs()
            if self._credentials_path:
                self._client = gcs_storage.Client.from_service_account_json(
                    self._credentials_path, project=self._project
                )
            else:
                self._client = gcs_storage.Client(project=self._project)
        return self._client.bucket(self._bucket_name)

    @staticmethod
    def _normalise(key: str) -> str:
        cleaned = key.lstrip("/")
        if not cleaned:
            raise StorageError("Invalid storage key.", details={"key": key})
        return cleaned

    # -- StorageClient ----------------------------------------------------
    async def put(self, key: str, data: bytes, content_type: str) -> StoredObject:
        object_key = self._normalise(key)

        def _put() -> None:
            blob = self._get_bucket().blob(object_key)
            blob.upload_from_string(data, content_type=content_type)

        try:
            await asyncio.to_thread(_put)
        except Exception as exc:
            raise StorageError(
                "Failed to store object.", details={"key": object_key}
            ) from exc
        return StoredObject(
            key=object_key,
            size_bytes=len(data),
            content_type=content_type,
            url=await self.presign_url(object_key),
        )

    async def get(self, key: str) -> bytes:
        object_key = self._normalise(key)

        def _get() -> bytes | None:
            blob = self._get_bucket().blob(object_key)
            if not blob.exists():
                return None
            downloaded: bytes = blob.download_as_bytes()
            return downloaded

        try:
            data = await asyncio.to_thread(_get)
        except Exception as exc:
            raise StorageError(
                "Failed to read object.", details={"key": object_key}
            ) from exc
        if data is None:
            raise NotFoundError("Stored object not found.", details={"key": object_key})
        return data

    async def delete(self, key: str) -> None:
        object_key = self._normalise(key)

        def _delete() -> None:
            # Absent objects are not an error, matching the other providers.
            self._get_bucket().blob(object_key).delete(if_generation_match=None)

        try:
            await asyncio.to_thread(_delete)
        except Exception as exc:
            if type(exc).__name__ == "NotFound":
                return
            raise StorageError(
                "Failed to delete object.", details={"key": object_key}
            ) from exc

    async def presign_url(self, key: str, expires_in: int = 3600) -> str:
        object_key = self._normalise(key)

        def _sign() -> str:
            blob = self._get_bucket().blob(object_key)
            signed: str = blob.generate_signed_url(
                expiration=timedelta(seconds=expires_in), version="v4"
            )
            return signed

        try:
            return await asyncio.to_thread(_sign)
        except Exception as exc:
            raise StorageError(
                "Failed to sign object URL.", details={"key": object_key}
            ) from exc

    async def exists(self, key: str) -> bool:
        object_key = self._normalise(key)

        def _exists() -> bool:
            found: bool = self._get_bucket().blob(object_key).exists()
            return found

        try:
            return await asyncio.to_thread(_exists)
        except Exception as exc:
            raise StorageError(
                "Failed to stat object.", details={"key": object_key}
            ) from exc

    async def health_check(self) -> bool:
        def _check() -> bool:
            reachable: bool = self._get_bucket().exists()
            return reachable

        try:
            return await asyncio.to_thread(_check)
        except Exception:
            return False


def create_gcs_storage() -> GCSStorageProvider:
    """Factory used to register the GCS provider."""
    return GCSStorageProvider()
