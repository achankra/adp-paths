"""
/ci-build — Deterministic Path

The CI/CD pipeline is deterministic at every maturity level.
Same commit + same pipeline definition = same result.

At L0-L1: Developer pushes code, pipeline runs lint/test/build/security.
At L2:    Agents may produce the code, but the pipeline is unchanged.
          It stays on L01. No L02 path definitions. No L03 agent infra.

This implementation uses REAL tools:
    - Ruff for linting (subprocess, same as CI would run it)
    - ast.parse + importlib for build verification
    - Pattern-based security scanning

PEH Reference:
    Chapter 8  — CI/CD as a Platform Service (pipeline design)
    Chapter 11 — Policy as Code (security gates)

Companion code: github.com/achankra/peh, ch08/ci_build.py
"""

from __future__ import annotations

from pathlib import Path

from src.layers import L01Tooling, PathType
from src import tools

SAMPLE_DIR = Path(__file__).parent.parent.parent / "sample" / "src"


def _default_target_files(input_data: dict) -> list[str]:
    """Resolve target files — use provided paths or fall back to sample code."""
    if "file_paths" in input_data:
        return input_data["file_paths"]
    return [
        str(SAMPLE_DIR / "handler.py"),
        str(SAMPLE_DIR / "utils.py"),
    ]


def create_default_stages(input_data: dict) -> list[dict]:
    """
    Create pipeline stages that use real tools.

    Each stage calls the actual Ruff linter, ast.parse, or
    security scanner — not a simulation.

    """
    target_files = _default_target_files(input_data)

    return [
        {
            "name": "lint",
            "tool": "ruff",
            "run": _make_lint_stage(target_files),
        },
        {
            "name": "test",
            "tool": "module-assertions",
            "run": _make_test_stage(target_files),
        },
        {
            "name": "build",
            "tool": "ast-verifier",
            "run": _make_build_stage(target_files),
        },
        {
            "name": "security",
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


def _make_test_stage(target_files):
    async def run(_input):
        # Find handler module in target files
        handler_path = next(
            (f for f in target_files if "handler" in f), target_files[0]
        )
        result = tools.run_tests(handler_path, [
            {
                "description": "handle_request returns 400 for None body",
                "fn": lambda mod: mod.handle_request(None)["status"] == 400,
            },
            {
                "description": "handle_request returns 400 for missing action",
                "fn": lambda mod: mod.handle_request({})["status"] == 400,
            },
            {
                "description": "handle_request returns 200 for valid input",
                "fn": lambda mod: mod.handle_request({"action": "create"})["status"] == 200,
            },
            {
                "description": "process_request sets processed flag",
                "fn": lambda mod: mod.process_request({"action": "deploy"})["processed"] is True,
            },
            {
                "description": "generate_id produces unique IDs",
                "fn": lambda mod: mod.generate_id() != mod.generate_id(),
            },
        ])
        return {
            "passed": result["passed"],
            "output": (
                f"PASS: {result['pass_count']} of {result['total']} assertions passed"
                if result["passed"]
                else (
                    f"FAIL: {result['fail_count']} of {result['total']} failed — "
                    + "; ".join(r["description"] for r in result["results"] if not r["passed"])
                )
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
                f"Verified {result['modules_checked']} module(s): "
                + "; ".join(
                    f"{r['file']} [{', '.join(r['exports'])}]"
                    for r in result["results"]
                    if r["passed"]
                )
                if result["passed"]
                else "Build failed: " + "; ".join(
                    f"{r['file']}: {r['error']}"
                    for r in result["results"]
                    if not r["passed"]
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
                f"No critical findings ({result['files_scanned']} file(s) scanned, "
                f"{result['total_findings']} info/low finding(s))"
                if result["passed"]
                else (
                    f"CRITICAL: {result['critical_count']} critical finding(s) — "
                    + "; ".join(
                        f"{f['file']}:{f['line']} {f['message']}"
                        for f in result["findings"]
                        if f["severity"] == "critical"
                    )
                )
            ),
            "detail": result,
        }
    return run


async def run_at_l01(input_data: dict, options: dict | None = None) -> dict:
    """
    Run /ci-build at L0-L1 (human-driven).

    The developer pushes code, the pipeline runs real tools.
    If it fails, the developer reads output and fixes manually.

    """
    options = options or {}
    obs = options.get("obs_stack")
    tooling = L01Tooling(obs_stack=obs)
    stages = create_default_stages(input_data)
    tooling.register_pipeline("ci-build", stages)

    pipeline_result = await tooling.run_pipeline("ci-build", input_data)

    return {
        "path": "/ci-build",
        "maturity_level": "L0-L1",
        "type": PathType.DETERMINISTIC,
        "layers": ["L01"],
        "triggered_by": "human",
        "pipeline": pipeline_result,
        "harness": None,
        "governance": None,
        "summary": {
            "l01": "Pipeline executed (lint → test → build → security)",
            "l02": "None — deterministic path has no path definition layer",
            "l03": "None — deterministic path has no agent infrastructure",
        },
    }


async def run_at_l02(input_data: dict, options: dict | None = None) -> dict:
    """
    Run /ci-build at L2 (agent era).

    The pipeline is identical. Agents may have authored the code,
    but the pipeline does not know or care.

    """
    options = options or {}
    obs = options.get("obs_stack")
    tooling = L01Tooling(obs_stack=obs)
    stages = create_default_stages(input_data)
    tooling.register_pipeline("ci-build", stages)

    pipeline_result = await tooling.run_pipeline("ci-build", input_data)

    return {
        "path": "/ci-build",
        "maturity_level": "L2",
        "type": PathType.DETERMINISTIC,
        "layers": ["L01"],
        "triggered_by": input_data.get("triggered_by", "agent"),
        "pipeline": pipeline_result,
        "harness": None,
        "governance": None,
        "summary": {
            "l01": "Pipeline executed (identical to L0-L1)",
            "l02": "None — deterministic paths stay on L01 at every maturity level",
            "l03": "None — no agent infrastructure needed for deterministic paths",
        },
    }
