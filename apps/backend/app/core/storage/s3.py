"""S3-compatible storage provider.

One implementation serves AWS S3, MinIO and Cloudflare R2 — they speak the same
API and differ only in endpoint and addressing style. ``aioboto3`` is an optional
dependency (``pip install -e ".[s3]"``); importing this module without it raises a
clear error rather than failing obscurely at first use.
"""

from __future__ import annotations

from types import TracebackType
from typing import TYPE_CHECKING, Any, Self

from app.config import settings
from app.core.storage.interfaces import StorageProvider, StoredObject
from app.exceptions.base import NotFoundError, StorageError

if TYPE_CHECKING:  # pragma: no cover - typing only
    pass


def _require_aioboto3() -> Any:
    """Import aioboto3, translating absence into an actionable error."""
    try:
        import aioboto3
    except ModuleNotFoundError as exc:  # pragma: no cover - import guard
        raise StorageError(
            "The S3 storage backend needs the 's3' extra. "
            'Install it with: pip install -e ".[s3]"',
            details={"missing": "aioboto3"},
        ) from exc
    return aioboto3


class S3StorageProvider:
    """Object storage against any S3-compatible endpoint.

    A session is created per operation rather than held open: the client is not
    safe to share across event loops, and object storage calls are infrequent
    enough that connection setup is not the bottleneck.
    """

    def __init__(
        self,
        *,
        provider: StorageProvider = StorageProvider.S3,
        bucket: str | None = None,
        region: str | None = None,
        endpoint_url: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        use_ssl: bool | None = None,
        force_path_style: bool | None = None,
    ) -> None:
        self.provider = provider
        self._bucket = bucket or settings.storage_bucket
        self._region = region or settings.storage_region
        self._endpoint_url = (
            endpoint_url if endpoint_url is not None else settings.storage_endpoint_url
        )
        self._access_key = access_key or settings.storage_access_key
        self._secret_key = secret_key or settings.storage_secret_key
        self._use_ssl = settings.storage_use_ssl if use_ssl is None else use_ssl
        self._force_path_style = (
            settings.storage_force_path_style
            if force_path_style is None
            else force_path_style
        )

    # -- internals --------------------------------------------------------
    def _client(self) -> Any:
        """Return an async context manager yielding a configured S3 client."""
        aioboto3 = _require_aioboto3()
        session = aioboto3.Session()

        config: Any = None
        if self._force_path_style:
            from botocore.config import Config

            config = Config(s3={"addressing_style": "path"})

        return session.client(
            "s3",
            region_name=self._region,
            endpoint_url=self._endpoint_url,
            aws_access_key_id=self._access_key or None,
            aws_secret_access_key=self._secret_key or None,
            use_ssl=self._use_ssl,
            config=config,
        )

    @staticmethod
    def _normalise(key: str) -> str:
        """Strip a leading slash so keys are consistent across providers."""
        cleaned = key.lstrip("/")
        if not cleaned:
            raise StorageError("Invalid storage key.", details={"key": key})
        return cleaned

    @staticmethod
    def _is_missing(exc: Exception) -> bool:
        """True when an S3 error means 'no such key/bucket'."""
        response = getattr(exc, "response", None)
        if not isinstance(response, dict):
            return False
        code = str(response.get("Error", {}).get("Code", ""))
        return code in {"NoSuchKey", "NoSuchBucket", "404", "NotFound"}

    # -- StorageClient ----------------------------------------------------
    async def put(self, key: str, data: bytes, content_type: str) -> StoredObject:
        object_key = self._normalise(key)
        try:
            async with self._client() as client:
                await client.put_object(
                    Bucket=self._bucket,
                    Key=object_key,
                    Body=data,
                    ContentType=content_type,
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
            async with self._client() as client:
                response = await client.get_object(Bucket=self._bucket, Key=object_key)
                body: bytes = await response["Body"].read()
        except Exception as exc:
            if self._is_missing(exc):
                raise NotFoundError(
                    "Stored object not found.", details={"key": object_key}
                ) from exc
            raise StorageError(
                "Failed to read object.", details={"key": object_key}
            ) from exc
        return body

    async def delete(self, key: str) -> None:
        object_key = self._normalise(key)
        try:
            async with self._client() as client:
                await client.delete_object(Bucket=self._bucket, Key=object_key)
        except Exception as exc:
            if self._is_missing(exc):
                return  # deleting an absent object is not an error
            raise StorageError(
                "Failed to delete object.", details={"key": object_key}
            ) from exc

    async def presign_url(self, key: str, expires_in: int = 3600) -> str:
        object_key = self._normalise(key)
        try:
            async with self._client() as client:
                url: str = await client.generate_presigned_url(
                    "get_object",
                    Params={"Bucket": self._bucket, "Key": object_key},
                    ExpiresIn=expires_in,
                )
        except Exception as exc:
            raise StorageError(
                "Failed to sign object URL.", details={"key": object_key}
            ) from exc
        return url

    async def exists(self, key: str) -> bool:
        object_key = self._normalise(key)
        try:
            async with self._client() as client:
                await client.head_object(Bucket=self._bucket, Key=object_key)
        except Exception as exc:
            if self._is_missing(exc):
                return False
            raise StorageError(
                "Failed to stat object.", details={"key": object_key}
            ) from exc
        return True

    async def health_check(self) -> bool:
        """True when the configured bucket is reachable."""
        try:
            async with self._client() as client:
                await client.head_bucket(Bucket=self._bucket)
        except Exception:
            return False
        return True

    # -- optional async context manager -----------------------------------
    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        return None


def create_s3_storage() -> S3StorageProvider:
    """Factory for the AWS S3 provider."""
    return S3StorageProvider(provider=StorageProvider.S3)


def create_minio_storage() -> S3StorageProvider:
    """Factory for MinIO — same API, path-style addressing by default."""
    return S3StorageProvider(
        provider=StorageProvider.MINIO,
        force_path_style=True,
    )


def create_r2_storage() -> S3StorageProvider:
    """Factory for Cloudflare R2 — S3 API with a custom endpoint."""
    return S3StorageProvider(provider=StorageProvider.R2)
