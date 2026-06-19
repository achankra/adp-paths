"""
HARNESS — Agent Execution Orchestrator

Two modes:
    --simulate (default): Local heuristic analysis. No API calls.
    --live:               Uses Claude via the anthropic Python SDK.
                          Requires ANTHROPIC_API_KEY env var.

Four components:
    Context    — Reads files, loads failure signals, gathers metadata
    Capability — Selects model/strategy based on change type
    Execution  — Runs analysis (simulated or Claude)
    Evaluation — Assesses result quality, determines next step

    "HARNESS is not a wrapper around a model call. It is the
     orchestration layer that turns a model call into a governed,
     observable, auditable platform action."
    — The Platform Engineer's Handbook, Chapter 14

PEH Reference:
    Chapter 14 — Agentic and AI-Augmented Platforms (HARNESS design,
                 agent orchestration patterns, context retrieval)

Companion code: github.com/achankra/peh, ch14/harness.py

Reference: "The Four Levels of Agentic Software Development" (Weave, 2025)
"""

from __future__ import annotations

import ast
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class HarnessContext:
    """
    Context retrieval component.

    Reads real files, loads failure signals, and gathers metadata
    that the execution component needs to do its job.

    PEH Ch.14: "The quality of agent output is a function of the
    quality of the context you feed it."
    Companion: github.com/achankra/peh, ch14/harness_context.py
    """

    async def retrieve(self, input_data: dict) -> dict:
        context = {
            "component": "context",
            "retrieved": [],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Read real files if paths provided
        if "file_paths" in input_data:
            files = []
            for fp in input_data["file_paths"]:
                try:
                    content = Path(fp).read_text()
                    files.append({
                        "path": os.path.basename(fp),
                        "content": content,
                        "lines": content.count("\n") + 1,
                    })
                except OSError:
                    pass  # skip unreadable files
            context["retrieved"].append({"source": "files", "items": files})

        # Parse real failure data if provided
        if input_data.get("failures"):
            context["retrieved"].append({
                "source": "failure-signals",
                "items": input_data["failures"],
            })

        if input_data.get("change_type"):
            context["retrieved"].append({
                "source": "change-metadata",
                "items": [{"change_type": input_data["change_type"]}],
            })

        return context


class HarnessCapability:
    """
    Model/strategy selection.

    Selects the appropriate model and execution strategy based on
    the change type and available context.

    PEH Ch.14: "Capability selection is routing. The platform
    decides which model handles which kind of change."
    Companion: github.com/achankra/peh, ch14/harness_capability.py
    """

    async def select(self, context: dict, options: dict | None = None) -> dict:
        options = options or {}
        model = (
            options.get("model")
            or os.environ.get("ANTHROPIC_MODEL")
            or "claude-sonnet-4-20250514"
        )

        change_meta = next(
            (r for r in context.get("retrieved", []) if r["source"] == "change-metadata"),
            None,
        )
        change_type = (
            change_meta["items"][0]["change_type"] if change_meta else "routine"
        )

        return {
            "component": "capability",
            "model": model,
            "change_type": change_type,
            "strategy": "deep-scan" if change_type == "security-sensitive" else "standard",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


class HarnessExecution:
    """
    Execution component — runs analysis in simulate or live mode.

    Simulate mode uses local heuristic analysis (AST parsing,
    pattern matching) — no API calls, no cost, works offline.

    Live mode sends code to Claude via the anthropic Python SDK
    for structured review or fix generation.

    PEH Ch.14: "The execution component is where the model does
    its work — but always under HARNESS orchestration and
    GOVERNANCE control."
    Companion: github.com/achankra/peh, ch14/harness_execution.py
    """

    def __init__(self, simulate: bool = True, model: str | None = None):
        self.simulate = simulate
        self.model = model or os.environ.get("ANTHROPIC_MODEL") or "claude-sonnet-4-20250514"
        self._client = None

    def _ensure_client(self):
        if self._client is not None:
            return
        try:
            import anthropic

            self._client = anthropic.Anthropic()
        except ImportError as e:
            raise RuntimeError(
                "anthropic SDK not available. Install with: pip install anthropic\n"
                "Or use --simulate mode."
            ) from e

    async def run(self, context: dict, capability: dict, action: str) -> dict:
        if self.simulate:
            return self._run_simulated(context, capability, action)
        return self._run_with_claude(context, capability, action)

    def _run_with_claude(self, context: dict, capability: dict, action: str) -> dict:
        self._ensure_client()
        start = time.time()
        prompt = self._build_prompt(context, action)
        model = capability.get("model") or self.model

        response = self._client.messages.create(
            model=model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )

        text = response.content[0].text if response.content else ""

        return {
            "component": "execution",
            "mode": "live",
            "model": model,
            "action": action,
            "output": self._parse_claude_response(text, action),
            "raw": text,
            "tokens_used": getattr(response.usage, "output_tokens", 0),
            "duration_ms": int((time.time() - start) * 1000),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _run_simulated(self, context: dict, capability: dict, action: str) -> dict:
        start = time.time()

        if action == "generate-review":
            output = self._simulate_review(context)
        elif action == "generate-fix":
            output = self._simulate_fix(context)
        else:
            output = {"action": action, "simulated": True}

        return {
            "component": "execution",
            "mode": "simulate",
            "model": "local-heuristic",
            "action": action,
            "output": output,
            "duration_ms": int((time.time() - start) * 1000),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def _build_prompt(self, context: dict, action: str) -> str:
        files = next(
            (r for r in context.get("retrieved", []) if r["source"] == "files"), None
        )
        failures = next(
            (r for r in context.get("retrieved", []) if r["source"] == "failure-signals"),
            None,
        )

        if action == "generate-review":
            file_content = "\n\n".join(
                f"--- {f['path']} ({f['lines']} lines) ---\n{f['content']}"
                for f in (files or {}).get("items", [])
            ) or "No files provided."

            return (
                "You are a code reviewer for a platform engineering team.\n"
                "Analyze the following code and provide a structured review.\n"
                "Respond in JSON format with these fields:\n"
                '  categories: array of {category, severity, findings: string[]}\n'
                '  recommendation: "approve" | "approve-with-comments" | "request-changes"\n'
                "  summary: one-sentence summary\n\n"
                f"{file_content}"
            )

        if action == "generate-fix":
            failure_data = "\n".join(
                json.dumps(f) if isinstance(f, dict) else str(f)
                for f in (failures or {}).get("items", [])
            ) or "No failure data."

            file_content = "\n\n".join(
                f"--- {f['path']} ---\n{f['content']}"
                for f in (files or {}).get("items", [])
            ) or ""

            return (
                "You are a platform engineering agent fixing CI failures.\n"
                "Given the following failure signals and source code,\n"
                "produce the corrected source code.\n"
                "Respond with ONLY the corrected code, no explanation.\n\n"
                f"FAILURES:\n{failure_data}\n\nSOURCE:\n{file_content}"
            )

        return f"Perform action: {action}. Context: {json.dumps(context.get('retrieved', []))}"

    def _parse_claude_response(self, text: str, action: str) -> dict:
        if action == "generate-review":
            try:
                match = re.search(r"\{[\s\S]*\}", text)
                if match:
                    return json.loads(match.group())
            except json.JSONDecodeError:
                pass
            return {
                "summary": text[:200],
                "categories": [
                    {"category": "general", "severity": "info", "findings": [text[:300]]}
                ],
                "recommendation": "approve-with-comments",
            }

        if action == "generate-fix":
            code_match = re.search(r"```(?:python)?\n?([\s\S]*?)```", text)
            return {
                "fix_type": "claude-generated",
                "code": code_match.group(1).strip() if code_match else text.strip(),
                "patch_generated": True,
            }

        return {"raw": text}

    def _simulate_review(self, context: dict) -> dict:
        """
        Local heuristic review using Python's ast module.

        Parses actual source code and looks for real patterns —
        not canned responses. The findings are a function of
        the input, not a simulation.
        """
        files = next(
            (r for r in context.get("retrieved", []) if r["source"] == "files"), None
        )
        categories = []

        if files and files.get("items"):
            for f in files["items"]:
                content = f.get("content", "")

                # Real AST analysis
                try:
                    tree = ast.parse(content)
                    # Check for bare except clauses
                    for node in ast.walk(tree):
                        if isinstance(node, ast.ExceptHandler) and node.type is None:
                            categories.append({
                                "category": "correctness",
                                "severity": "warning",
                                "findings": [f"{f['path']}: bare except clause (catch specific exceptions)"],
                            })
                except SyntaxError as e:
                    categories.append({
                        "category": "correctness",
                        "severity": "error",
                        "findings": [f"{f['path']}: SyntaxError at line {e.lineno}"],
                    })

                # Pattern-based checks
                if "eval(" in content:
                    categories.append({
                        "category": "security",
                        "severity": "critical",
                        "findings": [f"{f['path']}: uses eval()"],
                    })
                if "import *" in content:
                    categories.append({
                        "category": "style",
                        "severity": "warning",
                        "findings": [f"{f['path']}: wildcard import"],
                    })
                if re.search(r"except\s*:", content):
                    categories.append({
                        "category": "correctness",
                        "severity": "warning",
                        "findings": [f"{f['path']}: bare except"],
                    })

        if not categories:
            categories.append({
                "category": "general",
                "severity": "none",
                "findings": ["No issues found"],
            })

        has_critical = any(c["severity"] == "critical" for c in categories)
        has_error = any(c["severity"] == "error" for c in categories)

        return {
            "summary": f"Reviewed {len(files.get('items', [])) if files else 0} file(s). {len(categories)} finding(s).",
            "categories": categories,
            "recommendation": (
                "request-changes" if has_critical else "approve-with-comments" if has_error else "approve"
            ),
            "evidence_trail": True,
        }

    def _simulate_fix(self, context: dict) -> dict:
        """Generate fix using local heuristics."""
        failures = next(
            (r for r in context.get("retrieved", []) if r["source"] == "failure-signals"),
            None,
        )
        files = next(
            (r for r in context.get("retrieved", []) if r["source"] == "files"), None
        )

        targets = []
        if failures:
            for f in failures.get("items", []):
                if isinstance(f, dict):
                    targets.append(f.get("code") or f.get("rule") or f.get("name") or "unknown")
                else:
                    targets.append(str(f))

        return {
            "fix_type": "simulated",
            "targets": targets,
            "patch_generated": files is not None and len(files.get("items", [])) > 0,
        }


class HarnessEvaluation:
    """
    Result evaluation component.

    Assesses the execution result and determines the next step:
    auto-approve, request changes, or escalate to human.

    PEH Ch.14: "Evaluation is the checkpoint. The agent's output
    is only as good as the evaluation that gates it."
    Companion: github.com/achankra/peh, ch14/harness_evaluation.py
    """

    async def evaluate(self, execution_result: dict, criteria: dict | None = None) -> dict:
        criteria = criteria or {}
        recommendation = execution_result.get("output", {}).get("recommendation")

        action = "pending-human-review"
        if criteria.get("auto_approve") and recommendation == "approve":
            action = "auto-approved"
        elif recommendation == "request-changes":
            action = "request-changes"

        return {
            "component": "evaluation",
            "recommendation": recommendation,
            "action": action,
            "mode": execution_result.get("mode"),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


class Harness:
    """
    HARNESS orchestrator. Runs all four components in sequence.

    PEH Ch.14: "Context → Capability → Execution → Evaluation.
    Every probabilistic and hybrid path follows this sequence."
    Companion: github.com/achankra/peh, ch14/harness.py
    """

    def __init__(self, simulate: bool = True, model: str | None = None):
        self.context = HarnessContext()
        self.capability = HarnessCapability()
        self.execution = HarnessExecution(simulate=simulate, model=model)
        self.evaluation = HarnessEvaluation()
        self.options = {"simulate": simulate, "model": model}

    async def run(self, input_data: dict, action: str, evaluation_criteria: dict | None = None) -> dict:
        ctx = await self.context.retrieve(input_data)
        cap = await self.capability.select(ctx, self.options)
        exec_result = await self.execution.run(ctx, cap, action)
        eval_result = await self.evaluation.evaluate(exec_result, evaluation_criteria)

        return {
            "harness": True,
            "components": {
                "context": ctx,
                "capability": cap,
                "execution": exec_result,
                "evaluation": eval_result,
            },
            "action": eval_result["action"],
            "mode": exec_result["mode"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
