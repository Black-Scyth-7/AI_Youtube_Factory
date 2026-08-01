"""Integration tests for the S3-compatible provider, run against MinIO.

Skipped unless a MinIO (or other S3) endpoint is reachable, so the default test
run stays offline. To run them:

    docker compose up -d minio
    STORAGE_ENDPOINT_URL=http://localhost:9000 \\
    STORAGE_ACCESS_KEY=minioadmin STORAGE_SECRET_KEY=minioadmin \\
    pytest tests/integration/test_storage_s3.py
"""

from __future__ import annotations

import contextlib
import os
import uuid
from collections.abc import AsyncIterator

import pytest
from app.core.storage.interfaces import StorageProvider
from app.core.storage.s3 import S3StorageProvider
from app.exceptions.base import NotFoundError

pytestmark = pytest.mark.asyncio

ENDPOINT = os.environ.get("STORAGE_ENDPOINT_URL")
ACCESS_KEY = os.environ.get("STORAGE_ACCESS_KEY", "minioadmin")
SECRET_KEY = os.environ.get("STORAGE_SECRET_KEY", "minioadmin")
BUCKET = os.environ.get("STORAGE_BUCKET", "ayf-test")

pytest.importorskip("aioboto3")

if not ENDPOINT:
    pytest.skip(
        "Set STORAGE_ENDPOINT_URL to run S3 integration tests.",
        allow_module_level=True,
    )


@pytest.fixture
async def storage() -> AsyncIterator[S3StorageProvider]:
    """A provider pointed at the test bucket, created if absent."""
    provider = S3StorageProvider(
        provider=StorageProvider.MINIO,
        bucket=BUCKET,
        endpoint_url=ENDPOINT,
        access_key=ACCESS_KEY,
        secret_key=SECRET_KEY,
        use_ssl=ENDPOINT.startswith("https"),
        force_path_style=True,
    )
    async with provider._client() as client:
        with contextlib.suppress(Exception):  # bucket may already exist
            await client.create_bucket(Bucket=BUCKET)
    yield provider


async def test_round_trip(storage: S3StorageProvider) -> None:
    key = f"tests/{uuid.uuid4().hex}.txt"
    stored = await storage.put(key, b"hello minio", "text/plain")

    assert stored.key == key
    assert stored.size_bytes == 11
    assert stored.content_type == "text/plain"
    assert stored.url and stored.url.startswith("http")

    assert await storage.exists(key) is True
    assert await storage.get(key) == b"hello minio"

    await storage.delete(key)
    assert await storage.exists(key) is False


async def test_leading_slash_is_normalised(storage: S3StorageProvider) -> None:
    """ "/a" and "a" must address the same object."""
    name = f"tests/{uuid.uuid4().hex}.bin"
    await storage.put(f"/{name}", b"x", "application/octet-stream")
    assert await storage.get(name) == b"x"
    await storage.delete(name)


async def test_missing_object_raises_not_found(storage: S3StorageProvider) -> None:
    with pytest.raises(NotFoundError):
        await storage.get(f"tests/absent-{uuid.uuid4().hex}")


async def test_deleting_absent_object_is_a_no_op(storage: S3StorageProvider) -> None:
    await storage.delete(f"tests/absent-{uuid.uuid4().hex}")


async def test_binary_payload_is_byte_exact(storage: S3StorageProvider) -> None:
    key = f"tests/{uuid.uuid4().hex}.bin"
    payload = bytes(range(256)) * 64
    await storage.put(key, payload, "application/octet-stream")
    assert await storage.get(key) == payload
    await storage.delete(key)


async def test_overwrite_replaces_content(storage: S3StorageProvider) -> None:
    key = f"tests/{uuid.uuid4().hex}.txt"
    await storage.put(key, b"first", "text/plain")
    await storage.put(key, b"second", "text/plain")
    assert await storage.get(key) == b"second"
    await storage.delete(key)


async def test_presigned_url_is_fetchable(storage: S3StorageProvider) -> None:
    """The signed URL must actually serve the bytes, unauthenticated."""
    import httpx

    key = f"tests/{uuid.uuid4().hex}.txt"
    await storage.put(key, b"signed content", "text/plain")
    url = await storage.presign_url(key, expires_in=120)

    async with httpx.AsyncClient() as client:
        response = await client.get(url)
    assert response.status_code == 200
    assert response.content == b"signed content"

    await storage.delete(key)


async def test_health_check_true_for_existing_bucket(
    storage: S3StorageProvider,
) -> None:
    assert await storage.health_check() is True


async def test_health_check_false_for_missing_bucket() -> None:
    provider = S3StorageProvider(
        provider=StorageProvider.MINIO,
        bucket=f"absent-{uuid.uuid4().hex}",
        endpoint_url=ENDPOINT,
        access_key=ACCESS_KEY,
        secret_key=SECRET_KEY,
        use_ssl=False,
        force_path_style=True,
    )
    assert await provider.health_check() is False
