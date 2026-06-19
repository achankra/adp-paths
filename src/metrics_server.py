"""
Prometheus Metrics Server

Lightweight HTTP server that exposes an ObservabilityStack's metrics
on /metrics for Prometheus to scrape. Runs in a background thread
so the CLI can serve metrics while executing demos.
"""

from __future__ import annotations

import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.observability import ObservabilityStack


class _MetricsHandler(BaseHTTPRequestHandler):
    """Serves Prometheus text format on GET /metrics."""

    obs_stack: ObservabilityStack | None = None

    def do_GET(self):
        if self.path == "/metrics":
            body = ""
            if self.obs_stack:
                body = self.obs_stack.metrics.export_prometheus()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(body.encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        # Suppress request logging to keep CLI output clean
        pass


class MetricsServer:
    """
    Background HTTP server that exposes /metrics for Prometheus.

    Usage:
        obs = ObservabilityStack()
        server = MetricsServer(obs, port=8080)
        server.start()   # non-blocking, runs in a daemon thread
        # ... run demos, metrics accumulate in obs ...
        server.stop()
    """

    def __init__(self, obs_stack: ObservabilityStack, port: int = 8080):
        self.obs_stack = obs_stack
        self.port = port
        self._httpd: HTTPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self):
        """Start serving /metrics in a background thread."""
        handler = type("Handler", (_MetricsHandler,), {"obs_stack": self.obs_stack})
        self._httpd = HTTPServer(("0.0.0.0", self.port), handler)
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()

    def stop(self):
        """Shut down the server."""
        if self._httpd:
            self._httpd.shutdown()
            self._httpd = None
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None

    @property
    def url(self) -> str:
        return f"http://localhost:{self.port}/metrics"
