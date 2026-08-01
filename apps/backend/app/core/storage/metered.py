"""Metrics and tracing wrapper for storage clients.

Wraps any :class:`~app.core.storage.interfaces.StorageClient` so every backend
is instrumented once, rather than each provider repeating the same timing code
— and so a provider added later is instrumented by construction.

Applied by ``get_storage()``, not by the factory, so ``create_storage_client``
still returns the concrete provider a test asked for.
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from app.observability import instruments
from app.observability.tracing import start_span

if TYPE_CHECKING:
    from app.core.storage.interfaces import StorageClient, StoredObject


class MeteredStorageClient:
    """Times and counts every storage call, then delegates."""

    __slots__ = ("_backend", "_client")

    def __init__(self, client: StorageClient, backend: str) -> None:
        self._client = client
        self._backend = backend

    @property
    def wrapped(self) -> StorageClient:
        """The underlying client, for callers that need the concrete type."""
        return self._client

    def _record(self, operation: str, start: float, outcome: str) -> None:
        instruments.storage_operations_total.inc(
            1.0, backend=self._backend, operation=operation, outcome=outcome
        )
        instruments.storage_operation_duration_seconds.observe(
            time.perf_counter() - start, backend=self._backend, operation=operation
        )

    async def put(self, key: str, data: bytes, content_type: str) -> StoredObject:
        start = time.perf_counter()
        with start_span(
            "storage.put",
            kind="client",
            attributes={"storage.backend": self._backend, "storage.size": len(data)},
        ):
            try:
                result = await self._client.put(key, data, content_type)
            except Exception:
                self._record("put", start, "error")
                raise
            self._record("put", start, "success")
            return result

    async def get(self, key: str) -> bytes:
        start = time.perf_counter()
        with start_span(
            "storage.get", kind="client", attributes={"storage.backend": self._backend}
        ):
            try:
                data = await self._client.get(key)
            except Exception:
                self._record("get", start, "error")
                raise
            self._record("get", start, "success")
            return data

    async def delete(self, key: str) -> None:
        start = time.perf_counter()
        with start_span(
            "storage.delete",
            kind="client",
            attributes={"storage.backend": self._backend},
        ):
            try:
                await self._client.delete(key)
            except Exception:
                self._record("delete", start, "error")
                raise
            self._record("delete", start, "success")

    async def presign_url(self, key: str, expires_in: int = 3600) -> str:
        start = time.perf_counter()
        try:
            url = await self._client.presign_url(key, expires_in)
        except Exception:
            self._record("presign_url", start, "error")
            raise
        self._record("presign_url", start, "success")
        return url

    async def health_check(self) -> bool:
        start = time.perf_counter()
        try:
            healthy = await self._client.health_check()
        except Exception:
            self._record("health_check", start, "error")
            raise
        # A reachable backend reporting unhealthy is not an exception, but it is
        # not a success either — the distinction is the point of the check.
        self._record("health_check", start, "success" if healthy else "unhealthy")
        return healthy
