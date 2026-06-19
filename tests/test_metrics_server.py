"""Tests for the Prometheus metrics server."""

import time
import urllib.request

import pytest

from src.metrics_server import MetricsServer
from src.observability import ObservabilityStack


class TestMetricsServer:
    def test_start_and_stop(self):
        obs = ObservabilityStack(service_name="test")
        server = MetricsServer(obs, port=19090)
        server.start()
        assert server._thread is not None
        assert server._thread.is_alive()
        server.stop()
        assert server._thread is None

    def test_serves_metrics_endpoint(self):
        obs = ObservabilityStack(service_name="test")
        obs.metrics.counter("test_requests", labels={"path": "/api"})
        obs.metrics.counter("test_requests", labels={"path": "/api"})
        obs.metrics.gauge("test_active", 42)

        server = MetricsServer(obs, port=19091)
        server.start()
        try:
            time.sleep(0.1)
            resp = urllib.request.urlopen("http://localhost:19091/metrics")
            body = resp.read().decode()
            assert "test_requests" in body
            assert "test_active" in body
            assert resp.status == 200
        finally:
            server.stop()

    def test_returns_404_for_other_paths(self):
        obs = ObservabilityStack(service_name="test")
        server = MetricsServer(obs, port=19092)
        server.start()
        try:
            time.sleep(0.1)
            with pytest.raises(urllib.error.HTTPError) as exc_info:
                urllib.request.urlopen("http://localhost:19092/other")
            assert exc_info.value.code == 404
        finally:
            server.stop()

    def test_url_property(self):
        obs = ObservabilityStack(service_name="test")
        server = MetricsServer(obs, port=19093)
        assert server.url == "http://localhost:19093/metrics"

    def test_metrics_update_live(self):
        """Verify that metrics added after server start are visible."""
        obs = ObservabilityStack(service_name="test")
        server = MetricsServer(obs, port=19094)
        server.start()
        try:
            time.sleep(0.1)
            # Initially empty
            resp = urllib.request.urlopen("http://localhost:19094/metrics")
            body1 = resp.read().decode()

            # Add metrics after server is running
            obs.metrics.counter("late_metric")
            obs.metrics.gauge("active_connections", 7)

            resp = urllib.request.urlopen("http://localhost:19094/metrics")
            body2 = resp.read().decode()
            assert "late_metric" in body2
            assert "active_connections" in body2
        finally:
            server.stop()
