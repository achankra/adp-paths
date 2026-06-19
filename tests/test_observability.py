"""
Tests for src/observability.py — L01 Observability Infrastructure.

Three pillars: Tracer (spans), Metrics (counters/gauges/histograms),
StructuredLogger (JSON events). Plus the unified ObservabilityStack.

PEH Reference: Chapter 4 (Embedding Observability)
Companion code: github.com/achankra/peh, ch04/test_observability.py
"""

import json
import tempfile
from pathlib import Path

import pytest  # noqa: F401

from src.observability import (
    LogLevel,
    Metrics,
    ObservabilityStack,
    Span,
    SpanStatus,
    StructuredLogger,
    Tracer,
)

# ── Span ────────────────────────────────────────────────────────


class TestSpan:
    """PEH Ch.4: 'A trace is a tree of spans.'"""

    def test_span_defaults(self):
        span = Span(name="test-span")
        assert span.name == "test-span"
        assert span.status == SpanStatus.UNSET
        assert span.end_time is None
        assert span.duration_ms is None
        assert len(span.trace_id) == 32
        assert len(span.span_id) == 16

    def test_span_end(self):
        span = Span(name="test")
        span.end(SpanStatus.OK)
        assert span.status == SpanStatus.OK
        assert span.end_time is not None
        assert span.duration_ms is not None
        assert span.duration_ms >= 0

    def test_span_add_event(self):
        span = Span(name="test")
        span.add_event("checkpoint", {"key": "value"})
        assert len(span.events) == 1
        assert span.events[0]["name"] == "checkpoint"
        assert span.events[0]["attributes"]["key"] == "value"

    def test_span_set_attribute(self):
        span = Span(name="test")
        span.set_attribute("pipeline.name", "ci-build")
        assert span.attributes["pipeline.name"] == "ci-build"

    def test_span_to_dict(self):
        span = Span(name="test")
        span.end(SpanStatus.OK)
        d = span.to_dict()
        assert d["name"] == "test"
        assert d["status"]["code"] == "ok"
        assert d["traceId"] == span.trace_id
        assert d["spanId"] == span.span_id
        assert d["startTimeUnixNano"] > 0
        assert d["endTimeUnixNano"] is not None


# ── Tracer ──────────────────────────────────────────────────────


class TestTracer:
    """PEH Ch.4: 'The tracer is the entry point.'"""

    def test_start_and_end_span(self):
        tracer = Tracer(service_name="test-svc")
        span = tracer.start_span("op-1")
        tracer.end_span(span, SpanStatus.OK)
        assert len(tracer.get_spans()) == 1
        assert tracer.get_spans()[0].status == SpanStatus.OK

    def test_parent_child_spans(self):
        tracer = Tracer()
        parent = tracer.start_span("parent")
        child = tracer.start_span("child", parent=parent)
        assert child.trace_id == parent.trace_id
        assert child.parent_span_id == parent.span_id

    def test_get_traces_groups_by_trace_id(self):
        tracer = Tracer()
        root = tracer.start_span("root")
        tracer.start_span("child-1", parent=root)
        tracer.start_span("child-2", parent=root)
        traces = tracer.get_traces()
        assert len(traces) == 1
        assert len(traces[root.trace_id]) == 3

    def test_export_json(self):
        tracer = Tracer()
        span = tracer.start_span("test")
        tracer.end_span(span)
        exported = tracer.export_json()
        assert len(exported) == 1
        assert exported[0]["name"] == "test"

    def test_reset(self):
        tracer = Tracer()
        tracer.start_span("test")
        tracer.reset()
        assert len(tracer.get_spans()) == 0


# ── Metrics ─────────────────────────────────────────────────────


class TestMetrics:
    """PEH Ch.4: 'Metrics answer how much and how fast.'"""

    def test_counter_increments(self):
        m = Metrics()
        m.counter("requests")
        m.counter("requests")
        m.counter("requests", value=3)
        assert m.get_counter("requests") == 5

    def test_counter_with_labels(self):
        m = Metrics()
        m.counter("requests", labels={"method": "GET"})
        m.counter("requests", labels={"method": "POST"})
        assert m.get_counter("requests", labels={"method": "GET"}) == 1
        assert m.get_counter("requests", labels={"method": "POST"}) == 1

    def test_gauge_sets_value(self):
        m = Metrics()
        m.gauge("queue_size", 10)
        m.gauge("queue_size", 5)
        assert m.get_gauge("queue_size") == 5

    def test_histogram_records_values(self):
        m = Metrics()
        m.histogram("latency_ms", 10.5)
        m.histogram("latency_ms", 20.3)
        m.histogram("latency_ms", 15.1)
        values = m.get_histogram("latency_ms")
        assert len(values) == 3
        assert sum(values) == pytest.approx(45.9)

    def test_export_prometheus(self):
        m = Metrics()
        m.counter("http_requests", labels={"status": "200"})
        m.gauge("cpu_usage", 0.75)
        output = m.export_prometheus()
        assert "# TYPE http_requests counter" in output
        assert "# TYPE cpu_usage gauge" in output

    def test_export_json(self):
        m = Metrics()
        m.counter("requests")
        m.gauge("queue", 3)
        m.histogram("latency", 10.0)
        data = m.export_json()
        assert "counters" in data
        assert "gauges" in data
        assert "histograms" in data

    def test_reset(self):
        m = Metrics()
        m.counter("x")
        m.gauge("y", 1)
        m.histogram("z", 1.0)
        m.reset()
        assert m.get_counter("x") == 0
        assert m.get_gauge("y") == 0
        assert m.get_histogram("z") == []


# ── StructuredLogger ────────────────────────────────────────────


class TestStructuredLogger:
    """PEH Ch.4: 'Structured logs are queryable events.'"""

    def test_log_levels(self):
        logger = StructuredLogger()
        logger.debug("d")
        logger.info("i")
        logger.warn("w")
        logger.error("e")
        assert len(logger.get_entries()) == 4

    def test_filter_by_level(self):
        logger = StructuredLogger()
        logger.info("ok")
        logger.error("bad")
        logger.info("ok2")
        errors = logger.get_entries(LogLevel.ERROR)
        assert len(errors) == 1
        assert errors[0].message == "bad"

    def test_context_fields(self):
        logger = StructuredLogger(service_name="test-svc")
        logger.info("hello", user="alice", count=42)
        entry = logger.get_entries()[0]
        assert entry.context["service"] == "test-svc"
        assert entry.context["user"] == "alice"
        assert entry.context["count"] == 42

    def test_export_json(self):
        logger = StructuredLogger()
        logger.info("test message")
        exported = logger.export_json()
        assert len(exported) == 1
        assert exported[0]["level"] == "info"
        assert exported[0]["message"] == "test message"

    def test_reset(self):
        logger = StructuredLogger()
        logger.info("test")
        logger.reset()
        assert len(logger.get_entries()) == 0


# ── ObservabilityStack ──────────────────────────────────────────


class TestObservabilityStack:
    """PEH Ch.4: 'The three pillars are complementary views.'"""

    def test_stack_has_all_components(self):
        obs = ObservabilityStack(service_name="test")
        assert obs.tracer is not None
        assert obs.metrics is not None
        assert obs.logger is not None
        assert obs.service_name == "test"

    def test_export_all_without_dir(self):
        obs = ObservabilityStack()
        obs.tracer.start_span("test")
        obs.metrics.counter("x")
        obs.logger.info("hello")
        data = obs.export_all()
        assert "traces" in data
        assert "metrics" in data
        assert "logs" in data
        assert len(data["traces"]) == 1

    def test_export_all_with_dir(self):
        obs = ObservabilityStack()
        obs.tracer.start_span("test")
        obs.metrics.counter("x")
        obs.logger.info("hello")
        with tempfile.TemporaryDirectory() as tmpdir:
            obs.export_all(tmpdir)
            assert (Path(tmpdir) / "traces.json").exists()
            assert (Path(tmpdir) / "metrics.json").exists()
            assert (Path(tmpdir) / "logs.json").exists()
            assert (Path(tmpdir) / "prometheus.txt").exists()
            # Verify JSON is valid
            traces = json.loads((Path(tmpdir) / "traces.json").read_text())
            assert isinstance(traces, list)

    def test_reset(self):
        obs = ObservabilityStack()
        obs.tracer.start_span("s")
        obs.metrics.counter("c")
        obs.logger.info("l")
        obs.reset()
        assert len(obs.tracer.get_spans()) == 0
        assert obs.metrics.get_counter("c") == 0
        assert len(obs.logger.get_entries()) == 0
