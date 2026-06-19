"""
Tests for src/governance.py — GOVERNANCE control layer.

PEH Reference: Chapters 3, 4, 11, 14
Companion code: github.com/achankra/peh, ch14/test_governance.py
"""

import asyncio

import pytest

from src.governance import (
    Governance,
    GovernanceIdentity,
    GovernanceObservability,
    GovernanceSecurity,
)


class TestGovernanceIdentity:
    """PEH Ch.3: 'Identity is the first gate.'"""

    def test_register_and_verify(self):
        identity = GovernanceIdentity()
        identity.register("agent-001", {"team": "platform", "permissions": ["read"]})
        result = identity.verify("agent-001")
        assert result["verified"] is True
        assert result["agent_id"] == "agent-001"
        assert result["scope"]["team"] == "platform"

    def test_verify_unknown_agent(self):
        identity = GovernanceIdentity()
        result = identity.verify("unknown-agent")
        assert result["verified"] is False
        assert result["reason"] == "unknown-agent"


class TestGovernanceSecurity:
    """PEH Ch.11: 'Policy as Code — same policies, human or agent.'"""

    @pytest.mark.asyncio
    async def test_allow_when_no_policies(self):
        security = GovernanceSecurity()
        result = await security.enforce({"action": "review"})
        assert result["allowed"] is True
        assert result["policies_checked"] == 0

    @pytest.mark.asyncio
    async def test_enforce_passing_policy(self):
        security = GovernanceSecurity()
        security.add_policy({
            "name": "test-policy",
            "check": lambda action: {"allowed": True, "reason": "OK"},
        })
        result = await security.enforce({"action": "review"})
        assert result["allowed"] is True
        assert result["policies_checked"] == 1

    @pytest.mark.asyncio
    async def test_enforce_blocking_policy(self):
        security = GovernanceSecurity()
        security.add_policy({
            "name": "no-merge",
            "check": lambda action: {
                "allowed": action.get("action") != "merge",
                "reason": "Merge blocked" if action.get("action") == "merge" else "OK",
            },
        })
        result = await security.enforce({"action": "merge"})
        assert result["allowed"] is False

    @pytest.mark.asyncio
    async def test_multiple_policies_all_must_pass(self):
        security = GovernanceSecurity()
        security.add_policy({
            "name": "policy-a",
            "check": lambda _: {"allowed": True, "reason": "OK"},
        })
        security.add_policy({
            "name": "policy-b",
            "check": lambda _: {"allowed": False, "reason": "Denied"},
        })
        result = await security.enforce({"action": "review"})
        assert result["allowed"] is False


class TestGovernanceObservability:
    """PEH Ch.4: 'Observability is the ability to ask new questions.'"""

    def test_record_and_get_metrics(self):
        obs = GovernanceObservability()
        obs.record({"agent_id": "a1", "action": "auto-approved"})
        obs.record({"agent_id": "a2", "action": "rejected"})
        obs.record({"agent_id": "a3", "action": "escalated"})

        metrics = obs.get_metrics()
        assert metrics["total_executions"] == 3
        assert metrics["approvals"] == 1
        assert metrics["rejections"] == 1
        assert metrics["escalations"] == 1

    def test_audit_trail(self):
        obs = GovernanceObservability()
        obs.record({"agent_id": "a1", "action": "completed", "path": "/ci-build"})
        trail = obs.get_audit_trail()
        assert len(trail) == 1
        assert trail[0]["path"] == "/ci-build"
        assert "recorded_at" in trail[0]

    def test_reset(self):
        obs = GovernanceObservability()
        obs.record({"agent_id": "a1", "action": "completed"})
        obs.reset()
        assert obs.get_metrics()["total_executions"] == 0
        assert len(obs.get_audit_trail()) == 0


class TestGovernance:
    """Full GOVERNANCE orchestrator — wrap with identity + security + observability."""

    @pytest.mark.asyncio
    async def test_wrap_success(self):
        gov = Governance()
        gov.identity.register("agent-001", {"team": "platform"})
        gov.security.add_policy({
            "name": "allow-all",
            "check": lambda _: {"allowed": True, "reason": "OK"},
        })

        result = await gov.wrap(
            "agent-001",
            {"path": "/ci-build", "action": "review"},
            lambda: {"action": "completed", "data": "test"},
        )

        assert result["allowed"] is True
        assert result["result"]["data"] == "test"
        assert result["identity"]["verified"] is True
        assert gov.observability.get_metrics()["total_executions"] == 1

    @pytest.mark.asyncio
    async def test_wrap_identity_failure(self):
        gov = Governance()
        # Do not register agent
        result = await gov.wrap(
            "unknown",
            {"path": "/ci-build", "action": "review"},
            lambda: {"action": "completed"},
        )
        assert result["allowed"] is False
        assert result["reason"] == "identity-verification-failed"

    @pytest.mark.asyncio
    async def test_wrap_policy_violation(self):
        gov = Governance()
        gov.identity.register("agent-001", {"team": "platform"})
        gov.security.add_policy({
            "name": "deny-all",
            "check": lambda _: {"allowed": False, "reason": "Blocked"},
        })

        result = await gov.wrap(
            "agent-001",
            {"path": "/pr-review", "action": "merge"},
            lambda: {"action": "completed"},
        )
        assert result["allowed"] is False
        assert result["reason"] == "policy-violation"
        assert gov.observability.get_metrics()["rejections"] == 1
