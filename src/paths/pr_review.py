"""
/pr-review — Probabilistic Path (at L2)

At L0-L1: Human reads the diff. Hours later, with no context loaded.
          This path is unchanged at L1. Manual review only.
At L2:    Agent-driven with HARNESS orchestration and GOVERNANCE control.
          The agent retrieves context, generates a structured review,
          and the human validates. The agent does not merge.

Two modes:
    --simulate: Local heuristic code analysis using ast (no API calls)
    --live:     Claude API generates the structured review

HARNESS components activated at L2:
    Context    — Loads source files, ADRs, team conventions
    Capability — Selects review model by change type
    Execution  — Generates structured review with evidence
    Evaluation — Human validates. Agent does not merge.

PEH Reference:
    Chapter 3  — Securing Platform Access (RBAC, identity)
    Chapter 14 — Agentic Platforms (HARNESS, agent-driven review)

Companion code: github.com/achankra/peh, ch14/pr_review.py
"""

from __future__ import annotations

import os
import time
from pathlib import Path

from src.layers import PathType
from src.harness import Harness
from src.governance import Governance

SAMPLE_DIR = Path(__file__).parent.parent.parent / "sample" / "src"


async def run_at_l01(pr: dict) -> dict:
    """
    Run /pr-review at L0-L1 (human-driven).

    A human reviewer opens the PR, reads the diff, leaves comments.
    No agent involvement. No HARNESS. No GOVERNANCE.

    """
    start = time.time()

    review = {
        "reviewer": "human",
        "method": "manual-diff-read",
        "files_reviewed": len(pr.get("files", [])),
        "lines_changed": pr.get("lines_changed", 0),
        "time_to_review": "4-24 hours (typical)",
        "context_loaded": False,
        "evidence_trail": False,
        "categories": ["general"],
        "recommendation": "approve" if pr.get("obvious") else "request-changes",
    }

    return {
        "path": "/pr-review",
        "maturity_level": "L0-L1",
        "type": "manual",
        "layers": ["L01"],
        "triggered_by": "human",
        "review": review,
        "harness": None,
        "governance": None,
        "duration_ms": int((time.time() - start) * 1000),
        "summary": {
            "l01": "PR queued in review backlog",
            "l02": "None — path not defined at L0-L1",
            "l03": "None — no agent infrastructure",
        },
    }


async def run_at_l02(pr: dict, options: dict | None = None) -> dict:
    """
    Run /pr-review at L2 (agent-driven, probabilistic).

    The full HARNESS activates. GOVERNANCE wraps every action.
    The agent generates a structured review but does NOT merge.
    The human validates and decides.

    In simulate mode: local heuristic analysis of actual file content
    using Python's ast module.
    In live mode: Claude API generates the review.

    """
    options = options or {}
    start = time.time()
    simulate = options.get("simulate", True)
    model = options.get("model")

    obs = options.get("obs_stack")
    harness = Harness(simulate=simulate, model=model)
    governance = Governance(obs_stack=obs)

    # Register agent identity
    agent_id = options.get("agent_id", "pr-review-agent-001")
    governance.identity.register(agent_id, {
        "team": pr.get("team", "platform"),
        "repositories": [pr.get("repository", "default-repo")],
        "permissions": ["read", "comment"],  # No merge permission
    })

    # Add security policies
    governance.security.add_policy({
        "name": "repo-scope-check",
        "check": _repo_scope_policy,
    })
    governance.security.add_policy({
        "name": "no-merge-policy",
        "check": _no_merge_policy,
    })

    # Resolve real file paths for review
    file_paths = _resolve_file_paths(pr)

    governed_result = await governance.wrap(
        agent_id,
        {"path": "/pr-review", "action": "review"},
        lambda: harness.run(
            {
                "file_paths": file_paths,
                "change_type": pr.get("change_type", "routine"),
            },
            "generate-review",
            {"min_confidence": 0.80, "auto_approve": False},
        ),
    )

    exec_output = (
        governed_result.get("result", {})
        .get("components", {})
        .get("execution", {})
        .get("output", {})
    )
    mode = governed_result.get("result", {}).get("mode", "simulate")

    return {
        "path": "/pr-review",
        "maturity_level": "L2",
        "type": PathType.PROBABILISTIC,
        "layers": ["L01", "L02", "L03"],
        "triggered_by": "dispatch-work",
        "mode": mode,
        "review": {
            "reviewer": "agent",
            "method": "harness-orchestrated",
            "files_reviewed": len(file_paths),
            "lines_changed": pr.get("lines_changed", 0),
            "context_loaded": True,
            "evidence_trail": True,
            "categories": [
                c.get("category", "general") for c in exec_output.get("categories", [])
            ] or ["general"],
            "recommendation": exec_output.get("recommendation", "pending"),
            "findings": exec_output.get("categories", []),
        },
        "harness": governed_result.get("result", {}).get("components"),
        "governance": {
            "identity": governed_result.get("identity"),
            "security": governed_result.get("security"),
            "observability": governance.observability.get_metrics(),
        },
        "duration_ms": int((time.time() - start) * 1000),
        "summary": {
            "l01": "PR registered in pipeline system",
            "l02": "Path defined as probabilistic — agent-driven review",
            "l03": (
                f"HARNESS: Context → Capability → Execution → Evaluation (mode: {mode}). "
                "GOVERNANCE: identity verified, policies enforced, telemetry recorded."
            ),
        },
    }


def _resolve_file_paths(pr: dict) -> list[str]:
    """Resolve file paths from PR input, falling back to sample code."""
    raw = pr.get("file_paths") or pr.get("files") or []
    resolved = []
    for f in raw:
        if os.path.isabs(f) and os.path.exists(f):
            resolved.append(f)
        else:
            candidate = SAMPLE_DIR / os.path.basename(f)
            if candidate.exists():
                resolved.append(str(candidate))
    return resolved or [
        str(SAMPLE_DIR / "handler.py"),
        str(SAMPLE_DIR / "utils.py"),
    ]


async def _repo_scope_policy(_action: dict) -> dict:
    return {"allowed": True, "reason": "Agent scoped to repository RBAC"}


async def _no_merge_policy(action: dict) -> dict:
    if action.get("action") == "merge":
        return {
            "allowed": False,
            "reason": "Agents cannot merge PRs at L2 — human approval required",
        }
    return {"allowed": True, "reason": "Action permitted"}
