"""Azure Blob Storage provider.

Uses the SDK's native async client (``azure.storage.blob.aio``), so unlike the
GCS provider no thread offloading is needed. Optional dependency:
``pip install -e ".[azure]"``.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from app.config import settings
from app.core.storage.interfaces import StorageProvider, StoredObject
from app.exceptions.base import NotFoundError, StorageError


def _require_azure() -> Any:
    """Import the Azure blob SDK, translating absence into an actionable error."""
    try:
        from azure.storage.blob import aio as blob_aio
    except ModuleNotFoundError as exc:  # pragma: no cover - import guard
        raise StorageError(
            "The Azure storage backend needs the 'azure' extra. "
            'Install it with: pip install -e ".[azure]"',
            details={"missing": "azure-storage-blob"},
        ) from exc
    return blob_aio


class AzureStorageProvider:
    """Object storage backed by an Azure Blob container."""

    provider = StorageProvider.AZURE

    def __init__(
        self,
        *,
        container: str | None = None,
        account_url: str | None = None,
        connection_string: str | None = None,
    ) -> None:
        self._container = container or settings.storage_azure_container
        self._account_url = (
            account_url if account_url is not None else settings.storage_azure_account_url
        )
        self._connection_string = (
            connection_string
            if connection_string is not None
            else settings.storage_azure_connection_string
        )

    def _service(self) -> Any:
        """Return an async BlobServiceClient (used as a context manager)."""
        blob_aio = _require_azure()
        if self._connection_string:
            return blob_aio.BlobServiceClient.from_connection_string(
                self._connection_string
            )
        if not self._account_url:
            raise StorageError(
                "Azure storage needs STORAGE_AZURE_ACCOUNT_URL or "
                "STORAGE_AZURE_CONNECTION_STRING.",
                details={"provider": "azure"},
            )
        from azure.identity.aio import DefaultAzureCredential

        return blob_aio.BlobServiceClient(
            account_url=self._account_url, credential=DefaultAzureCredential()
        )

    @staticmethod
    def _normalise(key: str) -> str:
        cleaned = key.lstrip("/")
        if not cleaned:
            raise StorageError("Invalid storage key.", details={"key": key})
        return cleaned

    @staticmethod
    def _is_missing(exc: Exception) -> bool:
        return type(exc).__name__ == "ResourceNotFoundError"

    # -- StorageClient ----------------------------------------------------
    async def put(self, key: str, data: bytes, content_type: str) -> StoredObject:
        object_key = self._normalise(key)
        _require_azure()
        try:
            # ContentSettings is shared between the sync and aio surfaces.
            from azure.storage.blob import ContentSettings

            async with self._service() as service:
                container = service.get_container_client(self._container)
                await container.upload_blob(
                    name=object_key,
                    data=data,
                    overwrite=True,
                    content_settings=ContentSettings(content_type=content_type),
                )
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
        try:
            async with self._service() as service:
                blob = service.get_blob_client(self._container, object_key)
                stream = await blob.download_blob()
                data: bytes = await stream.readall()
        except Exception as exc:
            if self._is_missing(exc):
                raise NotFoundError(
                    "Stored object not found.", details={"key": object_key}
                ) from exc
            raise StorageError(
                "Failed to read object.", details={"key": object_key}
            ) from exc
        return data

    async def delete(self, key: str) -> None:
        object_key = self._normalise(key)
        try:
            async with self._service() as service:
                blob = service.get_blob_client(self._container, object_key)
                await blob.delete_blob()
        except Exception as exc:
            if self._is_missing(exc):
                return
            raise StorageError(
                "Failed to delete object.", details={"key": object_key}
            ) from exc

    async def presign_url(self, key: str, expires_in: int = 3600) -> str:
        """Return a SAS URL.

        Requires an account key, which only the connection-string form provides;
        with managed identity there is no key to sign with, so the plain blob URL
        is returned and access is governed by the container's own policy.
        """
        object_key = self._normalise(key)
        try:
            async with self._service() as service:
                blob = service.get_blob_client(self._container, object_key)
                account_key = getattr(service.credential, "account_key", None)
                if not account_key:
                    return str(blob.url)

                from azure.storage.blob import (
                    BlobSasPermissions,
                    generate_blob_sas,
                )

                token = generate_blob_sas(
                    account_name=service.account_name,
                    container_name=self._container,
                    blob_name=object_key,
                    account_key=account_key,
                    permission=BlobSasPermissions(read=True),
                    expiry=datetime.now(UTC) + timedelta(seconds=expires_in),
                )
                return f"{blob.url}?{token}"
        except Exception as exc:
            raise StorageError(
                "Failed to sign object URL.", details={"key": object_key}
            ) from exc

    async def exists(self, key: str) -> bool:
        object_key = self._normalise(key)
        try:
            async with self._service() as service:
                blob = service.get_blob_client(self._container, object_key)
                found: bool = await blob.exists()
        except Exception as exc:
            raise StorageError(
                "Failed to stat object.", details={"key": object_key}
            ) from exc
        return found

    async def health_check(self) -> bool:
        try:
            async with self._service() as service:
                container = service.get_container_client(self._container)
                reachable: bool = await container.exists()
        except Exception:
            return False
        return reachable


def create_azure_storage() -> AzureStorageProvider:
    """Factory used to register the Azure provider."""
    return AzureStorageProvider()
