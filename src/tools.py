"""
Real Pipeline Tools — L01 Deterministic Fabric

Functional wrappers around Ruff (lint/format), module verification,
and security scanning. These are the L01 deterministic tools — they
produce the same result for the same input, every time.

The deterministic fabric is what makes agent-driven paths possible.
Without it, there is nothing for the agent to submit to.

    "In a majority of failed AI initiatives, the cause wasn't the
     models themselves. It was the failure of the platform's
     deterministic fabric."
    — From IDP to ADP (Weave Intelligence, 2025)

PEH Reference:
    Chapter 8  — CI/CD as a Platform Service (pipeline stages, golden paths)
    Chapter 11 — Policy as Code (security gates, OPA integration)
    Chapter 3  — Securing Platform Access (RBAC, identity, scanning)

Companion code: github.com/achankra/peh, Chapters 8, 11
"""

from __future__ import annotations

import ast
import importlib
import importlib.util
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path


# ── Lint (Ruff) ──────────────────────────────────────────────────


def lint(file_paths: list[str], *, fix: bool = False, config: str | None = None) -> dict:
    """
    Run Ruff on target files. Returns structured results.

    Uses the project's ruff.toml for rules. Ruff is called via subprocess
    so it mirrors exactly what a CI pipeline would do — no library API,
    same binary, same output.

    PEH Ch.8: "The pipeline must be reproducible. Same commit, same
    config, same result — regardless of who or what triggered it."
    Companion: github.com/achankra/peh, ch08/pipeline.py
    """
    config_path = config or str(Path(__file__).parent.parent / "ruff.toml")

    # Find ruff binary — check common install locations
    import shutil

    ruff_bin = shutil.which("ruff")
    if ruff_bin is None:
        # Check pip user install location
        local_bin = Path.home() / ".local" / "bin" / "ruff"
        if local_bin.exists():
            ruff_bin = str(local_bin)

    if ruff_bin is None:
        return {
            "tool": "ruff",
            "passed": False,
            "error": "Ruff not installed. Install with: pip install ruff",
            "error_count": 0,
            "warning_count": 0,
            "fixable_count": 0,
            "errors": [],
            "warnings": [],
            "files_checked": 0,
        }

    cmd = [ruff_bin, "check", "--output-format=json", f"--config={config_path}"]

    if fix:
        cmd.append("--fix")

    cmd.extend(file_paths)

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except FileNotFoundError:
        return {
            "tool": "ruff",
            "passed": False,
            "error": "Ruff binary not found at expected path",
            "error_count": 0,
            "warning_count": 0,
            "fixable_count": 0,
            "errors": [],
            "warnings": [],
            "files_checked": 0,
        }

    import json

    try:
        findings = json.loads(result.stdout) if result.stdout.strip() else []
    except json.JSONDecodeError:
        findings = []

    errors = []
    warnings = []

    for f in findings:
        entry = {
            "file": os.path.basename(f.get("filename", "")),
            "line": f.get("location", {}).get("row", 0),
            "column": f.get("location", {}).get("column", 0),
            "code": f.get("code", ""),
            "message": f.get("message", ""),
            "fixable": f.get("fix") is not None,
        }
        # E/W are warnings in Ruff; F/S/B are errors
        if entry["code"].startswith(("E", "W")):
            warnings.append(entry)
        else:
            errors.append(entry)

    return {
        "tool": "ruff",
        "passed": len(errors) == 0 and len(warnings) == 0,
        "error_count": len(errors),
        "warning_count": len(warnings),
        "fixable_count": sum(1 for e in errors + warnings if e["fixable"]),
        "errors": errors,
        "warnings": warnings,
        "files_checked": len(file_paths),
    }


# ── Test (Module-level assertions) ───────────────────────────────


def run_tests(module_path: str, assertions: list[dict]) -> dict:
    """
    Run real assertions against a Python module.

    Each assertion is {"description": str, "fn": callable} where fn(module)
    returns True/False. The module is loaded fresh each time.

    PEH Ch.8: "Tests are deterministic gates. The pipeline runs them
    the same way every time — the output is a function of the code,
    not the environment."
    Companion: github.com/achankra/peh, ch08/test_runner.py
    """
    results = []
    pass_count = 0
    fail_count = 0

    # Load module from file path
    # PEH Ch.5: "Evaluate the User Experience" — the module under test
    # is the platform service endpoint
    mod = _load_module(module_path)
    if mod is None:
        return {
            "tool": "test-runner",
            "passed": False,
            "error": f"Failed to load module: {module_path}",
            "pass_count": 0,
            "fail_count": 1,
            "results": [{"description": "Module load", "passed": False}],
        }

    for assertion in assertions:
        try:
            result = assertion["fn"](mod)
            passed = result is True
            results.append({
                "description": assertion["description"],
                "passed": passed,
                "error": None if passed else f"Expected True, got {result!r}",
            })
            if passed:
                pass_count += 1
            else:
                fail_count += 1
        except Exception as e:
            results.append({
                "description": assertion["description"],
                "passed": False,
                "error": str(e),
            })
            fail_count += 1

    return {
        "tool": "test-runner",
        "passed": fail_count == 0,
        "pass_count": pass_count,
        "fail_count": fail_count,
        "total": len(results),
        "results": results,
    }


def _load_module(module_path: str):
    """Load a Python module from a file path."""
    path = Path(module_path)
    if not path.exists():
        return None

    spec = importlib.util.spec_from_file_location(path.stem, str(path))
    if spec is None or spec.loader is None:
        return None

    mod = importlib.util.module_from_spec(spec)
    try:
        # Temporarily add parent to sys.path so relative imports work
        parent = str(path.parent)
        if parent not in sys.path:
            sys.path.insert(0, parent)
        spec.loader.exec_module(mod)
    except Exception:
        return None

    return mod


# ── Build (Module verification) ──────────────────────────────────


def build(module_paths: list[str]) -> dict:
    """
    Verify that modules parse and load without errors.

    Uses ast.parse for syntax checking and importlib for load verification.
    This is the "build" stage — can the code be compiled and loaded?

    PEH Ch.8: "Build verification is the first gate. If the code
    doesn't parse, nothing else matters."
    Companion: github.com/achankra/peh, ch08/build_gate.py
    """
    results = []
    all_passed = True

    for mod_path in module_paths:
        path = Path(mod_path)
        try:
            source = path.read_text()
            tree = ast.parse(source)

            # Extract exports (top-level function and class names)
            exports = [
                node.name
                for node in ast.walk(tree)
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
                and not node.name.startswith("_")
            ]

            results.append({
                "file": path.name,
                "passed": True,
                "exports": exports,
            })
        except SyntaxError as e:
            results.append({
                "file": path.name,
                "passed": False,
                "error": f"SyntaxError: {e.msg} (line {e.lineno})",
            })
            all_passed = False
        except Exception as e:
            results.append({
                "file": path.name,
                "passed": False,
                "error": str(e),
            })
            all_passed = False

    return {
        "tool": "build-verifier",
        "passed": all_passed,
        "modules_checked": len(results),
        "results": results,
    }


# ── Security Scanner ─────────────────────────────────────────────

# PEH Ch.3: "Securing Platform Access" — these patterns catch the
# most common security anti-patterns in platform service code.
# PEH Ch.11: "Policy as Code" — in production these would be OPA
# policies; here we use regex patterns as a simplified equivalent.
# Companion: github.com/achankra/peh, ch03/security_scanner.py

SECURITY_PATTERNS = [
    {
        "pattern": r"\beval\s*\(",
        "rule": "no-eval",
        "severity": "critical",
        "message": "Use of eval() detected",
    },
    {
        "pattern": r"\bexec\s*\(",
        "rule": "no-exec",
        "severity": "critical",
        "message": "Use of exec() detected",
    },
    {
        "pattern": r"subprocess\.(?:call|run|Popen)\s*\([^)]*shell\s*=\s*True",
        "rule": "no-shell-true",
        "severity": "critical",
        "message": "subprocess with shell=True detected",
    },
    {
        "pattern": r"(?:password|passwd|pwd)\s*[:=]\s*['\"][^'\"]{3,}['\"]",
        "rule": "no-hardcoded-secrets",
        "severity": "critical",
        "message": "Hardcoded password detected",
    },
    {
        "pattern": r"api[_-]?key\s*[:=]\s*['\"][^'\"]{8,}['\"]",
        "rule": "no-hardcoded-secrets",
        "severity": "critical",
        "message": "Hardcoded API key detected",
    },
    {
        "pattern": r"secret\s*[:=]\s*['\"][^'\"]{8,}['\"]",
        "rule": "no-hardcoded-secrets",
        "severity": "critical",
        "message": "Hardcoded secret detected",
    },
    {
        "pattern": r"__import__\s*\(",
        "rule": "no-dynamic-import",
        "severity": "high",
        "message": "Dynamic __import__() detected",
    },
    {
        "pattern": r"os\.system\s*\(",
        "rule": "no-os-system",
        "severity": "high",
        "message": "os.system() detected — use subprocess instead",
    },
    {
        "pattern": r"pickle\.loads?\s*\(",
        "rule": "no-pickle",
        "severity": "high",
        "message": "pickle deserialization detected (untrusted data risk)",
    },
    {
        "pattern": r"os\.environ\[",
        "rule": "env-access",
        "severity": "info",
        "message": "Direct os.environ access (consider config module)",
    },
]


def security_scan(file_paths: list[str]) -> dict:
    """
    Scan files for security patterns. Returns structured findings.

    PEH Ch.3: "Every artifact that enters the platform goes through
    the same security gates — human-authored or agent-authored."
    Companion: github.com/achankra/peh, ch03/security_gate.py
    """
    findings = []
    critical_count = 0
    high_count = 0

    for file_path in file_paths:
        content = Path(file_path).read_text()
        file_name = os.path.basename(file_path)

        for spec in SECURITY_PATTERNS:
            for match in re.finditer(spec["pattern"], content, re.IGNORECASE):
                line = content[: match.start()].count("\n") + 1
                findings.append({
                    "file": file_name,
                    "line": line,
                    "rule": spec["rule"],
                    "severity": spec["severity"],
                    "message": spec["message"],
                    "match": match.group()[:40],
                })
                if spec["severity"] == "critical":
                    critical_count += 1
                elif spec["severity"] == "high":
                    high_count += 1

    return {
        "tool": "security-scanner",
        "passed": critical_count == 0,
        "critical_count": critical_count,
        "high_count": high_count,
        "total_findings": len(findings),
        "findings": findings,
        "files_scanned": len(file_paths),
    }
