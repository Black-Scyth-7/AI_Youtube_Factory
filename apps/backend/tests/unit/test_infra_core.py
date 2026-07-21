"""Unit tests for core infrastructure: cache, events, tasks, pagination, storage."""

from __future__ import annotations

import uuid

import pytest
from app.core.api.pagination import (
    Page,
    PageParams,
    decode_cursor,
    encode_cursor,
)
from app.core.cache import CacheService, InMemoryCache
from app.core.events import Event, EventBus
from app.core.storage.local import LocalStorageProvider
from app.core.storage.media import (
    compute_sha256,
    guess_mime_type,
    validate_mime_type,
)
from app.core.tasks import InMemoryTaskQueue, TaskSpec, TaskStatus
from app.exceptions.base import ValidationError

pytestmark = pytest.mark.asyncio


# -- Pagination ----------------------------------------------------------
def test_page_params_limits() -> None:
    assert PageParams(page=3, size=25).offset == 50
    assert PageParams(page=1, size=1000).limit == 100  # capped


def test_page_metadata() -> None:
    page = Page(items=[1, 2], total=45, page=2, size=20)
    assert page.pages == 3
    assert page.has_next is True
    assert page.has_prev is True


def test_cursor_roundtrip() -> None:
    payload = {"id": "abc", "created_at": "2026-01-01"}
    assert decode_cursor(encode_cursor(payload)) == payload


# -- Cache ---------------------------------------------------------------
async def test_cache_get_or_set_and_invalidate() -> None:
    cache = CacheService(InMemoryCache())
    calls = {"n": 0}

    async def factory() -> dict[str, int]:
        calls["n"] += 1
        return {"value": 42}

    first = await cache.get_or_set("ns", "k", factory)
    second = await cache.get_or_set("ns", "k", factory)
    assert first == second == {"value": 42}
    assert calls["n"] == 1  # cached second time

    await cache.invalidate_namespace("ns")
    assert await cache.get("ns", "k") is None


async def test_cache_ttl_expiry() -> None:
    import time

    backend = InMemoryCache()
    await backend.set("k", "v", ttl=60)
    assert await backend.get("k") == "v"
    # Force the entry to look expired; get() must evict and return None.
    backend._store["k"] = ("v", time.monotonic() - 1)
    assert await backend.get("k") is None


# -- Events --------------------------------------------------------------
async def test_event_bus_publish_and_retry() -> None:
    from dataclasses import dataclass

    @dataclass(frozen=True, slots=True, kw_only=True)
    class Ping(Event):
        n: int

    bus = EventBus(max_retries=2)
    received: list[int] = []

    @bus.on(Ping)
    async def _handler(event: Event) -> None:
        assert isinstance(event, Ping)
        received.append(event.n)

    await bus.publish(Ping(n=7))
    assert received == [7]


async def test_event_bus_dead_letters_on_failure() -> None:
    from dataclasses import dataclass

    @dataclass(frozen=True, slots=True, kw_only=True)
    class Boom(Event):
        pass

    bus = EventBus(max_retries=1)

    @bus.on(Boom)
    async def _bad(_: Event) -> None:
        raise RuntimeError("nope")

    await bus.publish(Boom())
    assert len(bus.dead_letters) == 1
    assert "nope" in bus.dead_letters[0].error


# -- Tasks ---------------------------------------------------------------
async def test_task_queue_runs_and_reports() -> None:
    queue = InMemoryTaskQueue()

    async def handler(payload: dict, record: object) -> int:
        return payload["a"] + payload["b"]

    queue.register("add", handler)
    record = await queue.submit(TaskSpec(name="add", payload={"a": 2, "b": 3}))
    done = await queue.wait(record.id)
    assert done.status == TaskStatus.SUCCEEDED
    assert done.result == 5


async def test_task_queue_retries_then_fails() -> None:
    queue = InMemoryTaskQueue()

    async def flaky(_: dict, __: object) -> None:
        raise ValueError("always")

    queue.register("flaky", flaky)
    record = await queue.submit(TaskSpec(name="flaky", max_retries=2))
    done = await queue.wait(record.id)
    assert done.status == TaskStatus.FAILED
    assert done.attempts == 3  # initial + 2 retries


# -- Storage (local) -----------------------------------------------------
async def test_local_storage_roundtrip(tmp_path) -> None:
    storage = LocalStorageProvider(
        base_path=str(tmp_path), public_base_url="http://x/files"
    )
    key = f"{uuid.uuid4()}/hello.txt"
    stored = await storage.put(key, b"hello", "text/plain")
    assert stored.size_bytes == 5
    assert await storage.exists(key) is True
    assert await storage.get(key) == b"hello"
    await storage.delete(key)
    assert await storage.exists(key) is False


async def test_local_storage_rejects_traversal(tmp_path) -> None:
    from app.exceptions.base import StorageError

    storage = LocalStorageProvider(base_path=str(tmp_path))
    with pytest.raises(StorageError):
        await storage.put("../escape.txt", b"x", "text/plain")


# -- Media utils ---------------------------------------------------------
def test_media_hash_and_mime() -> None:
    assert compute_sha256(b"a") == compute_sha256(b"a")
    assert guess_mime_type("clip.mp4") == "video/mp4"
    validate_mime_type("image/png")
    with pytest.raises(ValidationError):
        validate_mime_type("application/x-evil")
