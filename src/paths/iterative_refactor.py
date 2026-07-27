"""
/iterative-refactor — Hybrid Path (at L2)

Refactor under a test gate. Loops between Agent Infrastructure and Tooling.

At L0-L1: Single human-walked gate. Developer reads CI output,
          fixes manually, pushes again. No feedback loop.
At L2:    Agent + deterministic gate running in a loop.
          The agent interprets failures, generates fixes, resubmits.
          Loop continues until the gate passes or retry limit is reached.

This is a thin wrapper around the validate_change implementation,
exposing it under the path specification name /iterative-refactor.

PEH Reference:
    Chapter 4  — Embedding Observability (telemetry, structured signals)
    Chapter 11 — Policy as Code (automated policy gates)
    Chapter 13 — Resilience Automation (feedback loops, retry patterns)

Companion code: github.com/achankra/peh
"""

from __future__ import annotations

from src.paths import validate_change

# Re-export the validation stages — the gate is identical
create_validation_stages = validate_change.create_validation_stages


async def run_at_l01(change: dict) -> dict:
    """Run /iterative-refactor at L0-L1 (human-driven, single gate)."""
    result = await validate_change.run_at_l01(change)
    result["path"] = "/iterative-refactor"
    return result


async def run_at_l02(change: dict, options: dict | None = None) -> dict:
    """Run /iterative-refactor at L2 (hybrid — agent + gate feedback loop)."""
    options = options or {}
    options.setdefault("agent_id", "refactor-agent-001")
    result = await validate_change.run_at_l02(change, options)
    result["path"] = "/iterative-refactor"
    return result
