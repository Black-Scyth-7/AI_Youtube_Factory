"""Distributed tracing.

Spans always work. The built-in tracer generates W3C-compatible ids, maintains
the parent/child stack in a :mod:`contextvars` variable, and emits one
structured ``trace.span`` log record per completed span — which, with the JSON
formatter, is already enough to reconstruct a trace from logs alone.

When the ``[otel]`` extra is installed and ``OTEL_ENABLED=true``, spans are
additionally recorded through the OpenTelemetry SDK and exported over OTLP.
That path is a thin adapter over the same API, so nothing at a call site
changes and nothing here requires the SDK to be importable.

Ids follow the W3C Trace Context encoding — a 32-hex-digit trace id and a
16-hex-digit span id — so a ``traceparent`` header can be parsed straight into
a span context and propagated to downstream services.
"""

from __future__ import annotations

import re
import secrets
import time
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from typing import Any, Final

from app.config import settings
from app.logging import get_logger
from app.logging.context import trace_id_var

logger = get_logger(__name__)

#: ``version-traceid-spanid-flags``; version ff is forbidden by the spec.
_TRACEPARENT_RE: Final = re.compile(
    r"^(?P<version>[0-9a-f]{2})-"
    r"(?P<trace_id>[0-9a-f]{32})-"
    r"(?P<span_id>[0-9a-f]{16})-"
    r"(?P<flags>[0-9a-f]{2})$"
)
TRACEPARENT_HEADER: Final = "traceparent"

_INVALID_TRACE_ID: Final = "0" * 32
_INVALID_SPAN_ID: Final = "0" * 16

#: Sampled bit of the trace-flags field.
FLAG_SAMPLED: Final = 0x01


def new_trace_id() -> str:
    """A random 16-byte trace id, hex encoded."""
    return secrets.token_hex(16)


def new_span_id() -> str:
    """A random 8-byte span id, hex encoded."""
    return secrets.token_hex(8)


@dataclass(frozen=True, slots=True)
class SpanContext:
    """The propagatable identity of a span."""

    trace_id: str
    span_id: str
    sampled: bool = True

    def to_traceparent(self) -> str:
        """Render as a W3C ``traceparent`` header value."""
        flags = FLAG_SAMPLED if self.sampled else 0
        return f"00-{self.trace_id}-{self.span_id}-{flags:02x}"

    @classmethod
    def parse(cls, traceparent: str) -> SpanContext | None:
        """Parse a ``traceparent`` header, returning ``None`` if unusable.

        A malformed or all-zero header is not an error worth failing a request
        over — it just means this service starts a new trace.
        """
        match = _TRACEPARENT_RE.match(traceparent.strip().lower())
        if match is None:
            return None
        if match["version"] == "ff":
            return None
        trace_id, span_id = match["trace_id"], match["span_id"]
        if trace_id == _INVALID_TRACE_ID or span_id == _INVALID_SPAN_ID:
            return None
        return cls(
            trace_id=trace_id,
            span_id=span_id,
            sampled=bool(int(match["flags"], 16) & FLAG_SAMPLED),
        )


@dataclass(slots=True)
class Span:
    """A unit of work with a duration, attributes, and an outcome."""

    name: str
    context: SpanContext
    parent_span_id: str | None = None
    kind: str = "internal"
    attributes: dict[str, Any] = field(default_factory=dict)
    status: str = "ok"
    error: str | None = None
    start: float = field(default_factory=time.perf_counter)
    end: float | None = None
    #: Set when an OpenTelemetry span is shadowing this one.
    otel_span: Any = None

    @property
    def trace_id(self) -> str:
        return self.context.trace_id

    @property
    def span_id(self) -> str:
        return self.context.span_id

    @property
    def duration_ms(self) -> float:
        finished = self.end if self.end is not None else time.perf_counter()
        return round((finished - self.start) * 1000, 3)

    def set_attribute(self, key: str, value: Any) -> None:
        """Attach one attribute to the span."""
        self.attributes[key] = value
        if self.otel_span is not None:
            self.otel_span.set_attribute(key, value)

    def set_attributes(self, attributes: Mapping[str, Any]) -> None:
        for key, value in attributes.items():
            self.set_attribute(key, value)

    def record_exception(self, exc: BaseException) -> None:
        """Mark the span failed and record the exception type and message."""
        self.status = "error"
        self.error = f"{type(exc).__name__}: {exc}"
        if self.otel_span is not None:
            self.otel_span.record_exception(exc)


#: The innermost span currently open in this context.
current_span_var: ContextVar[Span | None] = ContextVar("current_span", default=None)


def current_span() -> Span | None:
    """The innermost open span, if any."""
    return current_span_var.get()


def current_context() -> SpanContext | None:
    """The context to propagate downstream, if a span is open."""
    span = current_span_var.get()
    return span.context if span is not None else None


def current_traceparent() -> str | None:
    """A ``traceparent`` header value for the open span, if any."""
    context = current_context()
    return context.to_traceparent() if context is not None else None


@contextmanager
def start_span(
    name: str,
    *,
    kind: str = "internal",
    parent: SpanContext | None = None,
    attributes: Mapping[str, Any] | None = None,
) -> Iterator[Span]:
    """Open a span for the duration of the block.

    The span joins the current trace unless ``parent`` is given, in which case
    it continues that one — which is how an inbound ``traceparent`` becomes the
    root of this service's work.

    Exceptions are recorded and re-raised: a span must never swallow one.
    """
    active = current_span_var.get()
    if parent is not None:
        effective_parent, remote = parent, True
    elif active is not None:
        effective_parent, remote = active.context, False
    else:
        effective_parent, remote = None, False

    attrs = dict(attributes or {})
    # Started before the ids are chosen: when OpenTelemetry is active, its span
    # is the authority on both, so the trace in a viewer and the trace_id in
    # the logs are the same string. Deriving them separately produced a tree
    # here and a pile of disconnected single-span traces in the exporter.
    otel_span, otel_ids = _otel_start(name, kind, effective_parent, remote, attrs)

    if otel_ids is not None:
        trace_id, span_id = otel_ids
    elif effective_parent is not None:
        trace_id, span_id = effective_parent.trace_id, new_span_id()
    else:
        trace_id, span_id = new_trace_id(), new_span_id()

    context = SpanContext(
        trace_id=trace_id,
        span_id=span_id,
        sampled=effective_parent.sampled if effective_parent is not None else True,
    )
    span = Span(
        name=name,
        context=context,
        parent_span_id=(
            effective_parent.span_id if effective_parent is not None else None
        ),
        kind=kind,
        attributes=attrs,
    )
    span.otel_span = otel_span

    span_token: Token[Span | None] = current_span_var.set(span)
    # Keep the log context on the same trace, so every record emitted inside
    # the span carries the id a trace viewer would search for.
    trace_token: Token[str | None] = trace_id_var.set(context.trace_id)
    try:
        yield span
    except BaseException as exc:
        span.record_exception(exc)
        raise
    finally:
        span.end = time.perf_counter()
        current_span_var.reset(span_token)
        trace_id_var.reset(trace_token)
        _otel_end(span)
        _log_span(span)


def _log_span(span: Span) -> None:
    """Emit the structured record that makes spans usable without a collector."""
    payload: dict[str, Any] = {
        "span_name": span.name,
        "span_id": span.span_id,
        "parent_span_id": span.parent_span_id,
        "span_kind": span.kind,
        "duration_ms": span.duration_ms,
        "span_status": span.status,
    }
    if span.error:
        payload["span_error"] = span.error
    for key, value in span.attributes.items():
        payload[f"attr.{key}"] = value
    logger.debug("trace.span", extra=payload)


# -- OpenTelemetry bridge -----------------------------------------------------
# Optional. Installed with `pip install -e ".[otel]"`; absent, everything above
# still works and the calls below are no-ops.

_tracer: Any = None
_otel_ready = False


def _otel_start(
    name: str,
    kind: str,
    parent: SpanContext | None,
    remote: bool,
    attributes: Mapping[str, Any],
) -> tuple[Any, tuple[str, str] | None]:
    """Begin a shadow OpenTelemetry span.

    Returns the span and its ``(trace_id, span_id)`` as hex, or ``(None, None)``
    when OpenTelemetry is not active. The ids are handed back so the caller can
    adopt them: the SDK generates its own, and a span whose logged id differs
    from its exported id is worse than no id at all.
    """
    if _tracer is None:
        return None, None
    try:
        from opentelemetry import trace as otel_trace
        from opentelemetry.trace import (
            NonRecordingSpan,
            TraceFlags,
        )
        from opentelemetry.trace import (
            SpanContext as OtelSpanContext,
        )

        context = None
        if parent is not None:
            # A stand-in for the parent, which either lives in another service
            # or was already exported by this one. Without it the SDK treats
            # every span as a root and the exported trace has no shape.
            flags = TraceFlags(
                TraceFlags.SAMPLED if parent.sampled else TraceFlags.DEFAULT
            )
            context = otel_trace.set_span_in_context(
                NonRecordingSpan(
                    OtelSpanContext(
                        trace_id=int(parent.trace_id, 16),
                        span_id=int(parent.span_id, 16),
                        is_remote=remote,
                        trace_flags=flags,
                    )
                )
            )

        otel_span = _tracer.start_span(
            name,
            context=context,
            kind=_OTEL_KINDS.get(kind, otel_trace.SpanKind.INTERNAL),
        )
        for key, value in attributes.items():
            otel_span.set_attribute(key, value)

        span_context = otel_span.get_span_context()
        return otel_span, (
            format(span_context.trace_id, "032x"),
            format(span_context.span_id, "016x"),
        )
    except Exception as exc:  # pragma: no cover - defensive
        # Telemetry must never be the reason a request fails.
        logger.warning("tracing.otel_start_failed", extra={"error": str(exc)})
        return None, None


def _otel_end(span: Span) -> None:
    """Close the shadow span, if there is one."""
    if span.otel_span is None:
        return
    try:
        from opentelemetry.trace import Status, StatusCode

        if span.status == "error":
            span.otel_span.set_status(Status(StatusCode.ERROR, span.error or ""))
        else:
            span.otel_span.set_status(Status(StatusCode.OK))
        span.otel_span.end()
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("tracing.otel_end_failed", extra={"error": str(exc)})


_OTEL_KINDS: dict[str, Any] = {}


def configure_tracing() -> None:
    """Wire up the OpenTelemetry SDK when enabled and installed.

    Called once at startup. Enabling tracing without the extra installed is a
    configuration mistake worth a loud warning, but not worth refusing to
    start over — the built-in tracer still produces usable span logs.
    """
    global _tracer, _otel_ready

    if not settings.otel_enabled:
        return
    if _otel_ready:
        return

    try:
        from opentelemetry import trace as otel_trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased
    except ImportError:
        logger.warning(
            "tracing.otel_unavailable",
            extra={
                "hint": "OTEL_ENABLED is true but the SDK is missing; "
                'install it with: pip install -e ".[otel]"'
            },
        )
        return

    _OTEL_KINDS.update(
        {
            "internal": otel_trace.SpanKind.INTERNAL,
            "server": otel_trace.SpanKind.SERVER,
            "client": otel_trace.SpanKind.CLIENT,
            "producer": otel_trace.SpanKind.PRODUCER,
            "consumer": otel_trace.SpanKind.CONSUMER,
        }
    )

    resource = Resource.create(
        {
            "service.name": settings.otel_service_name,
            "service.version": settings.otel_service_version,
            "deployment.environment": settings.environment.value,
        }
    )
    provider = TracerProvider(
        resource=resource,
        sampler=ParentBased(TraceIdRatioBased(settings.otel_sample_ratio)),
    )

    exporter = _build_exporter()
    if exporter is not None:
        provider.add_span_processor(BatchSpanProcessor(exporter))

    otel_trace.set_tracer_provider(provider)
    _tracer = otel_trace.get_tracer(settings.otel_service_name)
    _otel_ready = True
    logger.info(
        "tracing.otel_configured",
        extra={
            "service": settings.otel_service_name,
            "endpoint": settings.otel_exporter_endpoint or "console",
            "sample_ratio": settings.otel_sample_ratio,
        },
    )


def _build_exporter() -> Any:
    """Build the configured span exporter, or ``None`` if none can be built."""
    endpoint = settings.otel_exporter_endpoint
    if not endpoint:
        try:
            from opentelemetry.sdk.trace.export import ConsoleSpanExporter

            return ConsoleSpanExporter()
        except ImportError:  # pragma: no cover - ships with the SDK
            return None
    try:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )
    except ImportError:
        logger.warning(
            "tracing.otlp_exporter_unavailable",
            extra={"endpoint": endpoint, "hint": 'pip install -e ".[otel]"'},
        )
        return None
    # Headers (an auth token, usually) come from the standard
    # OTEL_EXPORTER_OTLP_HEADERS variable, which the exporter reads and parses
    # itself. Forwarding it here passed the raw "k=v,k=v" string where a dict
    # was expected.
    return OTLPSpanExporter(endpoint=endpoint)


def shutdown_tracing() -> None:
    """Flush and shut down the tracer provider at shutdown."""
    global _tracer, _otel_ready
    if not _otel_ready:
        return
    try:
        from opentelemetry import trace as otel_trace

        provider = otel_trace.get_tracer_provider()
        shutdown = getattr(provider, "shutdown", None)
        if callable(shutdown):
            shutdown()
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("tracing.otel_shutdown_failed", extra={"error": str(exc)})
    finally:
        _tracer = None
        _otel_ready = False


def reset_tracing() -> None:
    """Drop tracer state without touching the SDK. Tests only."""
    global _tracer, _otel_ready
    _tracer = None
    _otel_ready = False
    _OTEL_KINDS.clear()
