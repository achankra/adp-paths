"""
/validate-change — Hybrid Path (at L2)

At L0-L1: Single human-walked gate. Developer reads CI output,
          fixes manually, pushes again. No feedback loop.
At L2:    Agent + deterministic gate running in a loop.
          The agent interprets failures, generates fixes, resubmits.
          Loop continues until the gate passes or retry limit is reached.

This implementation uses REAL tools:
    - Ruff for lint checking (the deterministic gate)
    - Ruff --fix for agent-generated fixes (simulate mode)
    - Claude API for fix generation (live mode)

The deterministic gate (L01 pipeline) never changes.
The agent gets structured failure signals, not raw log output.
There is always a retry limit and human escalation.

PEH Reference:
    Chapter 4  — Embedding Observability (telemetry, structured signals)
    Chapter 11 — Policy as Code (automated policy gates)
    Chapter 13 — Resilience Automation (feedback loops, retry patterns)

Companion code: github.com/achankra/peh, ch04/observability.py,
                ch11/policy_gate.py, ch13/feedback_loop.py
"""

from __future__ import annotations

import os
import shutil
import tempfile
import time
from pathlib import Path

from src.layers import L01Tooling, PathType
from src.harness import Harness
from src.governance import Governance
from src import tools

SAMPLE_DIR = Path(__file__).parent.parent.parent / "sample" / "src"


def create_validation_stages(target_files: list[str]) -> list[dict]:
    """
    Create validation pipeline stages using real Ruff.

    The gate is always deterministic: same file, same rules, same result.

    """
    return [
        {
            "name": "lint-check",
            "tool": "ruff",
            "run": _make_lint_stage(target_files),
        },
        {
            "name": "build-check",
            "tool": "ast-verifier",
            "run": _make_build_stage(target_files),
        },
        {
            "name": "security-scan",
            "tool": "pattern-scanner",
            "run": _make_security_stage(target_files),
        },
    ]


def _make_lint_stage(target_files):
    async def run(_input):
        result = tools.lint(target_files)
        return {
            "passed": result["passed"],
            "output": (
                f"No lint errors ({result['files_checked']} file(s) checked)"
                if result["passed"]
                else f"{result['error_count']} error(s), {result['warning_count']} warning(s)"
            ),
            "detail": result,
        }
    return run


def _make_build_stage(target_files):
    async def run(_input):
        result = tools.build(target_files)
        return {
            "passed": result["passed"],
            "output": (
                f"{result['modules_checked']} module(s) verified"
                if result["passed"]
                else "Build failed: " + "; ".join(
                    r["error"] for r in result["results"] if not r["passed"]
                )
            ),
            "detail": result,
        }
    return run


def _make_security_stage(target_files):
    async def run(_input):
        result = tools.security_scan(target_files)
        return {
            "passed": result["passed"],
            "output": (
                f"No critical findings ({result['files_scanned']} file(s) scanned)"
                if result["passed"]
                else f"{result['critical_count']} critical finding(s)"
            ),
            "detail": result,
        }
    return run


async def run_at_l01(change: dict) -> dict:
    """
    Run /validate-change at L0-L1 (human-driven, single gate).

    Developer pushes code. CI runs real Ruff. Developer reads output.
    If it fails, they fix manually and push again.

    """
    target_files = change.get("file_paths") or [
        str(SAMPLE_DIR / "handler.py"),
        str(SAMPLE_DIR / "utils.py"),
    ]

    tooling = L01Tooling()
    stages = create_validation_stages(target_files)
    tooling.register_pipeline("validate-change", stages)

    pipeline_result = await tooling.run_pipeline("validate-change", change)

    return {
        "path": "/validate-change",
        "maturity_level": "L0-L1",
        "type": "gate",
        "layers": ["L01"],
        "triggered_by": "human",
        "pipeline": pipeline_result,
        "attempts": 1,
        "loop": None,
        "harness": None,
        "governance": None,
        "summary": {
            "l01": "Validation gate executed (lint → build → security)",
            "l02": "None — single gate, no feedback loop",
            "l03": "None — no agent infrastructure",
        },
    }


async def run_at_l02(change: dict, options: dict | None = None) -> dict:
    """
    Run /validate-change at L2 (hybrid — agent + gate feedback loop).

    The agent interprets failure signals, generates fixes, and resubmits
    to the deterministic pipeline. The loop continues until the gate
    passes or the retry limit is hit. On exhaustion, escalation to human.

    In simulate mode: Ruff --fix generates the fixes (deterministic auto-fix).
    In live mode: Claude API generates fixes from failure signals.

    """
    options = options or {}
    max_retries = options.get("max_retries", 3)
    simulate = options.get("simulate", True)
    model = options.get("model")

    obs = options.get("obs_stack")
    harness = Harness(simulate=simulate, model=model)
    governance = Governance(obs_stack=obs)

    # Copy target files to a temp directory so we can modify them in the loop
    source_files = change.get("file_paths") or [
        str(SAMPLE_DIR / "handler.py"),
        str(SAMPLE_DIR / "utils.py"),
    ]
    temp_dir = tempfile.mkdtemp(prefix="adp-validate-")
    target_files = []
    for f in source_files:
        dest = os.path.join(temp_dir, os.path.basename(f))
        shutil.copy2(f, dest)
        target_files.append(dest)

    # Register agent identity
    agent_id = options.get("agent_id", "validate-agent-001")
    governance.identity.register(agent_id, {
        "team": change.get("team", "platform"),
        "permissions": ["read", "fix", "resubmit"],
    })

    governance.security.add_policy({
        "name": "retry-limit-policy",
        "check": _retry_limit_policy,
    })

    loop_trace = []
    attempt = 0
    final_result = None

    while attempt < max_retries:
        # L01: Run the deterministic gate (real Ruff)
        tooling = L01Tooling(obs_stack=obs)
        stages = create_validation_stages(target_files)
        tooling.register_pipeline("validate-change", stages)
        pipeline_result = await tooling.run_pipeline("validate-change", {})

        loop_entry = {
            "attempt": attempt + 1,
            "pipeline": pipeline_result,
            "fix": None,
        }

        if pipeline_result["passed"]:
            loop_entry["outcome"] = "passed"
            loop_trace.append(loop_entry)
            final_result = {
                "status": "passed",
                "attempts": attempt + 1,
                "resolved_by": "first-pass" if attempt == 0 else "agent-fix",
            }
            break

        # Collect structured failure signals from the pipeline
        failed_stages = [
            {
                "name": s["name"],
                "output": s["output"],
                "detail": s.get("detail"),
            }
            for s in pipeline_result["stages"]
            if not s["passed"]
        ]

        lint_errors = []
        for s in failed_stages:
            if s["name"] == "lint-check" and s.get("detail"):
                lint_errors.extend(s["detail"].get("errors", []))
                lint_errors.extend(s["detail"].get("warnings", []))

        # L03: Agent interprets failure and generates fix
        governed = await governance.wrap(
            agent_id,
            {"path": "/validate-change", "action": "generate-fix"},
            lambda: _generate_fix(
                harness, target_files, lint_errors, failed_stages, simulate
            ),
        )

        exec_output = (
            governed.get("result", {})
            .get("components", {})
            .get("execution", {})
            .get("output", {})
            if governed.get("result", {}).get("components")
            else governed.get("result", {}).get("output", {})
        )

        loop_entry["fix"] = {
            "generated": exec_output.get("patch_generated", False),
            "targets": exec_output.get("targets", []),
            "fix_type": exec_output.get("fix_type", "unknown"),
        }
        loop_entry["outcome"] = "fix-applied-retrying"
        loop_trace.append(loop_entry)

        # If live mode returned code, write it to the temp file
        if exec_output.get("code") and not simulate:
            Path(target_files[0]).write_text(exec_output["code"])

        attempt += 1

    if final_result is None:
        final_result = {
            "status": "escalated",
            "attempts": attempt,
            "resolved_by": "human-escalation",
        }
        governance.observability.record({
            "agent_id": agent_id,
            "action": "escalated",
            "path": "/validate-change",
            "reason": f"Retry limit exhausted after {attempt} attempts",
        })

    # Clean up temp files
    shutil.rmtree(temp_dir, ignore_errors=True)

    return {
        "path": "/validate-change",
        "maturity_level": "L2",
        "type": PathType.HYBRID,
        "layers": ["L01", "L02", "L03"],
        "triggered_by": "dispatch-work",
        "mode": "simulate" if simulate else "live",
        "result": final_result,
        "attempts": final_result["attempts"],
        "loop": loop_trace,
        "harness": "activated",
        "governance": {
            "observability": governance.observability.get_metrics(),
            "audit_trail": governance.observability.get_audit_trail(),
        },
        "summary": {
            "l01": "Deterministic gate executed on each attempt (real Ruff, real security scan)",
            "l02": "Path defined as hybrid — agent + gate feedback loop",
            "l03": (
                f"HARNESS generated {sum(1 for l in loop_trace if l.get('fix'))} fix(es). "
                f"GOVERNANCE tracked {final_result['attempts']} attempt(s). "
                f"Final status: {final_result['status']}."
            ),
        },
    }


async def _generate_fix(harness, target_files, lint_errors, failed_stages, simulate):
    """Generate a fix using either Ruff --fix (simulate) or Claude (live)."""
    if simulate:
        # Use Ruff --fix directly — deterministic auto-fix
        fix_result = tools.lint(target_files, fix=True)
        return {
            "harness": True,
            "mode": "simulate",
            "action": "fix-applied",
            "components": {
                "execution": {
                    "output": {
                        "fix_type": "ruff-autofix",
                        "targets": [e.get("code", "unknown") for e in lint_errors],
                        "patch_generated": fix_result.get("fixable_count", 0) > 0,
                        "fixable_count": fix_result.get("fixable_count", 0),
                    },
                    "mode": "simulate",
                },
            },
        }

    # Live mode: use Claude to generate fixes
    return await harness.run(
        {
            "file_paths": target_files,
            "failures": lint_errors if lint_errors else failed_stages,
        },
        "generate-fix",
        {"min_confidence": 0.70},
    )


async def _retry_limit_policy(_action: dict) -> dict:
    return {"allowed": True, "reason": "Retry limit enforced by loop control"}
