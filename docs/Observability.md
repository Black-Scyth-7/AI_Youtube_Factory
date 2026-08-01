# Observability

Three signals, none of which require a collector to be useful:

| Signal      | Where it lives                        | Needs                        |
| ----------- | ------------------------------------- | ---------------------------- |
| **Logs**    | stdout, JSON when `LOG_JSON=true`     | nothing                      |
| **Metrics** | `GET /metrics`, Prometheus text       | nothing                      |
| **Traces**  | `trace.span` log records at DEBUG     | nothing                      |
| ↳ exported  | OTLP to a collector                   | `pip install -e ".[otel]"`   |

Every log record carries the `request_id` and `trace_id` of the work that
produced it, so a single request can be followed across all three.

## Running the stack

```bash
docker compose --profile observability up
```

- Prometheus — <http://localhost:9090> (scrapes the backend every 15s)
- Grafana — <http://localhost:3002>, anonymous viewer access, `admin`/`admin`
  to edit. The datasource and both dashboards are provisioned on start.

The profile keeps `docker compose up` as the application stack; two more
containers should be an opt-in.

## Metrics

`/metrics` is unversioned and at the root, because that is where every scraper
looks by default.

### Restricting it

The payload describes traffic shape, error rates, and spend — useful to an
operator and equally useful to someone mapping the service. Restrict it at the
network layer, or set `METRICS_TOKEN` and scrape with a bearer token:

```yaml
authorization:
  type: Bearer
  credentials_file: /etc/prometheus/scrape_token
```

`METRICS_ENABLED=false` makes the endpoint return 404, indistinguishable from
never having been mounted.

### The registry

`app/observability/metrics.py` is a small Prometheus-compatible registry with no
third-party dependency. `prometheus_client` was the obvious alternative; its
global registry does not survive a test suite that builds the application more
than once, since the second definition of a metric aborts the process.

Metrics are defined in one place, `app/observability/instruments.py`, so a name
in a dashboard query can be checked against the source.

### Label discipline

**Labels must be bounded sets.** A label carrying a user id, a raw URL path, or
anything else a client controls creates one time series per distinct value —
which is how a metrics endpoint takes down the process it was meant to be
monitoring.

Two things enforce this:

- HTTP metrics are labelled by the matched **route template**
  (`/api/v1/agents/{slug}`), never the request path. Requests matching no route
  share a single `__unmatched__` series, so a 404 probe sweep cannot create a
  series per probed path.
- Every metric caps itself at `MAX_SERIES_PER_METRIC` (2000). Past the cap, new
  series are dropped and one error is logged. Losing a label value beats losing
  the process.

`MetricsCardinalityCapped` in `infra/prometheus/alerts.yml` fires when a metric
sits at its ceiling.

### What is measured

| Area      | Metrics                                                                                             |
| --------- | --------------------------------------------------------------------------------------------------- |
| HTTP      | `http_requests_total`, `http_request_duration_seconds`, `http_requests_in_progress`, `http_request_exceptions_total` |
| LLM       | `llm_requests_total`, `llm_request_duration_seconds`, `llm_tokens_total`, `llm_cost_usd_total`       |
| Pipeline  | `pipeline_stages_total`, `pipeline_stage_duration_seconds`, `pipeline_artifact_bytes`                |
| Workflow  | `workflow_runs_total`, `workflow_run_duration_seconds`, `workflow_nodes_total`, `workflow_runs_in_progress` |
| Storage   | `storage_operations_total`, `storage_operation_duration_seconds`                                    |
| Build     | `app_info`                                                                                          |

Counters end in `_total` and are not auto-suffixed, so the name in the code is
the name in the query. Durations are in seconds and sizes in bytes, per
Prometheus convention — not milliseconds, however tempting.

### Adding a metric

```python
# app/observability/instruments.py
jobs_total = counter("jobs_total", "Jobs run, by kind and outcome.", ("kind", "outcome"))
```

```python
from app.observability import instruments

instruments.jobs_total.inc(kind="digest", outcome="succeeded")
```

Label names are checked on every call: passing a label the metric does not
declare raises rather than silently creating an empty second series.

## Tracing

Spans always work. `start_span` generates W3C-compatible ids, tracks the
parent/child stack in a context variable, and emits one `trace.span` log record
per completed span — enough to reconstruct a trace from logs alone.

```python
from app.observability import start_span

with start_span("render.encode", attributes={"codec": "h264"}) as span:
    span.set_attribute("frames", 1800)
```

Spans record exceptions and re-raise them; they never swallow one.

### Propagation

Requests carry [W3C Trace Context](https://www.w3.org/TR/trace-context/). An
inbound `traceparent` continues the caller's trace, so a request crossing
services shares one trace id; the response echoes `traceparent`, `X-Request-ID`,
and `X-Trace-ID`. A malformed header starts a fresh trace rather than failing
the request.

To propagate to a service this application calls:

```python
from app.observability import current_traceparent

headers = {"traceparent": current_traceparent() or ""}
```

Inbound `X-Request-ID` is echoed back and written into logs, so it is validated
against a conservative pattern and replaced when it does not match.

### Exporting to a collector

```bash
pip install -e ".[otel]"
export OTEL_ENABLED=true
export OTEL_EXPORTER_ENDPOINT=http://localhost:4318/v1/traces
export OTEL_SAMPLE_RATIO=0.1
```

Spans are then also recorded through the OpenTelemetry SDK and exported over
OTLP. With `OTEL_EXPORTER_ENDPOINT` blank, spans go to the console.

Enabling this without the extra installed logs a warning and keeps running on
the built-in tracer: a missing telemetry dependency is not a reason to refuse
to serve traffic. For the same reason, every OTel call is wrapped — telemetry
must never be the thing that fails a request.

## Alerting

`infra/prometheus/alerts.yml` holds 8 rules, all on symptoms a user would
notice — error rate, latency, a stalled pipeline, spend — rather than on causes
like CPU, which fire during healthy traffic spikes and end up silenced.

Every `for:` is longer than one scrape interval, so a single bad scrape pages
nobody. Validate changes before shipping them:

```bash
docker run --rm -v "$PWD/infra/prometheus:/etc/prometheus:ro" \
  --entrypoint promtool prom/prometheus:v3.1.0 \
  check config /etc/prometheus/prometheus.yml
```

## Dashboards

- **API overview** (`ayf-api-overview`) — rate, errors, latency percentiles,
  slowest routes, unhandled exceptions.
- **Pipeline and cost** (`ayf-pipeline-cost`) — stage throughput and duration,
  LLM spend and token use, workflow node outcomes, artifact sizes.

Both are provisioned from `infra/grafana/dashboards/`. Edits made in the
Grafana UI are allowed but live only in that container's database — export the
JSON back into the repository to keep them.
