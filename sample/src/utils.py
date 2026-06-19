"""
Platform Utility Functions

Input validation, response formatting, and input sanitization.
Used across platform service endpoints.

PEH Reference: Chapter 3 (Securing Platform Access)
Companion code: github.com/achankra/peh, ch03/utils.py
"""

from __future__ import annotations

import re
import time

ALLOWED_ACTIONS = ("create", "read", "update", "delete", "deploy", "validate")


def validate_input(body: dict | None) -> dict:
    """Validate incoming request body."""
    if not body or not isinstance(body, dict):
        return {"valid": False, "error": "Invalid input: expected dict"}
    if "action" not in body:
        return {"valid": False, "error": "Missing required field: action"}
    if body["action"] not in ALLOWED_ACTIONS:
        return {
            "valid": False,
            "error": f"Unknown action: {body['action']}. Allowed: {', '.join(ALLOWED_ACTIONS)}",
        }
    return {"valid": True, "data": body}


def format_response(status: int, body: dict) -> dict:
    """Wrap a response with status and timestamp."""
    return {
        "status": status,
        "body": body,
        "timestamp": time.time(),
    }


def sanitize(data):
    """Strip HTML tags from string values, recursively."""
    if isinstance(data, str):
        return re.sub(r"<[^>]*>", "", data)
    if isinstance(data, dict):
        return {k: sanitize(v) for k, v in data.items()}
    return data
