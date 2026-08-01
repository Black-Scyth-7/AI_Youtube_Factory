"""Tests for the metrics registry and the tracer."""

from __future__ import annotations

import logging
import math
import threading
from typing import Any

import pytest
from app.logging.context import trace_id_var
from app.observability.metrics import (
    MAX_SERIES_PER_METRIC,
    Counter,
    Gauge,
    Histogram,
    MetricsRegistry,
)
from app.observability.tracing import SpanContext, start_span

# -- Counters -----------------------------------------------------------------


def test_counter_accumulates_per_label_set() -> None:
    c = Counter("requests_total", "doc", ("method",))
    c.inc(method="GET")
    c.inc(2.0, method="GET")
    c.inc(method="POST")
    assert c.value(method="GET") == 3.0
    assert c.value(method="POST") == 1.0


def test_counter_rejects_a_decrease() -> None:
    """A counter that can go down breaks every rate() query built on it."""
    c = Counter("requests_total", "doc")
    with pytest.raises(ValueError, match="cannot decrease"):
        c.inc(-1.0)


def test_counter_without_labels_renders_zero_before_use() -> None:
    """An absent series and a zero series mean different things to an alert."""
    assert "requests_total 0" in Counter("requests_total", "doc").render()


def test_wrong_label_names_raise() -> None:
    """A typo would otherwise create a second, permanently empty series."""
    c = Counter("requests_total", "doc", ("method",))
    with pytest.raises(ValueError, match="expects labels"):
        c.inc(methd="GET")
    with pytest.raises(ValueError, match="expects labels"):
        c.inc(method="GET", extra="x")


def test_invalid_names_are_rejected() -> None:
    with pytest.raises(ValueError, match="Invalid metric name"):
        Counter("has-a-dash", "doc")
    with pytest.raises(ValueError, match="Invalid label name"):
        Counter("ok_total", "doc", ("has-a-dash",))
    with pytest.raises(ValueError, match="reserved"):
        Counter("ok_total", "doc", ("__reserved",))
    with pytest.raises(ValueError, match="Duplicate"):
        Counter("ok_total", "doc", ("a", "a"))


# -- Cardinality --------------------------------------------------------------


def test_series_count_is_capped(caplog: pytest.LogCaptureFixture) -> None:
    """The cap is what stops an id-valued label from exhausting memory."""
    c = Counter("leaky_total", "doc", ("id",))
    with caplog.at_level(logging.ERROR):
        for i in range(MAX_SERIES_PER_METRIC + 50):
            c.inc(id=str(i))

    rendered = c.render()
    assert rendered.count("\n") - 1 == MAX_SERIES_PER_METRIC
    assert "metrics.cardinality_exceeded" in caplog.text
    # Logged once, not once per dropped series.
    assert caplog.text.count("metrics.cardinality_exceeded") == 1
    # Series admitted before the cap keep counting.
    c.inc(id="0")
    assert c.value(id="0") == 2.0


# -- Gauges -------------------------------------------------------------------


def test_gauge_goes_both_ways() -> None:
    g = Gauge("in_flight", "doc", ("method",))
    g.inc(method="GET")
    g.inc(method="GET")
    g.dec(method="GET")
    assert g.value(method="GET") == 1.0
    g.set(0.0, method="GET")
    assert g.value(method="GET") == 0.0


# -- Histograms ---------------------------------------------------------------


def test_histogram_buckets_are_cumulative() -> None:
    """Prometheus buckets are 'less than or equal', so each contains the last."""
    h = Histogram("latency_seconds", "doc", (), (0.1, 1.0))
    for value in (0.05, 0.5, 5.0):
        h.observe(value)

    lines = {
        line.rsplit(" ", 1)[0]: float(line.rsplit(" ", 1)[1])
        for line in h.render().splitlines()
        if not line.startswith("#")
    }
    assert lines['latency_seconds_bucket{le="0.1"}'] == 1
    assert lines['latency_seconds_bucket{le="1"}'] == 2
    assert lines['latency_seconds_bucket{le="+Inf"}'] == 3
    assert lines["latency_seconds_count"] == 3
    assert lines["latency_seconds_sum"] == pytest.approx(5.55)


def test_histogram_appends_the_infinity_bucket() -> None:
    h = Histogram("latency_seconds", "doc", (), (0.1,))
    assert h.buckets == (0.1, math.inf)


def test_histogram_rejects_unordered_buckets() -> None:
    with pytest.raises(ValueError, match="ascending"):
        Histogram("latency_seconds", "doc", (), (1.0, 0.1))


def test_histogram_rejects_the_le_label() -> None:
    """'le' is the bucket boundary; a user label of that name would collide."""
    with pytest.raises(ValueError, match="reserved"):
        Histogram("latency_seconds", "doc", ("le",))


# -- Exposition format --------------------------------------------------------


def test_label_values_are_escaped() -> None:
    """An unescaped quote or newline produces a payload no scraper can parse."""
    c = Counter("errors_total", "doc", ("message",))
    c.inc(message='say "hi"\nand \\bye')
    assert 'message="say \\"hi\\"\\nand \\\\bye"' in c.render()


def test_render_has_help_and_type_lines() -> None:
    body = Counter("requests_total", "How many.", ("method",)).render()
    assert body.splitlines()[0] == "# HELP requests_total How many."
    assert body.splitlines()[1] == "# TYPE requests_total counter"


def test_integral_values_render_without_a_decimal_point() -> None:
    c = Counter("requests_total", "doc")
    c.inc(3.0)
    assert c.render().endswith("requests_total 3")


# -- Registry -----------------------------------------------------------------


def test_registering_the_same_metric_twice_returns_the_original() -> None:
    """Module reloads re-run metric definitions; that must not be fatal."""
    registry = MetricsRegistry()
    first = registry.register(Counter("requests_total", "doc", ("method",)))
    second = registry.register(Counter("requests_total", "doc", ("method",)))
    assert first is second

    first.inc(method="GET")
    assert second.value(method="GET") == 1.0


def test_registering_a_conflicting_metric_raises() -> None:
    registry = MetricsRegistry()
    registry.register(Counter("thing_total", "doc", ("a",)))
    with pytest.raises(ValueError, match="already registered"):
        registry.register(Gauge("thing_total", "doc", ("a",)))
    with pytest.raises(ValueError, match="already registered"):
        registry.register(Counter("thing_total", "doc", ("b",)))


def test_registry_renders_every_metric_sorted_and_newline_terminated() -> None:
    registry = MetricsRegistry()
    registry.register(Counter("z_total", "doc"))
    registry.register(Counter("a_total", "doc"))
    body = registry.render()
    assert body.index("a_total") < body.index("z_total")
    assert body.endswith("\n")


def test_empty_registry_renders_empty() -> None:
    assert MetricsRegistry().render() == ""


def test_counters_are_thread_safe() -> None:
    """Metrics are written from request threads and read by the scrape."""
    c = Counter("requests_total", "doc")
    threads = [
        threading.Thread(target=lambda: [c.inc() for _ in range(500)]) for _ in range(8)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert c.value() == 4000.0


# -- Trace context ------------------------------------------------------------


def test_traceparent_round_trips() -> None:
    context = SpanContext("0" * 31 + "1", "0" * 15 + "2", sampled=True)
    assert context.to_traceparent() == f"00-{'0' * 31}1-{'0' * 15}2-01"
    assert SpanContext.parse(context.to_traceparent()) == context


def test_unsampled_flag_round_trips() -> None:
    context = SpanContext("a" * 32, "b" * 16, sampled=False)
    parsed = SpanContext.parse(context.to_traceparent())
    assert parsed is not None and parsed.sampled is False


@pytest.mark.parametrize(
    "header",
    [
        "",
        "garbage",
        "00-tooshort-0000000000000001-01",
        f"00-{'0' * 32}-{'0' * 15}1-01",  # all-zero trace id is invalid
        f"00-{'a' * 32}-{'0' * 16}-01",  # all-zero span id is invalid
        f"ff-{'a' * 32}-{'b' * 16}-01",  # version ff is forbidden
    ],
)
def test_unusable_traceparent_starts_a_new_trace(header: str) -> None:
    """A bad header is the caller's problem; this service still serves."""
    assert SpanContext.parse(header) is None


def test_traceparent_is_case_insensitive() -> None:
    assert SpanContext.parse(f"00-{'A' * 32}-{'B' * 16}-01") is not None


# -- Spans --------------------------------------------------------------------


def test_nested_spans_share_a_trace_and_chain_parents() -> None:
    with start_span("outer") as outer, start_span("inner") as inner:
        assert inner.trace_id == outer.trace_id
        assert inner.parent_span_id == outer.span_id
        assert inner.span_id != outer.span_id


def test_a_span_continues_an_inbound_trace() -> None:
    parent = SpanContext("c" * 32, "d" * 16)
    with start_span("server", parent=parent) as span:
        assert span.trace_id == parent.trace_id
        assert span.parent_span_id == parent.span_id


def test_span_binds_the_trace_id_for_logging_and_restores_it() -> None:
    """Log records inside the span must carry the id a trace viewer searches."""
    assert trace_id_var.get() is None
    with start_span("work") as span:
        assert trace_id_var.get() == span.trace_id
    assert trace_id_var.get() is None


def test_span_records_an_exception_without_swallowing_it() -> None:
    with pytest.raises(RuntimeError, match="boom"), start_span("work") as span:
        raise RuntimeError("boom")

    assert span.status == "error"
    assert span.error == "RuntimeError: boom"
    assert span.end is not None


def test_span_duration_is_recorded_once_closed() -> None:
    with start_span("work") as span:
        pass
    first = span.duration_ms
    assert first >= 0.0
    # A closed span's duration must not keep growing.
    assert span.duration_ms == first


def test_span_attributes_are_captured() -> None:
    with start_span("work", attributes={"a": 1}) as span:
        span.set_attribute("b", 2)
        span.set_attributes({"c": 3})
    assert span.attributes == {"a": 1, "b": 2, "c": 3}


# -- The OpenTelemetry bridge -------------------------------------------------
# Optional: the extra is not installed in CI, so these skip rather than fail.


def test_tracing_stays_off_unless_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.config import settings
    from app.observability import tracing

    monkeypatch.setattr(settings, "otel_enabled", False)
    monkeypatch.setattr(tracing, "_tracer", None)
    tracing.configure_tracing()
    assert tracing._tracer is None


def test_enabling_without_the_sdk_warns_and_keeps_serving(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A missing telemetry dependency must not stop the application starting."""
    import builtins

    from app.config import settings
    from app.observability import tracing

    real_import = builtins.__import__

    def no_otel(name: str, *args: object, **kwargs: object) -> object:
        if name.startswith("opentelemetry"):
            raise ImportError(f"No module named {name!r}")
        return real_import(name, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(settings, "otel_enabled", True)
    monkeypatch.setattr(tracing, "_tracer", None)
    monkeypatch.setattr(tracing, "_otel_ready", False)
    monkeypatch.setattr(builtins, "__import__", no_otel)

    with caplog.at_level(logging.WARNING):
        tracing.configure_tracing()

    assert "tracing.otel_unavailable" in caplog.text
    assert tracing._tracer is None

    # And the built-in tracer still produces a usable span.
    monkeypatch.setattr(builtins, "__import__", real_import)
    with start_span("still works") as span:
        assert len(span.trace_id) == 32


@pytest.fixture()
def otel_tracer(monkeypatch: pytest.MonkeyPatch) -> object:
    """Configure the SDK against an in-memory exporter, or skip."""
    pytest.importorskip("opentelemetry.sdk", reason="needs the [otel] extra")
    from app.observability import tracing
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import (
        InMemorySpanExporter,
    )

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))

    from opentelemetry.trace import SpanKind

    monkeypatch.setattr(tracing, "_tracer", provider.get_tracer("test"))
    # configure_tracing() normally fills this in; the fixture bypasses it.
    monkeypatch.setattr(
        tracing,
        "_OTEL_KINDS",
        {
            "internal": SpanKind.INTERNAL,
            "server": SpanKind.SERVER,
            "client": SpanKind.CLIENT,
        },
    )
    return exporter


def test_exported_span_ids_match_the_logged_ids(otel_tracer: Any) -> None:
    """The whole point of correlation: the id in the log is the id in the
    trace viewer. These used to be generated independently."""
    with start_span("work") as span:
        pass

    exported = otel_tracer.get_finished_spans()
    assert len(exported) == 1
    context = exported[0].get_span_context()
    assert format(context.trace_id, "032x") == span.trace_id
    assert format(context.span_id, "016x") == span.span_id


def test_exported_spans_form_one_connected_trace(otel_tracer: Any) -> None:
    """Without an explicit parent context the SDK makes every span a root, and
    the exported trace is a pile of unrelated single-span traces."""
    with start_span("outer") as outer, start_span("inner") as inner:
        pass

    by_name = {s.name: s for s in otel_tracer.get_finished_spans()}
    assert by_name["inner"].parent.span_id == by_name["outer"].get_span_context().span_id
    assert (
        by_name["inner"].get_span_context().trace_id
        == by_name["outer"].get_span_context().trace_id
    )
    assert format(by_name["outer"].get_span_context().trace_id, "032x") == outer.trace_id
    assert inner.parent_span_id == outer.span_id


def test_an_exported_span_continues_an_inbound_trace(otel_tracer: Any) -> None:
    from opentelemetry.trace import SpanKind

    inbound = SpanContext("a" * 32, "b" * 16)
    with start_span("server", kind="server", parent=inbound):
        pass

    exported = otel_tracer.get_finished_spans()[0]
    assert exported.kind is SpanKind.SERVER
    assert exported.parent.is_remote, "an inbound trace's parent is another service"
    assert format(exported.get_span_context().trace_id, "032x") == inbound.trace_id
    assert format(exported.parent.span_id, "016x") == inbound.span_id


def test_an_exported_span_records_its_failure(otel_tracer: Any) -> None:
    from opentelemetry.trace import StatusCode

    with pytest.raises(RuntimeError), start_span("work"):
        raise RuntimeError("boom")

    exported = otel_tracer.get_finished_spans()[0]
    assert exported.status.status_code is StatusCode.ERROR
    assert exported.events, "the exception should be recorded as a span event"
