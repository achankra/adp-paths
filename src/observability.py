"""
Observability Infrastructure — L01 Platform Telemetry

Three components that provide structured observability across the platform:
    Tracer           — OpenTelemetry-compatible span tracking with parent-child
    Metrics          — Prometheus-compatible counters, gauges, histograms
    StructuredLogger — JSON event log emitter with severity and context

This is L01 infrastructure — the same observability fabric that captures
pipeline telemetry also captures agent telemetry. GOVERNANCE.Observability
(L03) wraps this infrastructure for agent-specific events.

    "Observability is not logging. Observability is the ability to ask
     new questions of your system without deploying new code."
    — The Platform Engineer's Handbook, Chapter 4

PEH Reference:
    Chapter 4  — Embedding Observability (OpenTelemetry, metrics, traces)
    Chapter 14 — Agentic Platforms (agent telemetry, audit trails)

Companion code: github.com/achankra/peh, ch04/observability.py
"""

from __future__ import annotations

import json
import secrets
import string
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


# ── Tracer — OpenTelemetry-Compatible Spans ─────────────────────


class SpanStatus(str, Enum):
    """Span completion status — mirrors OpenTelemetry StatusCode."""

    OK = "ok"
    ERROR = "error"
    UNSET = "unset"


def _generate_id(length: int = 16) -> str:
    """Generate a hex ID for traces and spans."""
    alphabet = string.hexdigits[:16]
    return "".join(secrets.choice(alphabet) for _ in range(length))


@dataclass
class Span:
    """
    OpenTelemetry-compatible span.

    Each span represents a unit of work — a pipeline stage, an agent
    execution, a governance check. Spans nest via parent_span_id to
    form a trace tree.

    PEH Ch.4: "A trace is a tree of spans. The root span is the
    request. Each child span is a unit of work within that request."
    Companion: github.com/achankra/peh, ch04/tracing.py
    """

    name: str
    trace_id: str = field(default_factory=lambda: _generate_id(32))
    span_id: str = field(default_factory=lambda: _generate_id(16))
    parent_span_id: str | None = None
    start_time: float = field(default_factory=time.time)
    end_time: float | None = None
    status: SpanStatus = SpanStatus.UNSET
    attributes: dict[str, Any] = field(default_factory=dict)
    events: list[dict] = field(default_factory=list)

    def add_event(self, name: str, attributes: dict | None = None):
        """Add a timestamped event to the span."""
        self.events.append({
            "name": name,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "attributes": attributes or {},
        })

    def set_attribute(self, key: str, value: Any):
        """Set a span attribute."""
        self.attributes[key] = value

    def end(self, status: SpanStatus = SpanStatus.OK):
        """End the span with a status."""
        self.end_time = time.time()
        self.status = status

    @property
    def duration_ms(self) -> float | None:
        """Span duration in milliseconds."""
        if self.end_time is None:
            return None
        return (self.end_time - self.start_time) * 1000

    def to_dict(self) -> dict:
        """Export span as a dictionary (OpenTelemetry-compatible structure)."""
        return {
            "traceId": self.trace_id,
            "spanId": self.span_id,
            "parentSpanId": self.parent_span_id,
            "name": self.name,
            "startTimeUnixNano": int(self.start_time * 1e9),
            "endTimeUnixNano": int(self.end_time * 1e9) if self.end_time else None,
            "status": {"code": self.status.value},
            "attributes": self.attributes,
            "events": self.events,
            "durationMs": self.duration_ms,
        }


class Tracer:
    """
    Span tracer — creates, manages, and exports spans.

    PEH Ch.4: "The tracer is the entry point. Every platform action
    starts a span. Every span has a parent, except the root."
    Companion: github.com/achankra/peh, ch04/tracer.py
    """

    def __init__(self, service_name: str = "adp-paths"):
        self.service_name = service_name
        self._spans: list[Span] = []

    def start_span(
        self,
        name: str,
        parent: Span | None = None,
        attributes: dict | None = None,
    ) -> Span:
        """Start a new span, optionally as a child of a parent span."""
        span = Span(
            name=name,
            trace_id=parent.trace_id if parent else _generate_id(32),
            parent_span_id=parent.span_id if parent else None,
            attributes={"service.name": self.service_name, **(attributes or {})},
        )
        self._spans.append(span)
        return span

    def end_span(self, span: Span, status: SpanStatus = SpanStatus.OK):
        """End a span with the given status."""
        span.end(status)

    def get_spans(self) -> list[Span]:
        """Return all recorded spans."""
        return list(self._spans)

    def get_traces(self) -> dict[str, list[Span]]:
        """Group spans by trace ID."""
        traces: dict[str, list[Span]] = {}
        for span in self._spans:
            traces.setdefault(span.trace_id, []).append(span)
        return traces

    def export_json(self) -> list[dict]:
        """Export all spans as JSON-serializable dicts."""
        return [s.to_dict() for s in self._spans]

    def reset(self):
        """Clear all recorded spans."""
        self._spans.clear()


# ── Metrics — Prometheus-Compatible Counters/Gauges/Histograms ──


@dataclass
class MetricPoint:
    """A single metric data point."""

    name: str
    type: str  # counter, gauge, histogram
    value: float
    labels: dict[str, str] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class Metrics:
    """
    Prometheus-compatible metrics collector.

    Supports counters (monotonically increasing), gauges (point-in-time
    values), and histograms (distribution of values).

    PEH Ch.4: "Metrics answer 'how much' and 'how fast.' Counters
    for totals, gauges for current state, histograms for latency."
    Companion: github.com/achankra/peh, ch04/metrics.py
    """

    def __init__(self):
        self._counters: dict[str, float] = {}
        self._gauges: dict[str, float] = {}
        self._histograms: dict[str, list[float]] = {}
        self._labels: dict[str, dict[str, str]] = {}
        self._points: list[MetricPoint] = []

    def _key(self, name: str, labels: dict[str, str] | None = None) -> str:
        """Create a unique key for a metric + label combination."""
        if not labels:
            return name
        label_str = ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"

    def counter(self, name: str, value: float = 1, labels: dict[str, str] | None = None):
        """Increment a counter by value (default 1)."""
        key = self._key(name, labels)
        self._counters[key] = self._counters.get(key, 0) + value
        self._labels[key] = labels or {}
        self._points.append(MetricPoint(name=name, type="counter", value=self._counters[key], labels=labels or {}))

    def gauge(self, name: str, value: float, labels: dict[str, str] | None = None):
        """Set a gauge to a specific value."""
        key = self._key(name, labels)
        self._gauges[key] = value
        self._labels[key] = labels or {}
        self._points.append(MetricPoint(name=name, type="gauge", value=value, labels=labels or {}))

    def histogram(self, name: str, value: float, labels: dict[str, str] | None = None):
        """Record a value in a histogram (for latency distributions)."""
        key = self._key(name, labels)
        self._histograms.setdefault(key, []).append(value)
        self._labels[key] = labels or {}
        self._points.append(MetricPoint(name=name, type="histogram", value=value, labels=labels or {}))

    def get_counter(self, name: str, labels: dict[str, str] | None = None) -> float:
        """Get current counter value."""
        return self._counters.get(self._key(name, labels), 0)

    def get_gauge(self, name: str, labels: dict[str, str] | None = None) -> float:
        """Get current gauge value."""
        return self._gauges.get(self._key(name, labels), 0)

    def get_histogram(self, name: str, labels: dict[str, str] | None = None) -> list[float]:
        """Get histogram values."""
        return list(self._histograms.get(self._key(name, labels), []))

    def export_prometheus(self) -> str:
        """
        Export metrics in Prometheus text exposition format.

        PEH Ch.4: "Prometheus scrapes /metrics. The format is
        human-readable and machine-parseable."
        Companion: github.com/achankra/peh, ch04/prometheus_exporter.py
        """
        lines = []
        seen_help: set[str] = set()

        for key, value in sorted(self._counters.items()):
            name = key.split("{")[0]
            if name not in seen_help:
                lines.append(f"# TYPE {name} counter")
                seen_help.add(name)
            lines.append(f"{key} {value}")

        for key, value in sorted(self._gauges.items()):
            name = key.split("{")[0]
            if name not in seen_help:
                lines.append(f"# TYPE {name} gauge")
                seen_help.add(name)
            lines.append(f"{key} {value}")

        for key, values in sorted(self._histograms.items()):
            name = key.split("{")[0]
            if name not in seen_help:
                lines.append(f"# TYPE {name} histogram")
                seen_help.add(name)
            lines.append(f"{key}_count {len(values)}")
            lines.append(f"{key}_sum {sum(values)}")

        return "\n".join(lines) + "\n" if lines else ""

    def export_json(self) -> dict:
        """Export all metrics as a JSON-serializable dict."""
        return {
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
            "histograms": {k: {"count": len(v), "sum": sum(v), "values": v} for k, v in self._histograms.items()},
        }

    def reset(self):
        """Clear all metrics."""
        self._counters.clear()
        self._gauges.clear()
        self._histograms.clear()
        self._labels.clear()
        self._points.clear()


# ── Structured Logger — JSON Event Logs ─────────────────────────


class LogLevel(str, Enum):
    """Log severity levels."""

    DEBUG = "debug"
    INFO = "info"
    WARN = "warn"
    ERROR = "error"


@dataclass
class LogEntry:
    """A structured log entry."""

    level: LogLevel
    message: str
    timestamp: str
    context: dict[str, Any]

    def to_dict(self) -> dict:
        return {
            "level": self.level.value,
            "message": self.message,
            "timestamp": self.timestamp,
            "context": self.context,
        }


class StructuredLogger:
    """
    JSON structured log emitter.

    Every log entry is a JSON object with level, message, timestamp,
    and arbitrary context fields. Logs are queryable and filterable.

    PEH Ch.4: "Structured logs are not printf. They are queryable
    events. Every field is a dimension you can filter on."
    Companion: github.com/achankra/peh, ch04/structured_logging.py
    """

    def __init__(self, service_name: str = "adp-paths"):
        self.service_name = service_name
        self._entries: list[LogEntry] = []

    def log(self, level: LogLevel, message: str, **context: Any):
        """Emit a structured log entry."""
        entry = LogEntry(
            level=level,
            message=message,
            timestamp=datetime.now(timezone.utc).isoformat(),
            context={"service": self.service_name, **context},
        )
        self._entries.append(entry)

    def debug(self, message: str, **context: Any):
        self.log(LogLevel.DEBUG, message, **context)

    def info(self, message: str, **context: Any):
        self.log(LogLevel.INFO, message, **context)

    def warn(self, message: str, **context: Any):
        self.log(LogLevel.WARN, message, **context)

    def error(self, message: str, **context: Any):
        self.log(LogLevel.ERROR, message, **context)

    def get_entries(self, level: LogLevel | None = None) -> list[LogEntry]:
        """Get log entries, optionally filtered by level."""
        if level is None:
            return list(self._entries)
        return [e for e in self._entries if e.level == level]

    def export_json(self) -> list[dict]:
        """Export all entries as JSON-serializable dicts."""
        return [e.to_dict() for e in self._entries]

    def reset(self):
        """Clear all log entries."""
        self._entries.clear()


# ── Observability Stack — Unified Infrastructure ────────────────


class ObservabilityStack:
    """
    Unified observability stack combining tracer, metrics, and logger.

    This is the L01 infrastructure that every layer uses:
    - L01 Tooling: pipeline telemetry (span per stage, pass/fail counters)
    - L03 GOVERNANCE: agent events (identity checks, policy enforcement,
      execution audit trail)

    PEH Ch.4: "The three pillars — metrics, logs, traces — are not
    alternatives. They are complementary views of the same system."
    Companion: github.com/achankra/peh, ch04/observability_stack.py
    """

    def __init__(self, service_name: str = "adp-paths"):
        self.service_name = service_name
        self.tracer = Tracer(service_name)
        self.metrics = Metrics()
        self.logger = StructuredLogger(service_name)

    def export_all(self, output_dir: str | None = None) -> dict:
        """
        Export all observability data.

        If output_dir is provided, writes three JSON files:
        traces.json, metrics.json, logs.json.

        Returns the combined data as a dict.
        """
        data = {
            "service": self.service_name,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "traces": self.tracer.export_json(),
            "metrics": self.metrics.export_json(),
            "logs": self.logger.export_json(),
        }

        if output_dir:
            out = Path(output_dir)
            out.mkdir(parents=True, exist_ok=True)
            (out / "traces.json").write_text(json.dumps(data["traces"], indent=2))
            (out / "metrics.json").write_text(json.dumps(data["metrics"], indent=2))
            (out / "logs.json").write_text(json.dumps(data["logs"], indent=2))
            (out / "prometheus.txt").write_text(self.metrics.export_prometheus())

        return data

    def reset(self):
        """Clear all observability data."""
        self.tracer.reset()
        self.metrics.reset()
        self.logger.reset()
