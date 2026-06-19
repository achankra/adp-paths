"""
Tests for src/harness.py — HARNESS agent execution orchestrator.

All tests use simulate mode (no API calls, no cost).

PEH Reference: Chapter 14 (Agentic Platforms)
Companion code: github.com/achankra/peh, ch14/test_harness.py
"""

import os
import tempfile
from pathlib import Path

import pytest

from src.harness import (
    Harness,
    HarnessCapability,
    HarnessContext,
    HarnessEvaluation,
    HarnessExecution,
)

SAMPLE_DIR = Path(__file__).parent.parent / "sample" / "src"


class TestHarnessContext:

    @pytest.mark.asyncio
    async def test_retrieve_files(self):
        ctx = HarnessContext()
        result = await ctx.retrieve({
            "file_paths": [str(SAMPLE_DIR / "handler.py")],
        })
        assert result["component"] == "context"
        files = next(r for r in result["retrieved"] if r["source"] == "files")
        assert len(files["items"]) == 1
        assert files["items"][0]["path"] == "handler.py"
        assert files["items"][0]["lines"] > 0

    @pytest.mark.asyncio
    async def test_retrieve_failures(self):
        ctx = HarnessContext()
        result = await ctx.retrieve({
            "failures": [{"rule": "no-eval", "line": 5}],
        })
        signals = next(r for r in result["retrieved"] if r["source"] == "failure-signals")
        assert len(signals["items"]) == 1

    @pytest.mark.asyncio
    async def test_retrieve_empty(self):
        ctx = HarnessContext()
        result = await ctx.retrieve({})
        assert result["component"] == "context"
        assert len(result["retrieved"]) == 0


class TestHarnessCapability:

    @pytest.mark.asyncio
    async def test_select_default_model(self):
        cap = HarnessCapability()
        context = {"retrieved": []}
        result = await cap.select(context)
        assert result["component"] == "capability"
        assert "model" in result
        assert result["strategy"] == "standard"

    @pytest.mark.asyncio
    async def test_select_security_strategy(self):
        cap = HarnessCapability()
        context = {
            "retrieved": [
                {"source": "change-metadata", "items": [{"change_type": "security-sensitive"}]},
            ]
        }
        result = await cap.select(context)
        assert result["strategy"] == "deep-scan"

    @pytest.mark.asyncio
    async def test_select_with_model_override(self):
        cap = HarnessCapability()
        result = await cap.select(
            {"retrieved": []},
            {"model": "claude-haiku-4-5-20251001"},
        )
        assert result["model"] == "claude-haiku-4-5-20251001"


class TestHarnessExecution:

    @pytest.mark.asyncio
    async def test_simulate_review(self):
        """Simulate mode should analyze real file content."""
        exc = HarnessExecution(simulate=True)
        context = {
            "retrieved": [
                {
                    "source": "files",
                    "items": [
                        {"path": "handler.py", "content": "def foo():\n    return 1\n", "lines": 2},
                    ],
                },
            ],
        }
        capability = {"model": "local-heuristic"}
        result = await exc.run(context, capability, "generate-review")

        assert result["component"] == "execution"
        assert result["mode"] == "simulate"
        assert "output" in result
        assert "recommendation" in result["output"]

    @pytest.mark.asyncio
    async def test_simulate_review_detects_eval(self):
        """Simulate review should detect eval() as critical."""
        exc = HarnessExecution(simulate=True)
        context = {
            "retrieved": [
                {
                    "source": "files",
                    "items": [
                        {"path": "bad.py", "content": 'x = eval("1+1")\n', "lines": 1},
                    ],
                },
            ],
        }
        capability = {"model": "local-heuristic"}
        result = await exc.run(context, capability, "generate-review")

        assert result["output"]["recommendation"] == "request-changes"
        assert any(
            c["severity"] == "critical"
            for c in result["output"]["categories"]
        )

    @pytest.mark.asyncio
    async def test_simulate_fix(self):
        """Simulate fix should return targets from failure signals."""
        exc = HarnessExecution(simulate=True)
        context = {
            "retrieved": [
                {"source": "failure-signals", "items": [{"code": "F401"}, {"code": "E501"}]},
                {"source": "files", "items": [{"path": "test.py", "content": "x = 1\n", "lines": 1}]},
            ],
        }
        capability = {"model": "local-heuristic"}
        result = await exc.run(context, capability, "generate-fix")

        assert result["mode"] == "simulate"
        assert "F401" in result["output"]["targets"]


class TestHarnessEvaluation:

    @pytest.mark.asyncio
    async def test_approve_recommendation(self):
        evl = HarnessEvaluation()
        result = await evl.evaluate(
            {"output": {"recommendation": "approve"}, "mode": "simulate"},
            {"auto_approve": True},
        )
        assert result["action"] == "auto-approved"

    @pytest.mark.asyncio
    async def test_request_changes(self):
        evl = HarnessEvaluation()
        result = await evl.evaluate(
            {"output": {"recommendation": "request-changes"}, "mode": "simulate"},
        )
        assert result["action"] == "request-changes"

    @pytest.mark.asyncio
    async def test_default_pending_review(self):
        evl = HarnessEvaluation()
        result = await evl.evaluate(
            {"output": {"recommendation": "approve"}, "mode": "simulate"},
        )
        # auto_approve not set, so should be pending
        assert result["action"] == "pending-human-review"


class TestHarness:
    """Full HARNESS orchestration in simulate mode."""

    @pytest.mark.asyncio
    async def test_full_review_flow(self):
        harness = Harness(simulate=True)
        result = await harness.run(
            {"file_paths": [str(SAMPLE_DIR / "handler.py")]},
            "generate-review",
            {"auto_approve": False},
        )
        assert result["harness"] is True
        assert result["mode"] == "simulate"
        assert "components" in result
        assert all(
            k in result["components"]
            for k in ("context", "capability", "execution", "evaluation")
        )

    @pytest.mark.asyncio
    async def test_full_fix_flow(self):
        harness = Harness(simulate=True)
        result = await harness.run(
            {
                "file_paths": [str(SAMPLE_DIR / "handler.py")],
                "failures": [{"code": "F401", "message": "unused import"}],
            },
            "generate-fix",
            {"min_confidence": 0.70},
        )
        assert result["harness"] is True
        assert result["mode"] == "simulate"
