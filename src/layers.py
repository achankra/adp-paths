"""
ADP Three-Layer Architecture

L01 — Tooling (IDP): The deterministic foundation. CI pipelines, policy
      gates, observability, identity. Does not change when agents arrive.
L02 — Path Definitions: The eight paths to outcomes. Each typed as
      deterministic, probabilistic, or hybrid.
L03 — Agent Infrastructure: HARNESS (Context, Capability, Execution,
      Evaluation) and GOVERNANCE (Identity, Security, Observability).

    "An IDP standardizes paths for humans;
     an ADP makes those paths executable by agents at scale."
    — From IDP to ADP (Weave Intelligence, 2025)

PEH Reference:
    Chapter 1  — Groundwork (platform foundations)
    Chapter 2  — Kubernetes/Runtime (L01 infrastructure)
    Chapter 8  — CI/CD as a Platform Service (L01 pipelines)
    Chapter 9  — Infrastructure as Code (L01 provisioning)
    Chapter 10 — Starter Kits and Golden Paths (L02 path definitions)
    Chapter 14 — Agentic and AI-Augmented Platforms (L03 agent infra)

Companion code: github.com/achankra/peh, Chapters 1, 8, 10, 14
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable

from src.observability import ObservabilityStack, SpanStatus


class PathType(str, Enum):
    """
    Path classification. Every path to outcome is one of these three.

    PEH Ch.14: "Each path is typed — deterministic, probabilistic,
    or hybrid — and the type determines which layers activate."
    Companion: github.com/achankra/peh, ch14/path_types.py
    """

    DETERMINISTIC = "deterministic"
    PROBABILISTIC = "probabilistic"
    HYBRID = "hybrid"


# ── L01 — IDP Tooling Layer ──────────────────────────────────────


class L01Tooling:
    """
    L01 — The deterministic fabric.

    Provides pipelines, policy gates, and telemetry. This layer is
    identical at L0/L1 and L2. It does not bend for agents.

    When an ObservabilityStack is provided, pipeline runs are traced
    with spans — one root span per pipeline, one child span per stage.

    PEH Ch.8: "The pipeline is the arbiter. It does not know or care
    whether the code was written by a human or an agent."
    Companion: github.com/achankra/peh, ch08/pipeline.py
    """

    def __init__(self, obs_stack: ObservabilityStack | None = None):
        self.pipelines: dict[str, list[dict]] = {}
        self.policies: dict[str, Callable] = {}
        self.telemetry: list[dict] = []
        self._obs_stack = obs_stack

    def register_pipeline(self, name: str, stages: list[dict]):
        """Register a named pipeline with its stages."""
        self.pipelines[name] = stages

    def register_policy(self, name: str, check: Callable):
        """Register a named policy gate."""
        self.policies[name] = check

    async def run_pipeline(self, name: str, input_data: Any) -> dict:
        """
        Execute a pipeline. Fail-fast on first stage failure.

        When an ObservabilityStack is attached, each pipeline run
        is a trace and each stage is a span within that trace.

        PEH Ch.8: "Deterministic pipelines fail fast. There is no
        point running security scans on code that doesn't compile."
        Companion: github.com/achankra/peh, ch08/pipeline.py
        """
        stages = self.pipelines.get(name)
        if stages is None:
            raise ValueError(f"Pipeline not found: {name}")

        # Start pipeline span if obs stack is available
        pipeline_span = None
        if self._obs_stack:
            pipeline_span = self._obs_stack.tracer.start_span(
                f"pipeline-{name}",
                attributes={"pipeline.name": name, "pipeline.stages": len(stages)},
            )
            self._obs_stack.logger.info(f"Pipeline started: {name}", pipeline=name)

        results = []
        all_passed = True

        for stage in stages:
            # Start stage span
            stage_span = None
            if self._obs_stack and pipeline_span:
                stage_span = self._obs_stack.tracer.start_span(
                    f"stage-{stage['name']}",
                    parent=pipeline_span,
                    attributes={"stage.name": stage["name"], "stage.tool": stage["tool"]},
                )

            result = await stage["run"](input_data)
            results.append({
                "name": stage["name"],
                "tool": stage["tool"],
                "passed": result["passed"],
                "output": result["output"],
                "detail": result.get("detail"),
            })

            # End stage span
            if stage_span:
                stage_span.set_attribute("stage.passed", result["passed"])
                self._obs_stack.tracer.end_span(
                    stage_span,
                    SpanStatus.OK if result["passed"] else SpanStatus.ERROR,
                )
                self._obs_stack.metrics.counter(
                    "pipeline_stage_runs",
                    labels={"pipeline": name, "stage": stage["name"],
                            "passed": str(result["passed"])},
                )

            if not result["passed"]:
                all_passed = False
                break  # Fail-fast

        # End pipeline span
        if pipeline_span:
            pipeline_span.set_attribute("pipeline.passed", all_passed)
            self._obs_stack.tracer.end_span(
                pipeline_span,
                SpanStatus.OK if all_passed else SpanStatus.ERROR,
            )
            self._obs_stack.metrics.counter(
                "pipeline_runs",
                labels={"pipeline": name, "passed": str(all_passed)},
            )

        record = {
            "pipeline": name,
            "passed": all_passed,
            "stages": results,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        self.telemetry.append(record)
        return record

    async def enforce_policy(self, name: str, subject: Any) -> dict:
        """Enforce a registered policy against a subject."""
        check = self.policies.get(name)
        if check is None:
            raise ValueError(f"Policy not found: {name}")
        return await check(subject)

    def get_telemetry(self) -> list[dict]:
        return list(self.telemetry)

    def reset(self):
        self.telemetry.clear()


# ── L02 — Path Definitions Layer ─────────────────────────────────


@dataclass
class PathDefinition:
    """
    A registered path to outcome.

    PEH Ch.10: "Golden paths are not suggestions. They are the
    platform team's answer to 'how do we do X here?'"
    Companion: github.com/achankra/peh, ch10/golden_paths.py
    """

    name: str
    type: PathType
    layers: list[str]
    description: str = ""


class L02PathDefinitions:
    """
    L02 — Registry of the eight paths to outcomes.

    Each path declares its type and which layers it requires.
    At L0/L1, only two paths are altered (Retrieve Context,
    Implement Change). At L2, six of eight paths are new or altered,
    and Dispatch Work is NEW.

    PEH Ch.10: "Starter kits encode the golden path."
    Companion: github.com/achankra/peh, ch10/path_registry.py
    """

    def __init__(self):
        self.paths: dict[str, PathDefinition] = {}

    def register(self, path: PathDefinition):
        self.paths[path.name] = path

    def get(self, name: str) -> PathDefinition | None:
        return self.paths.get(name)

    def get_all(self) -> list[PathDefinition]:
        return list(self.paths.values())

    def requires_agent_infra(self, name: str) -> bool:
        path = self.paths.get(name)
        if path is None:
            return False
        return path.type in (PathType.PROBABILISTIC, PathType.HYBRID)


# ── L03 — Agent Infrastructure Layer ─────────────────────────────


class L03AgentInfra:
    """
    L03 — Agent Infrastructure.

    Only activates for paths typed as probabilistic or hybrid.
    Contains HARNESS (orchestration) and GOVERNANCE (control).
    See: harness.py, governance.py

    PEH Ch.14: "Agent infrastructure is not a separate system.
    It is a layer that activates on top of the existing platform
    when a path requires non-deterministic execution."
    Companion: github.com/achankra/peh, ch14/agent_infra.py
    """

    def __init__(self, harness=None, governance=None):
        self.harness = harness
        self.governance = governance
        self.active = False

    def activate(self):
        self.active = True

    def deactivate(self):
        self.active = False

    def is_active(self) -> bool:
        return self.active
