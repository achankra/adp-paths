"""
GOVERNANCE — Agent Control Layer

Three components that control how the agent operates:
    Identity      — Who or what is acting (agent identity, team scope)
    Security      — What is allowed (RBAC, policy enforcement)
    Observability — What happened (telemetry, audit trail)

GOVERNANCE is mandatory for all agent-driven paths.
Every HARNESS execution is wrapped by GOVERNANCE.

    "Without governance, agent autonomy is just agent chaos."
    — The Platform Engineer's Handbook, Chapter 14

PEH Reference:
    Chapter 3  — Securing Platform Access (RBAC, identity, OPA)
    Chapter 4  — Embedding Observability (telemetry, tracing)
    Chapter 11 — Policy as Code (OPA policies, admission control)
    Chapter 14 — Agentic Platforms (agent governance, guardrails)

Companion code: github.com/achankra/peh, Chapters 3, 4, 11, 14
"""

from __future__ import annotations

import asyncio
import inspect
from datetime import datetime, timezone
from typing import Any, Callable


class GovernanceIdentity:
    """
    Agent identity verification.

    Every agent that touches a platform path must be registered
    and verified before execution. No anonymous agents.

    PEH Ch.3: "Identity is the first gate. If you cannot prove
    who you are, you cannot act."
    Companion: github.com/achankra/peh, ch03/identity.py
    """

    def __init__(self):
        self.registered_agents: dict[str, dict] = {}

    def register(self, agent_id: str, scope: dict):
        """Register an agent identity with its scope."""
        self.registered_agents[agent_id] = {
            "id": agent_id,
            "scope": scope,
            "registered_at": datetime.now(timezone.utc).isoformat(),
        }

    def verify(self, agent_id: str) -> dict:
        """
        Verify an agent's identity before execution.

        PEH Ch.3: "Verification is not optional. Even internal
        agents go through the same RBAC gates as external ones."
        """
        agent = self.registered_agents.get(agent_id)
        if agent is None:
            return {"verified": False, "reason": "unknown-agent", "agent_id": agent_id}
        return {
            "verified": True,
            "agent_id": agent["id"],
            "scope": agent["scope"],
            "verified_at": datetime.now(timezone.utc).isoformat(),
        }


class GovernanceSecurity:
    """
    Policy enforcement layer.

    Every agent action is checked against registered policies
    before execution. Policies are functions that return
    {"allowed": bool, "reason": str}.

    PEH Ch.11: "Policy as Code — the same policies that gate
    human deployments must gate agent deployments."
    Companion: github.com/achankra/peh, ch11/policy_gate.py
    """

    def __init__(self):
        self.policies: list[dict] = []

    def add_policy(self, policy: dict):
        """Add a security policy check."""
        self.policies.append(policy)

    async def enforce(self, action: dict) -> dict:
        """
        Enforce all registered policies against an action.

        Handles both sync and async policy check functions.

        PEH Ch.11: "Policies are evaluated in sequence. A single
        deny is a deny — there is no override without audit."
        """
        results = []
        all_allowed = True

        for policy in self.policies:
            check_fn = policy["check"]
            result = check_fn(action)
            if inspect.isawaitable(result):
                result = await result
            results.append({
                "policy": policy["name"],
                "allowed": result["allowed"],
                "reason": result["reason"],
            })
            if not result["allowed"]:
                all_allowed = False

        return {
            "allowed": all_allowed,
            "policies_checked": len(results),
            "results": results,
            "enforced_at": datetime.now(timezone.utc).isoformat(),
        }


class GovernanceObservability:
    """
    Telemetry and audit trail.

    Every agent action is recorded — approved, rejected, escalated,
    or overridden. The audit trail is immutable within a session.

    PEH Ch.4: "Observability is not logging. Observability is the
    ability to ask new questions of your system without deploying
    new code."
    Companion: github.com/achankra/peh, ch04/observability.py
    """

    def __init__(self):
        self.events: list[dict] = []
        self.metrics = {
            "total_executions": 0,
            "approvals": 0,
            "rejections": 0,
            "escalations": 0,
            "overrides": 0,
        }

    def record(self, event: dict):
        """Record an event in the audit trail."""
        self.events.append({
            **event,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        })
        self.metrics["total_executions"] += 1

        action = event.get("action", "")
        if action in ("auto-approved", "human-approved"):
            self.metrics["approvals"] += 1
        elif action == "rejected":
            self.metrics["rejections"] += 1
        elif action in ("escalated-low-confidence", "escalated"):
            self.metrics["escalations"] += 1
        elif action == "human-override":
            self.metrics["overrides"] += 1

    def get_metrics(self) -> dict:
        return dict(self.metrics)

    def get_audit_trail(self) -> list[dict]:
        return list(self.events)

    def reset(self):
        self.events.clear()
        self.metrics = {
            "total_executions": 0,
            "approvals": 0,
            "rejections": 0,
            "escalations": 0,
            "overrides": 0,
        }


class Governance:
    """
    GOVERNANCE orchestrator.

    Wraps every agent action with identity verification, policy
    enforcement, and observability recording.

    PEH Ch.14: "GOVERNANCE is not bureaucracy. It is the control
    plane that makes agent autonomy safe."
    Companion: github.com/achankra/peh, ch14/governance.py
    """

    def __init__(self):
        self.identity = GovernanceIdentity()
        self.security = GovernanceSecurity()
        self.observability = GovernanceObservability()

    async def wrap(self, agent_id: str, action: dict, fn: Callable) -> dict:
        """
        Wrap an agent action with full governance.

        Sequence: verify identity → enforce policies → execute → record.
        If identity fails or policy denies, the action never executes.
        """
        # 1. Verify identity
        identity_result = self.identity.verify(agent_id)
        if not identity_result["verified"]:
            self.observability.record({
                "agent_id": agent_id,
                "action": "rejected",
                "reason": identity_result["reason"],
                "path": action.get("path"),
            })
            return {
                "allowed": False,
                "reason": "identity-verification-failed",
                "identity": identity_result,
            }

        # 2. Enforce security policies
        security_result = await self.security.enforce(action)
        if not security_result["allowed"]:
            self.observability.record({
                "agent_id": agent_id,
                "action": "rejected",
                "reason": "policy-violation",
                "path": action.get("path"),
                "policies": security_result["results"],
            })
            return {
                "allowed": False,
                "reason": "policy-violation",
                "identity": identity_result,
                "security": security_result,
            }

        # 3. Execute the wrapped function (sync or async)
        result = fn()
        if inspect.isawaitable(result):
            result = await result

        # 4. Record in observability
        self.observability.record({
            "agent_id": agent_id,
            "action": result.get("action", "completed"),
            "path": action.get("path"),
        })

        return {
            "allowed": True,
            "identity": identity_result,
            "security": security_result,
            "result": result,
        }
