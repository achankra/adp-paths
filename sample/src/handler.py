"""
Platform API Request Handler

A real, testable module representing a platform service endpoint.
Used by the /ci-build and /validate-change paths as the target
codebase that pipelines operate on.

PEH Reference: Chapter 5 (Evaluate the User Experience)
Companion code: github.com/achankra/peh, ch05/handler.py
"""

from __future__ import annotations

import secrets
import string
import time

try:
    from .utils import format_response, sanitize, validate_input
except ImportError:
    from utils import format_response, sanitize, validate_input


def handle_request(body: dict | None) -> dict:
    """Process an incoming platform API request."""
    result = validate_input(body)
    if not result["valid"]:
        return format_response(400, {"error": result["error"]})

    processed = process_request(sanitize(result["data"]))
    return format_response(200, processed)


def process_request(data: dict) -> dict:
    """Execute the validated request."""
    return {
        "id": generate_id(),
        "processed": True,
        "action": data.get("action"),
        "timestamp": time.time(),
    }


def generate_id() -> str:
    """Generate a unique request identifier."""
    alphabet = string.ascii_lowercase + string.digits
    suffix = "".join(secrets.choice(alphabet) for _ in range(6))
    return f"req-{int(time.time())}-{suffix}"
