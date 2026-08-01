"""Observability: metrics, tracing, and the scrape endpoint.

Three layers, none of which require a running collector to be useful:

* :mod:`app.observability.metrics` — a dependency-free Prometheus registry.
* :mod:`app.observability.instruments` — the application's metric definitions.
* :mod:`app.observability.tracing` — W3C spans, optionally exported via
  OpenTelemetry when the ``[otel]`` extra is installed.

Structured logging (:mod:`app.logging`) is the fourth: every log record carries
the request id and trace id of the work that produced it.
"""

from __future__ import annotations

from app.observability.metrics import (
    CONTENT_TYPE,
    REGISTRY,
    Counter,
    Gauge,
    Histogram,
    MetricsRegistry,
    counter,
    gauge,
    histogram,
    render,
)
from app.observability.tracing import (
    TRACEPARENT_HEADER,
    Span,
    SpanContext,
    configure_tracing,
    current_context,
    current_span,
    current_traceparent,
    new_span_id,
    new_trace_id,
    shutdown_tracing,
    start_span,
)

__all__ = [
    "CONTENT_TYPE",
    "REGISTRY",
    "TRACEPARENT_HEADER",
    "Counter",
    "Gauge",
    "Histogram",
    "MetricsRegistry",
    "Span",
    "SpanContext",
    "configure_tracing",
    "counter",
    "current_context",
    "current_span",
    "current_traceparent",
    "gauge",
    "histogram",
    "new_span_id",
    "new_trace_id",
    "render",
    "shutdown_tracing",
    "start_span",
]
