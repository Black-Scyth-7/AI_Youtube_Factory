"""The application's metric definitions.

One module so every name is declared once and a dashboard query can be checked
against the source. Metrics are cheap to define and free until observed, so
they live here rather than being scattered across the call sites that record
them.

Label discipline: labels are bounded sets — a method, a route template, a
provider slug, a status class. Never an id, a raw path, or anything a client
controls. See ``metrics.MAX_SERIES_PER_METRIC`` for what happens otherwise.
"""

from __future__ import annotations

from app.observability.metrics import (
    DEFAULT_BUCKETS,
    SIZE_BUCKETS,
    counter,
    gauge,
    histogram,
)

# -- HTTP ---------------------------------------------------------------------
http_requests_total = counter(
    "http_requests_total",
    "Total HTTP requests, by method, route template, and status code.",
    ("method", "route", "status"),
)
http_request_duration_seconds = histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds, by method and route template.",
    ("method", "route"),
    DEFAULT_BUCKETS,
)
http_requests_in_progress = gauge(
    "http_requests_in_progress",
    "HTTP requests currently being served, by method.",
    # Not labelled by route: the route is only known after routing has run,
    # and a gauge whose increment and decrement disagree never returns to zero.
    ("method",),
)
http_request_exceptions_total = counter(
    "http_request_exceptions_total",
    "HTTP requests that raised out of the handler, by route and exception type.",
    ("route", "exception"),
)

# -- Database -----------------------------------------------------------------
db_queries_total = counter(
    "db_queries_total",
    "Database statements executed, by operation.",
    ("operation",),
)
db_query_duration_seconds = histogram(
    "db_query_duration_seconds",
    "Database statement latency in seconds, by operation.",
    ("operation",),
    DEFAULT_BUCKETS,
)

# -- LLM ----------------------------------------------------------------------
llm_requests_total = counter(
    "llm_requests_total",
    "LLM requests, by provider, model, and outcome.",
    ("provider", "model", "outcome"),
)
llm_request_duration_seconds = histogram(
    "llm_request_duration_seconds",
    "LLM request latency in seconds, by provider and model.",
    ("provider", "model"),
    # An LLM call is slower than an HTTP handler; the default buckets top out
    # at 10s and would put most real completions in +Inf.
    (0.5, 1.0, 2.5, 5.0, 10.0, 20.0, 30.0, 60.0, 120.0, 300.0),
)
llm_tokens_total = counter(
    "llm_tokens_total",
    "Tokens consumed, by provider, model, and direction (input/output).",
    ("provider", "model", "direction"),
)
llm_cost_usd_total = counter(
    "llm_cost_usd_total",
    "Estimated LLM spend in USD, by provider and model.",
    ("provider", "model"),
)

# -- Video pipeline -----------------------------------------------------------
pipeline_stages_total = counter(
    "pipeline_stages_total",
    "Pipeline stages executed, by stage and outcome.",
    ("stage", "outcome"),
)
pipeline_stage_duration_seconds = histogram(
    "pipeline_stage_duration_seconds",
    "Pipeline stage duration in seconds, by stage.",
    ("stage",),
    # Rendering is measured in minutes, not milliseconds.
    (1.0, 5.0, 15.0, 30.0, 60.0, 300.0, 900.0, 1800.0, 3600.0),
)
pipeline_artifact_bytes = histogram(
    "pipeline_artifact_bytes",
    "Size in bytes of artifacts produced, by stage.",
    ("stage",),
    SIZE_BUCKETS,
)

# -- Workflow engine ----------------------------------------------------------
workflow_runs_total = counter(
    "workflow_runs_total",
    "Workflow runs, by outcome.",
    ("outcome",),
)
workflow_run_duration_seconds = histogram(
    "workflow_run_duration_seconds",
    "Workflow run duration in seconds.",
    (),
    (0.1, 0.5, 1.0, 5.0, 15.0, 60.0, 300.0, 900.0, 3600.0),
)
workflow_nodes_total = counter(
    "workflow_nodes_total",
    "Workflow nodes executed, by node type and outcome.",
    ("node_type", "outcome"),
)
workflow_runs_in_progress = gauge(
    "workflow_runs_in_progress",
    "Workflow runs currently executing.",
)

# -- Storage ------------------------------------------------------------------
storage_operations_total = counter(
    "storage_operations_total",
    "Storage operations, by backend, operation, and outcome.",
    ("backend", "operation", "outcome"),
)
storage_operation_duration_seconds = histogram(
    "storage_operation_duration_seconds",
    "Storage operation latency in seconds, by backend and operation.",
    ("backend", "operation"),
    DEFAULT_BUCKETS,
)

# -- Payments -----------------------------------------------------------------
payments_total = counter(
    "payments_total",
    "Payment attempts, by provider and outcome (succeeded/declined/refunded).",
    ("provider", "outcome"),
)
payments_collected_cents_total = counter(
    "payments_collected_cents_total",
    "Money successfully collected, in minor units, by provider.",
    ("provider",),
)
payment_webhooks_total = counter(
    "payment_webhooks_total",
    "Verified provider callbacks, by provider and event type.",
    ("provider", "event_type"),
)

# -- Application --------------------------------------------------------------
app_info = gauge(
    "app_info",
    "Build and environment information; the value is always 1.",
    ("version", "environment"),
)
