"""Prometheus-compatible metrics, implemented in process.

Deliberately dependency-free. The text exposition format is small and stable,
and ``prometheus_client``'s global registry does not survive the test suite
importing an application factory repeatedly — a duplicate time series aborts
the process. Everything here is import-safe, resettable, and works offline.

Naming follows the Prometheus conventions: base units (seconds, bytes), a
``_total`` suffix on counters, and a unit suffix on everything else. Counter
names are *not* auto-suffixed; spell out ``_total`` at the call site so the
name in the code matches the name in a dashboard query.

Every metric caps its series count. Labelling by an unbounded value (a user id,
a raw URL path) is the classic way to turn a metrics endpoint into an outage;
this drops new series past the cap and logs once instead of exhausting memory.
"""

from __future__ import annotations

import math
import re
import threading
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from typing import ClassVar, Final, TypeVar

from app.logging import get_logger

logger = get_logger(__name__)

#: Scrape response content type for the Prometheus text format.
CONTENT_TYPE: Final = "text/plain; version=0.0.4; charset=utf-8"

_NAME_RE: Final = re.compile(r"^[a-zA-Z_:][a-zA-Z0-9_:]*$")
_LABEL_RE: Final = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

#: Per-metric series ceiling. Generous for well-chosen labels, fatal for a
#: label accidentally carrying an identifier.
MAX_SERIES_PER_METRIC: Final = 2000

#: Latency buckets in seconds, spanning a fast cache hit to a stalled upstream.
DEFAULT_BUCKETS: Final[tuple[float, ...]] = (
    0.005,
    0.01,
    0.025,
    0.05,
    0.1,
    0.25,
    0.5,
    1.0,
    2.5,
    5.0,
    10.0,
)

#: Buckets for payload and artifact sizes, 1 KiB to 1 GiB.
SIZE_BUCKETS: Final[tuple[float, ...]] = (
    1024.0,
    16384.0,
    262144.0,
    1048576.0,
    16777216.0,
    268435456.0,
    1073741824.0,
)

_LabelKey = tuple[str, ...]


def _format_float(value: float) -> str:
    """Render a float the way the exposition format expects."""
    if math.isnan(value):
        return "NaN"
    if math.isinf(value):
        return "+Inf" if value > 0 else "-Inf"
    if value.is_integer() and abs(value) < 1e15:
        return str(int(value))
    return repr(value)


def _escape_label_value(value: str) -> str:
    """Escape a label value: backslash, double quote, and newline."""
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _render_labels(names: tuple[str, ...], values: _LabelKey, extra: str = "") -> str:
    """Render a ``{a="1",b="2"}`` label set, empty string when there are none."""
    parts = [
        f'{n}="{_escape_label_value(v)}"' for n, v in zip(names, values, strict=True)
    ]
    if extra:
        parts.append(extra)
    return "{" + ",".join(parts) + "}" if parts else ""


@dataclass(frozen=True, slots=True)
class Sample:
    """One rendered time series point."""

    name: str
    labels: str
    value: float

    def render(self) -> str:
        return f"{self.name}{self.labels} {_format_float(self.value)}"


class Metric:
    """Base class holding naming, labels, locking, and the series cap."""

    type_: ClassVar[str] = "untyped"

    def __init__(
        self, name: str, documentation: str, labelnames: tuple[str, ...] = ()
    ) -> None:
        if not _NAME_RE.match(name):
            raise ValueError(f"Invalid metric name: {name!r}")
        for label in labelnames:
            if not _LABEL_RE.match(label):
                raise ValueError(f"Invalid label name: {label!r}")
            if label.startswith("__"):
                raise ValueError(
                    f"Label names starting with '__' are reserved: {label!r}"
                )
        if len(set(labelnames)) != len(labelnames):
            raise ValueError(f"Duplicate label names for {name!r}: {labelnames!r}")

        self.name = name
        self.documentation = documentation
        self.labelnames = labelnames
        self._lock = threading.Lock()
        self._overflowed = False

    def _key(self, labels: Mapping[str, object]) -> _LabelKey:
        """Order a label mapping into a series key, rejecting a mismatch.

        A typo in a label name would otherwise create a second, silently empty
        series rather than an error anyone notices.
        """
        if labels.keys() != set(self.labelnames):
            expected = ", ".join(self.labelnames) or "(none)"
            got = ", ".join(sorted(str(k) for k in labels)) or "(none)"
            raise ValueError(
                f"Metric {self.name!r} expects labels [{expected}] but got [{got}]"
            )
        return tuple(str(labels[name]) for name in self.labelnames)

    def _admit(self, key: _LabelKey, known: int) -> bool:
        """Whether a new series may be created. Caller holds the lock."""
        if known < MAX_SERIES_PER_METRIC:
            return True
        if not self._overflowed:
            self._overflowed = True
            logger.error(
                "metrics.cardinality_exceeded",
                extra={
                    "metric": self.name,
                    "limit": MAX_SERIES_PER_METRIC,
                    "labelnames": list(self.labelnames),
                },
            )
        return False

    def collect(self) -> Iterator[Sample]:  # pragma: no cover - overridden
        raise NotImplementedError

    def render(self) -> str:
        """Render this metric as an exposition-format block."""
        lines = [
            f"# HELP {self.name} {self.documentation}",
            f"# TYPE {self.name} {self.type_}",
        ]
        lines.extend(sample.render() for sample in self.collect())
        return "\n".join(lines)


class Counter(Metric):
    """A monotonically increasing total."""

    type_: ClassVar[str] = "counter"

    def __init__(
        self, name: str, documentation: str, labelnames: tuple[str, ...] = ()
    ) -> None:
        super().__init__(name, documentation, labelnames)
        self._values: dict[_LabelKey, float] = {}
        if not labelnames:
            self._values[()] = 0.0

    def inc(self, amount: float = 1.0, /, **labels: object) -> None:
        """Add ``amount`` (which must not be negative) to a series."""
        if amount < 0:
            raise ValueError(f"Counter {self.name!r} cannot decrease (got {amount})")
        key = self._key(labels)
        with self._lock:
            if key in self._values:
                self._values[key] += amount
            elif self._admit(key, len(self._values)):
                self._values[key] = amount

    def value(self, **labels: object) -> float:
        """Current value of a series; 0.0 if never incremented."""
        key = self._key(labels)
        with self._lock:
            return self._values.get(key, 0.0)

    def collect(self) -> Iterator[Sample]:
        with self._lock:
            items = sorted(self._values.items())
        for key, value in items:
            yield Sample(self.name, _render_labels(self.labelnames, key), value)


class Gauge(Metric):
    """A value that goes up and down."""

    type_: ClassVar[str] = "gauge"

    def __init__(
        self, name: str, documentation: str, labelnames: tuple[str, ...] = ()
    ) -> None:
        super().__init__(name, documentation, labelnames)
        self._values: dict[_LabelKey, float] = {}
        if not labelnames:
            self._values[()] = 0.0

    def set(self, value: float, /, **labels: object) -> None:
        key = self._key(labels)
        with self._lock:
            if key in self._values or self._admit(key, len(self._values)):
                self._values[key] = value

    def inc(self, amount: float = 1.0, /, **labels: object) -> None:
        key = self._key(labels)
        with self._lock:
            if key in self._values:
                self._values[key] += amount
            elif self._admit(key, len(self._values)):
                self._values[key] = amount

    def dec(self, amount: float = 1.0, /, **labels: object) -> None:
        self.inc(-amount, **labels)

    def value(self, **labels: object) -> float:
        key = self._key(labels)
        with self._lock:
            return self._values.get(key, 0.0)

    def collect(self) -> Iterator[Sample]:
        with self._lock:
            items = sorted(self._values.items())
        for key, value in items:
            yield Sample(self.name, _render_labels(self.labelnames, key), value)


@dataclass(slots=True)
class _Bucketed:
    """Cumulative bucket counts, sum, and count for one histogram series."""

    counts: list[float]
    total: float = 0.0
    count: float = 0.0

    @classmethod
    def for_buckets(cls, buckets: tuple[float, ...]) -> _Bucketed:
        return cls(counts=[0.0] * len(buckets))


class Histogram(Metric):
    """Bucketed observations, exposing ``_bucket``, ``_sum``, and ``_count``."""

    type_: ClassVar[str] = "histogram"

    def __init__(
        self,
        name: str,
        documentation: str,
        labelnames: tuple[str, ...] = (),
        buckets: tuple[float, ...] = DEFAULT_BUCKETS,
    ) -> None:
        super().__init__(name, documentation, labelnames)
        if "le" in labelnames:
            raise ValueError("'le' is reserved for histogram bucket boundaries")
        if not buckets:
            raise ValueError(f"Histogram {name!r} needs at least one bucket")
        finite = tuple(b for b in buckets if not math.isinf(b))
        if list(finite) != sorted(finite):
            raise ValueError(f"Histogram {name!r} buckets must be ascending: {buckets!r}")
        #: +Inf is implicit in the constructor and explicit in the output.
        self.buckets = (*finite, math.inf)
        self._values: dict[_LabelKey, _Bucketed] = {}
        if not labelnames:
            self._values[()] = _Bucketed.for_buckets(self.buckets)

    def observe(self, value: float, /, **labels: object) -> None:
        """Record one observation."""
        key = self._key(labels)
        with self._lock:
            series = self._values.get(key)
            if series is None:
                if not self._admit(key, len(self._values)):
                    return
                series = _Bucketed.for_buckets(self.buckets)
                self._values[key] = series
            series.total += value
            series.count += 1
            for index, bound in enumerate(self.buckets):
                if value <= bound:
                    series.counts[index] += 1

    def count(self, **labels: object) -> float:
        key = self._key(labels)
        with self._lock:
            series = self._values.get(key)
            return series.count if series else 0.0

    def sum(self, **labels: object) -> float:
        key = self._key(labels)
        with self._lock:
            series = self._values.get(key)
            return series.total if series else 0.0

    def collect(self) -> Iterator[Sample]:
        with self._lock:
            items = [
                (key, series.counts[:], series.total, series.count)
                for key, series in sorted(self._values.items())
            ]
        for key, counts, total, count in items:
            for bound, bucket_count in zip(self.buckets, counts, strict=True):
                labels = _render_labels(
                    self.labelnames, key, f'le="{_format_float(bound)}"'
                )
                yield Sample(f"{self.name}_bucket", labels, bucket_count)
            plain = _render_labels(self.labelnames, key)
            yield Sample(f"{self.name}_sum", plain, total)
            yield Sample(f"{self.name}_count", plain, count)


_M = TypeVar("_M", bound=Metric)


@dataclass(slots=True)
class MetricsRegistry:
    """Holds registered metrics and renders a scrape response."""

    _metrics: dict[str, Metric] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def register(self, metric: _M) -> _M:
        """Register ``metric``, or return the equivalent already registered.

        Idempotent on purpose: module-level metric definitions are evaluated
        again whenever a test reloads a module, and raising there would make
        metrics the reason a test suite fails.
        """
        with self._lock:
            existing = self._metrics.get(metric.name)
            if existing is None:
                self._metrics[metric.name] = metric
                return metric

        if type(existing) is not type(metric) or existing.labelnames != metric.labelnames:
            raise ValueError(
                f"Metric {metric.name!r} is already registered as "
                f"{type(existing).__name__}{list(existing.labelnames)}, cannot "
                f"re-register as {type(metric).__name__}{list(metric.labelnames)}"
            )
        # The types match, so the caller wants the same metric it asked for
        # before; hand back the live one so both call sites share counts.
        return existing

    def unregister(self, name: str) -> None:
        with self._lock:
            self._metrics.pop(name, None)

    def clear(self) -> None:
        """Drop every metric. Tests only."""
        with self._lock:
            self._metrics.clear()

    def names(self) -> list[str]:
        with self._lock:
            return sorted(self._metrics)

    def render(self) -> str:
        """Render the full exposition payload, newline-terminated."""
        with self._lock:
            metrics = [self._metrics[name] for name in sorted(self._metrics)]
        blocks = [metric.render() for metric in metrics]
        return "\n".join(blocks) + "\n" if blocks else ""


#: The registry the application scrapes.
REGISTRY: Final = MetricsRegistry()


def counter(name: str, documentation: str, labelnames: tuple[str, ...] = ()) -> Counter:
    """Define a counter on the default registry."""
    return REGISTRY.register(Counter(name, documentation, labelnames))


def gauge(name: str, documentation: str, labelnames: tuple[str, ...] = ()) -> Gauge:
    """Define a gauge on the default registry."""
    return REGISTRY.register(Gauge(name, documentation, labelnames))


def histogram(
    name: str,
    documentation: str,
    labelnames: tuple[str, ...] = (),
    buckets: tuple[float, ...] = DEFAULT_BUCKETS,
) -> Histogram:
    """Define a histogram on the default registry."""
    return REGISTRY.register(Histogram(name, documentation, labelnames, buckets))


def render() -> str:
    """Render the default registry."""
    return REGISTRY.render()
