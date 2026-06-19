"""
Tests for the three platform paths:
    /ci-build        — Deterministic
    /pr-review       — Probabilistic
    /validate-change — Hybrid

All tests use simulate mode (no API calls).
All tests run against real sample code (sample/src/).

PEH Reference: Chapter 14 (Agentic Platforms)
Companion code: github.com/achankra/peh, ch14/test_paths.py
"""

from pathlib import Path

import pytest

from src.paths import ci_build, pr_review, validate_change

SAMPLE_DIR = Path(__file__).parent.parent / "sample" / "src"
SAMPLE_FILES = [
    str(SAMPLE_DIR / "handler.py"),
    str(SAMPLE_DIR / "utils.py"),
]


# ── /ci-build — Deterministic ────────────────────────────────────


class TestCiBuild:
    """
    The pipeline is identical at L0-L1 and L2. It stays on L01.
    No HARNESS. No GOVERNANCE.

    PEH Ch.8: "The pipeline is the arbiter."
    """

    @pytest.mark.asyncio
    async def test_l01_runs_all_stages(self):
        result = await ci_build.run_at_l01({"file_paths": SAMPLE_FILES})
        assert result["path"] == "/ci-build"
        assert result["maturity_level"] == "L0-L1"
        assert result["type"] == "deterministic"
        assert result["layers"] == ["L01"]
        assert result["triggered_by"] == "human"
        assert result["harness"] is None
        assert result["governance"] is None
        assert len(result["pipeline"]["stages"]) == 4

    @pytest.mark.asyncio
    async def test_l01_pipeline_passes_clean_code(self):
        result = await ci_build.run_at_l01({"file_paths": SAMPLE_FILES})
        assert result["pipeline"]["passed"]

    @pytest.mark.asyncio
    async def test_l02_identical_to_l01(self):
        """Pipeline is unchanged at L2 — same stages, same result."""
        result = await ci_build.run_at_l02({
            "file_paths": SAMPLE_FILES,
            "triggered_by": "agent-commit",
        })
        assert result["maturity_level"] == "L2"
        assert result["layers"] == ["L01"]  # Still only L01
        assert result["harness"] is None  # Still no HARNESS
        assert result["triggered_by"] == "agent-commit"

    @pytest.mark.asyncio
    async def test_l02_pipeline_passes(self):
        result = await ci_build.run_at_l02({"file_paths": SAMPLE_FILES})
        assert result["pipeline"]["passed"]


# ── /pr-review — Probabilistic ───────────────────────────────────


class TestPrReview:
    """
    At L0-L1: manual. At L2: agent-driven with HARNESS + GOVERNANCE.

    PEH Ch.14: "The agent reviews with context and evidence.
    The human validates — the agent does not merge."
    """

    @pytest.mark.asyncio
    async def test_l01_manual_review(self):
        result = await pr_review.run_at_l01({
            "files": SAMPLE_FILES,
            "lines_changed": 42,
            "obvious": False,
        })
        assert result["path"] == "/pr-review"
        assert result["maturity_level"] == "L0-L1"
        assert result["review"]["reviewer"] == "human"
        assert result["review"]["context_loaded"] is False
        assert result["review"]["evidence_trail"] is False
        assert result["harness"] is None
        assert result["governance"] is None

    @pytest.mark.asyncio
    async def test_l02_agent_review_simulate(self):
        result = await pr_review.run_at_l02(
            {
                "file_paths": SAMPLE_FILES,
                "change_type": "routine",
                "team": "platform",
            },
            {"simulate": True},
        )
        assert result["maturity_level"] == "L2"
        assert result["type"] == "probabilistic"
        assert result["mode"] == "simulate"
        assert result["layers"] == ["L01", "L02", "L03"]
        assert result["review"]["reviewer"] == "agent"
        assert result["review"]["context_loaded"] is True
        assert result["review"]["evidence_trail"] is True
        assert result["review"]["recommendation"] in (
            "approve", "approve-with-comments", "request-changes",
        )

    @pytest.mark.asyncio
    async def test_l02_has_harness(self):
        result = await pr_review.run_at_l02(
            {"file_paths": SAMPLE_FILES},
            {"simulate": True},
        )
        assert result["harness"] is not None
        assert "context" in result["harness"]
        assert "capability" in result["harness"]
        assert "execution" in result["harness"]
        assert "evaluation" in result["harness"]

    @pytest.mark.asyncio
    async def test_l02_has_governance(self):
        result = await pr_review.run_at_l02(
            {"file_paths": SAMPLE_FILES},
            {"simulate": True},
        )
        gov = result["governance"]
        assert gov is not None
        assert gov["identity"]["verified"] is True
        assert gov["security"]["policies_checked"] >= 2
        assert gov["observability"]["total_executions"] >= 1


# ── /validate-change — Hybrid ────────────────────────────────────


class TestValidateChange:
    """
    The most underestimated shift. Agent + deterministic gate
    in a feedback loop.

    PEH Ch.13: "The gate does not change. The agent adapts."
    """

    @pytest.mark.asyncio
    async def test_l01_single_gate(self):
        result = await validate_change.run_at_l01({"file_paths": SAMPLE_FILES})
        assert result["path"] == "/validate-change"
        assert result["maturity_level"] == "L0-L1"
        assert result["type"] == "gate"
        assert result["attempts"] == 1
        assert result["loop"] is None
        assert result["harness"] is None

    @pytest.mark.asyncio
    async def test_l01_clean_code_passes(self):
        result = await validate_change.run_at_l01({"file_paths": SAMPLE_FILES})
        assert result["pipeline"]["passed"]

    @pytest.mark.asyncio
    async def test_l02_hybrid_loop_simulate(self):
        """With clean code, should pass on first attempt."""
        result = await validate_change.run_at_l02(
            {"file_paths": SAMPLE_FILES},
            {"max_retries": 3, "simulate": True},
        )
        assert result["maturity_level"] == "L2"
        assert result["type"] == "hybrid"
        assert result["mode"] == "simulate"
        assert result["layers"] == ["L01", "L02", "L03"]
        assert result["result"]["status"] == "passed"
        assert result["attempts"] >= 1

    @pytest.mark.asyncio
    async def test_l02_loop_trace_exists(self):
        result = await validate_change.run_at_l02(
            {"file_paths": SAMPLE_FILES},
            {"simulate": True},
        )
        assert isinstance(result["loop"], list)
        assert len(result["loop"]) >= 1
        # First entry should record the attempt
        entry = result["loop"][0]
        assert "attempt" in entry
        assert "pipeline" in entry
        assert "outcome" in entry

    @pytest.mark.asyncio
    async def test_l02_has_governance(self):
        result = await validate_change.run_at_l02(
            {"file_paths": SAMPLE_FILES},
            {"simulate": True},
        )
        assert result["governance"] is not None
        assert "observability" in result["governance"]
        assert "audit_trail" in result["governance"]

    @pytest.mark.asyncio
    async def test_l02_resolves_by_first_pass_or_fix(self):
        result = await validate_change.run_at_l02(
            {"file_paths": SAMPLE_FILES},
            {"simulate": True},
        )
        assert result["result"]["resolved_by"] in ("first-pass", "agent-fix")
