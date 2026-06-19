"""
/dispatch-work — Dispatch Path (L2 only)

This path does NOT exist at L0/L1. At L0 and L1, humans pick up work
themselves — from a backlog, a Kanban board, a PR queue. There is no
dispatch. The concept of assigning work to an agent is new at L2.

At L2, Dispatch Work is the orchestrator that feeds the other paths.
It receives work items, matches them to agents based on capability,
assigns with GOVERNANCE wrapping, and tracks outcomes.

Three-layer mapping:
    L01 — WorkQueue: infrastructure for queueing work items
    L02 — Path definition: dispatch typed as probabilistic
    L03 — HARNESS: context → capability matching → assignment → evaluation
          GOVERNANCE: identity verification, scope enforcement, audit trail

PEH Reference:
    Chapter 8  — CI/CD as a Platform Service (pipeline triggering)
    Chapter 10 — Starter Kits and Golden Paths (path definitions)
    Chapter 14 — Agentic Platforms (dispatch, agent orchestration)

Companion code: github.com/achankra/peh, ch14/dispatch.py
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone

from src.governance import Governance
from src.harness import Harness  # noqa: F401 — referenced conceptually
from src.layers import PathType
from src.observability import ObservabilityStack, SpanStatus

# ── Work Item ───────────────────────────────────────────────────


@dataclass
class WorkItem:
    """
    A unit of work to be dispatched.

    Work items arrive from external triggers — a PR opened, a commit
    pushed, a scheduled validation, a remediation alert. Each item
    has a type that maps to a platform path.

    """

    id: str
    type: str  # "review", "validate", "build", "remediate"
    priority: str = "medium"  # "critical", "high", "medium", "low"
    source: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # Dispatch state
    assigned_to: str | None = None
    assigned_at: str | None = None
    status: str = "pending"  # pending, assigned, completed, failed, escalated


# ── Work Queue — L01 Infrastructure ─────────────────────────────


class WorkQueue:
    """
    L01 work queue infrastructure.

    A priority-ordered queue for work items. This is platform
    infrastructure — it exists at L01 regardless of whether agents
    or humans consume from it.

    """

    def __init__(self):
        self._queues: dict[str, deque[WorkItem]] = {
            "critical": deque(),
            "high": deque(),
            "medium": deque(),
            "low": deque(),
        }

    def enqueue(self, item: WorkItem):
        """Add a work item to the appropriate priority queue."""
        priority = item.priority if item.priority in self._queues else "medium"
        self._queues[priority].append(item)

    def dequeue(self) -> WorkItem | None:
        """
        Dequeue the highest-priority item.

        Priority order: critical → high → medium → low.
        Within a priority level, FIFO ordering.
        """
        for priority in ("critical", "high", "medium", "low"):
            if self._queues[priority]:
                return self._queues[priority].popleft()
        return None

    def peek(self) -> list[WorkItem]:
        """Return all queued items without removing them, highest priority first."""
        items = []
        for priority in ("critical", "high", "medium", "low"):
            items.extend(self._queues[priority])
        return items

    def size(self) -> int:
        """Total number of items across all priority levels."""
        return sum(len(q) for q in self._queues.values())

    def size_by_priority(self) -> dict[str, int]:
        """Item count per priority level."""
        return {p: len(q) for p, q in self._queues.items()}


# ── Agent Registry — L01 Infrastructure ─────────────────────────


@dataclass
class AgentCapability:
    """
    Registered agent with its capabilities.

    The dispatcher matches work items to agents based on declared
    capabilities and current load.

    """

    agent_id: str
    capabilities: list[str]  # work types this agent handles
    max_concurrent: int = 3
    current_load: int = 0

    def can_handle(self, work_type: str) -> bool:
        """Check if this agent can handle a given work type."""
        return work_type in self.capabilities

    def has_capacity(self) -> bool:
        """Check if agent has capacity for more work."""
        return self.current_load < self.max_concurrent


# ── Dispatcher — L02 Path Logic ─────────────────────────────────


# Agent-to-path mapping: which work types map to which platform paths
WORK_TYPE_TO_PATH = {
    "review": "/pr-review",
    "validate": "/validate-change",
    "build": "/ci-build",
    "remediate": "/remediate-issue",
}


def _match_agent(
    work_item: WorkItem,
    agents: list[AgentCapability],
) -> AgentCapability | None:
    """
    Match a work item to the best available agent.

    Selection criteria: capability match → capacity → lowest load.

    """
    candidates = [
        a for a in agents if a.can_handle(work_item.type) and a.has_capacity()
    ]
    if not candidates:
        return None
    # Prefer agent with lowest current load
    return min(candidates, key=lambda a: a.current_load)


# ── Path Execution ──────────────────────────────────────────────


async def run_at_l01(work_items: list[dict]) -> dict:
    """
    Run /dispatch-work at L0-L1 (human-driven).

    At L0 and L1, there is no dispatch. Humans pick up work from
    a backlog. The platform queues items but does not assign them.

    """
    queue = WorkQueue()
    items = []

    for raw in work_items:
        item = WorkItem(
            id=raw.get("id", f"work-{len(items) + 1}"),
            type=raw.get("type", "review"),
            priority=raw.get("priority", "medium"),
            source=raw.get("source", {}),
            metadata=raw.get("metadata", {}),
        )
        queue.enqueue(item)
        items.append(item)

    return {
        "path": "/dispatch-work",
        "maturity_level": "L0-L1",
        "type": "manual",
        "layers": ["L01"],
        "triggered_by": "human",
        "dispatch": {
            "method": "manual-backlog",
            "queue_size": queue.size(),
            "queue_by_priority": queue.size_by_priority(),
            "items_queued": len(items),
            "items_assigned": 0,
            "assignment_method": "human-picks-from-board",
        },
        "harness": None,
        "governance": None,
        "summary": {
            "l01": f"Work queue loaded with {len(items)} item(s)",
            "l02": "None — no dispatch path at L0-L1",
            "l03": "None — no agent infrastructure",
        },
    }


async def run_at_l02(
    work_items: list[dict],
    options: dict | None = None,
) -> dict:
    """
    Run /dispatch-work at L2 (agent dispatch).

    The full dispatch pipeline: queue → capability match → HARNESS
    context/evaluation → GOVERNANCE-wrapped assignment → tracking.

    This is where "Dispatch Work" becomes a real path. The dispatcher
    selects agents based on capability, enforces scope via GOVERNANCE,
    and records every assignment in the observability layer.

    """
    options = options or {}
    start = time.time()
    simulate = options.get("simulate", True)

    governance = Governance()
    obs = ObservabilityStack(service_name="dispatch-work")

    # Start root trace span
    root_span = obs.tracer.start_span("dispatch-cycle", attributes={
        "work_items.count": len(work_items),
    })
    obs.logger.info("Dispatch cycle started", item_count=len(work_items))

    # L01: Load work items into queue
    queue = WorkQueue()
    parsed_items: list[WorkItem] = []
    for raw in work_items:
        item = WorkItem(
            id=raw.get("id", f"work-{len(parsed_items) + 1}"),
            type=raw.get("type", "review"),
            priority=raw.get("priority", "medium"),
            source=raw.get("source", {}),
            metadata=raw.get("metadata", {}),
        )
        queue.enqueue(item)
        parsed_items.append(item)

    obs.metrics.gauge("dispatch_queue_size", queue.size())

    # Register available agents
    agents = options.get("agents") or [
        AgentCapability(
            agent_id="review-agent-001",
            capabilities=["review"],
            max_concurrent=5,
        ),
        AgentCapability(
            agent_id="validate-agent-001",
            capabilities=["validate"],
            max_concurrent=3,
        ),
        AgentCapability(
            agent_id="build-agent-001",
            capabilities=["build"],
            max_concurrent=10,
        ),
        AgentCapability(
            agent_id="general-agent-001",
            capabilities=["review", "validate", "remediate"],
            max_concurrent=2,
        ),
    ]

    # Register all agents in GOVERNANCE identity layer
    for agent in agents:
        governance.identity.register(agent.agent_id, {
            "capabilities": agent.capabilities,
            "max_concurrent": agent.max_concurrent,
        })

    # Add dispatch security policies
    governance.security.add_policy({
        "name": "capability-scope-check",
        "check": lambda action: {
            "allowed": True,
            "reason": "Agent capability verified by dispatcher",
        },
    })

    # L02 + L03: Dispatch each work item
    assignments: list[dict] = []
    escalations: list[dict] = []

    while queue.size() > 0:
        item = queue.dequeue()
        if item is None:
            break

        assign_span = obs.tracer.start_span(
            f"assign-{item.id}",
            parent=root_span,
            attributes={"work_item.id": item.id, "work_item.type": item.type},
        )

        # HARNESS: Context — understand the work item
        assign_span.set_attribute("work_item.priority", item.priority)
        assign_span.set_attribute(
            "work_item.target_path",
            WORK_TYPE_TO_PATH.get(item.type, "unknown"),
        )

        # HARNESS: Capability — match agent to work
        matched_agent = _match_agent(item, agents)

        if matched_agent is None:
            # No agent available — escalate to human
            item.status = "escalated"
            escalations.append({
                "item_id": item.id,
                "type": item.type,
                "reason": "no-capable-agent-available",
            })
            obs.metrics.counter("dispatch_escalations", labels={"type": item.type})
            obs.logger.warn(
                "Work item escalated — no capable agent",
                item_id=item.id,
                work_type=item.type,
            )
            governance.observability.record({
                "agent_id": "dispatcher",
                "action": "escalated",
                "path": "/dispatch-work",
                "reason": f"No agent for {item.type}",
            })
            obs.tracer.end_span(assign_span, SpanStatus.ERROR)
            continue

        # GOVERNANCE: Wrap the assignment
        governed_result = await governance.wrap(
            matched_agent.agent_id,
            {"path": "/dispatch-work", "action": "accept-assignment"},
            lambda item=item, agent=matched_agent: _execute_assignment(
                item, agent, obs,
            ),
        )

        if governed_result.get("allowed"):
            assignment = governed_result.get("result", {})
            assignments.append(assignment)
            obs.metrics.counter("dispatch_assignments", labels={
                "type": item.type,
                "agent": matched_agent.agent_id,
            })
            obs.logger.info(
                "Work item assigned",
                item_id=item.id,
                agent_id=matched_agent.agent_id,
                target_path=WORK_TYPE_TO_PATH.get(item.type),
            )
            obs.tracer.end_span(assign_span, SpanStatus.OK)
        else:
            item.status = "escalated"
            escalations.append({
                "item_id": item.id,
                "type": item.type,
                "reason": governed_result.get("reason", "governance-denied"),
            })
            obs.metrics.counter("dispatch_governance_denials", labels={"type": item.type})
            obs.tracer.end_span(assign_span, SpanStatus.ERROR)

    # End root span
    obs.tracer.end_span(root_span, SpanStatus.OK)
    obs.metrics.histogram("dispatch_cycle_duration_ms", (time.time() - start) * 1000)
    obs.logger.info(
        "Dispatch cycle complete",
        assigned=len(assignments),
        escalated=len(escalations),
    )

    return {
        "path": "/dispatch-work",
        "maturity_level": "L2",
        "type": PathType.PROBABILISTIC,
        "layers": ["L01", "L02", "L03"],
        "triggered_by": "platform-event",
        "mode": "simulate" if simulate else "live",
        "dispatch": {
            "method": "capability-matched",
            "items_received": len(parsed_items),
            "items_assigned": len(assignments),
            "items_escalated": len(escalations),
            "assignments": assignments,
            "escalations": escalations,
        },
        "harness": "activated",
        "governance": {
            "identity": f"{len(agents)} agent(s) registered",
            "security": "1 policy checked (capability-scope)",
            "observability": governance.observability.get_metrics(),
        },
        "observability": {
            "spans": len(obs.tracer.get_spans()),
            "metrics": obs.metrics.export_json(),
            "logs": len(obs.logger.get_entries()),
        },
        "duration_ms": int((time.time() - start) * 1000),
        "summary": {
            "l01": f"Work queue processed {len(parsed_items)} item(s) by priority",
            "l02": "Path defined as probabilistic — capability-matched dispatch",
            "l03": (
                f"HARNESS: context loaded, {len(assignments)} assignment(s) matched. "
                f"GOVERNANCE: {len(agents)} agent(s) verified, policies enforced, "
                f"{len(escalations)} escalation(s)."
            ),
        },
    }


async def _execute_assignment(
    item: WorkItem,
    agent: AgentCapability,
    obs: ObservabilityStack,
) -> dict:
    """Execute a single work assignment."""
    item.assigned_to = agent.agent_id
    item.assigned_at = datetime.now(timezone.utc).isoformat()
    item.status = "assigned"
    agent.current_load += 1

    return {
        "action": "auto-approved",
        "item_id": item.id,
        "type": item.type,
        "assigned_to": agent.agent_id,
        "target_path": WORK_TYPE_TO_PATH.get(item.type, "unknown"),
        "priority": item.priority,
        "assigned_at": item.assigned_at,
        "agent_load_after": agent.current_load,
    }
