"""In-process asynchronous event bus.

Provides publish/subscribe with per-handler isolation, bounded retries, and a
dead-letter list for handlers that exhaust retries. Handlers are coroutine
functions keyed by event type. This is the foundation future AI agents subscribe
to; it can later be backed by a durable broker without changing call sites.
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

from app.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True, kw_only=True)
class Event:
    """Base class for all domain events."""

    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def name(self) -> str:
        return type(self).__name__


Handler = Callable[[Event], Awaitable[None]]


@dataclass(slots=True)
class DeadLetter:
    """A failed event delivery captured after retries are exhausted."""

    event: Event
    handler: str
    error: str


class EventBus:
    """Async pub/sub bus with retry and dead-letter capture."""

    def __init__(self, *, max_retries: int = 2, retry_delay: float = 0.0) -> None:
        self._handlers: dict[type[Event], list[Handler]] = defaultdict(list)
        self._max_retries = max_retries
        self._retry_delay = retry_delay
        self.dead_letters: list[DeadLetter] = []

    def subscribe(self, event_type: type[Event], handler: Handler) -> None:
        """Register ``handler`` for ``event_type``."""
        self._handlers[event_type].append(handler)

    def on(self, event_type: type[Event]) -> Callable[[Handler], Handler]:
        """Decorator form of :meth:`subscribe`."""

        def decorator(handler: Handler) -> Handler:
            self.subscribe(event_type, handler)
            return handler

        return decorator

    async def publish(self, event: Event) -> None:
        """Deliver ``event`` to all handlers concurrently, isolating failures."""
        handlers = self._handlers.get(type(event), [])
        if not handlers:
            return
        await asyncio.gather(*(self._deliver(h, event) for h in handlers))

    async def _deliver(self, handler: Handler, event: Event) -> None:
        attempt = 0
        while True:
            try:
                await handler(event)
                return
            except Exception as exc:
                attempt += 1
                if attempt > self._max_retries:
                    logger.error(
                        "event.handler_failed",
                        extra={
                            "event": event.name,
                            "handler": getattr(handler, "__name__", repr(handler)),
                            "error": str(exc),
                        },
                    )
                    self.dead_letters.append(
                        DeadLetter(
                            event=event,
                            handler=getattr(handler, "__name__", repr(handler)),
                            error=str(exc),
                        )
                    )
                    return
                if self._retry_delay:
                    await asyncio.sleep(self._retry_delay)


_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    """Return the process event-bus singleton."""
    global _bus
    if _bus is None:
        _bus = EventBus()
    return _bus


def set_event_bus(bus: EventBus) -> None:
    """Override the event-bus singleton (used in tests)."""
    global _bus
    _bus = bus
