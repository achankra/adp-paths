#!/usr/bin/env python3
"""
ADP in Action — Demo Runner

Runs all three platform paths at L0/L1 and L2, side by side,
showing the structural differences in layer activation, HARNESS
engagement, and GOVERNANCE tracking.

Usage:
    python -m src.cli --simulate                              # All paths, local heuristics (default)
    python -m src.cli --live                                   # All paths, Claude API
    python -m src.cli --live --model claude-sonnet-4-20250514  # Specific model
    python -m src.cli --simulate ci-build                      # Single path
    python -m src.cli --simulate pr-review
    python -m src.cli --simulate validate-change

Environment:
    ANTHROPIC_API_KEY  — Required for --live mode
    ANTHROPIC_MODEL    — Optional model override (default: claude-sonnet-4-20250514)

PEH Reference: The Platform Engineer's Handbook (Chankramath, 2026)
Companion code: github.com/achankra/peh
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

from src.observability import ObservabilityStack
from src.paths import ci_build, dispatch_work, pr_review, validate_change

SAMPLE_DIR = Path(__file__).parent.parent / "sample" / "src"

# ── Terminal colors ──────────────────────────────────────────────

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"


def header(text: str):
    line = "═" * 68
    print(f"\n{CYAN}{line}{RESET}")
    print(f"{BOLD}{CYAN}  {text}{RESET}")
    print(f"{CYAN}{line}{RESET}")


def subheader(text: str):
    print(f"\n{BOLD}  {text}{RESET}")
    print(f"{DIM}  {'─' * 60}{RESET}")


def label(key: str, value: str):
    print(f"  {DIM}{key}:{RESET} {value}")


def layer_chip(layers: list[str]) -> str:
    chips = []
    for layer in layers:
        if layer == "L01":
            chips.append(f"{BLUE}[L01 Tooling]{RESET}")
        elif layer == "L02":
            chips.append(f"{MAGENTA}[L02 Paths]{RESET}")
        elif layer == "L03":
            chips.append(f"{YELLOW}[L03 Agents]{RESET}")
        else:
            chips.append(layer)
    return " ".join(chips)


def status_icon(passed: bool) -> str:
    return f"{GREEN}PASS{RESET}" if passed else f"{RED}FAIL{RESET}"


def print_pipeline(pipeline: dict | None):
    if not pipeline:
        return
    for stage in pipeline["stages"]:
        print(f"    {status_icon(stage['passed'])} {stage['name']} ({stage['tool']}) — {stage['output']}")


def print_summary(summary: dict):
    print(f"\n  {BOLD}Layer Summary:{RESET}")
    label("  L01 Tooling", summary["l01"])
    label("  L02 Paths  ", summary["l02"])
    label("  L03 Agents ", summary["l03"])


# ── Path demos ───────────────────────────────────────────────────

async def demo_ci_build(args):
    header("/ci-build — Deterministic Path")

    sample_files = [
        str(SAMPLE_DIR / "handler.py"),
        str(SAMPLE_DIR / "utils.py"),
    ]

    # L0-L1
    subheader("L0-L1: Human-driven")
    l01 = await ci_build.run_at_l01({"file_paths": sample_files})
    label("Type", str(l01["type"]))
    label("Layers", layer_chip(l01["layers"]))
    label("Triggered by", l01["triggered_by"])
    print(f"\n  {BOLD}Pipeline:{RESET}")
    print_pipeline(l01["pipeline"])
    label("HARNESS", "None")
    label("GOVERNANCE", "None")
    print_summary(l01["summary"])

    # L2
    subheader("L2: Agent era (pipeline unchanged)")
    l02 = await ci_build.run_at_l02({
        "file_paths": sample_files,
        "triggered_by": "agent-commit",
    })
    label("Type", str(l02["type"]))
    label("Layers", layer_chip(l02["layers"]))
    label("Triggered by", l02["triggered_by"])
    print(f"\n  {BOLD}Pipeline:{RESET}")
    print_pipeline(l02["pipeline"])
    label("HARNESS", "None — deterministic path")
    label("GOVERNANCE", "None — deterministic path")
    print_summary(l02["summary"])


async def demo_pr_review(args):
    header("/pr-review — Probabilistic Path (at L2)")

    sample_files = [
        str(SAMPLE_DIR / "handler.py"),
        str(SAMPLE_DIR / "utils.py"),
    ]

    # L0-L1
    subheader("L0-L1: Human-driven review")
    l01 = await pr_review.run_at_l01({
        "files": sample_files,
        "lines_changed": 42,
        "obvious": False,
    })
    label("Reviewer", l01["review"]["reviewer"])
    label("Method", l01["review"]["method"])
    label("Context loaded", str(l01["review"]["context_loaded"]))
    label("Evidence trail", str(l01["review"]["evidence_trail"]))
    label("Time to review", l01["review"]["time_to_review"])
    label("Layers", layer_chip(l01["layers"]))
    label("HARNESS", "None")
    label("GOVERNANCE", "None")
    print_summary(l01["summary"])

    # L2
    mode_label = "simulate" if args.simulate else "live"
    subheader(f"L2: Agent-driven review ({mode_label})")
    l02 = await pr_review.run_at_l02(
        {
            "file_paths": sample_files,
            "lines_changed": 42,
            "change_type": "routine",
            "repository": "platform-api",
            "team": "platform",
        },
        {"simulate": args.simulate, "model": args.model},
    )
    label("Reviewer", l02["review"]["reviewer"])
    label("Method", l02["review"]["method"])
    label("Mode", l02["mode"])
    label("Context loaded", str(l02["review"]["context_loaded"]))
    label("Evidence trail", str(l02["review"]["evidence_trail"]))
    label("Categories", ", ".join(l02["review"]["categories"]))
    label("Recommendation", l02["review"]["recommendation"])
    label("Type", str(l02["type"]))
    label("Layers", layer_chip(l02["layers"]))

    print(f"\n  {BOLD}HARNESS:{RESET}")
    if l02["harness"]:
        ctx = l02["harness"]["context"]
        cap = l02["harness"]["capability"]
        exc = l02["harness"]["execution"]
        evl = l02["harness"]["evaluation"]
        label("  Context", f"Retrieved from {len(ctx['retrieved'])} source(s)")
        label("  Capability", f"Model: {cap['model']}, Strategy: {cap['strategy']}")
        label("  Execution", f"Mode: {exc['mode']}, Duration: {exc['duration_ms']}ms")
        label("  Evaluation", evl["action"])

    print(f"\n  {BOLD}GOVERNANCE:{RESET}")
    if l02["governance"]:
        label("  Identity", "Verified" if l02["governance"]["identity"]["verified"] else "FAILED")
        label("  Security", f"{l02['governance']['security']['policies_checked']} policies checked")
        label("  Observability", f"{l02['governance']['observability']['total_executions']} event(s) recorded")

    if l02["review"].get("findings"):
        print(f"\n  {BOLD}Findings:{RESET}")
        for f in l02["review"]["findings"]:
            severity = f.get("severity", "info")
            color = RED if severity == "critical" else YELLOW if severity in ("error", "warning") else DIM
            findings_str = ", ".join(f.get("findings", []))
            print(f"    {color}[{severity}]{RESET} {f.get('category', 'general')}: {findings_str}")

    print_summary(l02["summary"])


async def demo_validate_change(args):
    header("/validate-change — Hybrid Path (at L2)")

    sample_files = [
        str(SAMPLE_DIR / "handler.py"),
        str(SAMPLE_DIR / "utils.py"),
    ]

    # L0-L1
    subheader("L0-L1: Single gate")
    l01 = await validate_change.run_at_l01({"file_paths": sample_files})
    label("Type", str(l01["type"]))
    label("Layers", layer_chip(l01["layers"]))
    label("Passed", str(l01["pipeline"]["passed"]))
    print(f"\n  {BOLD}Pipeline:{RESET}")
    print_pipeline(l01["pipeline"])
    label("Loop", "None — human reads output and fixes manually")
    label("HARNESS", "None")
    label("GOVERNANCE", "None")
    print_summary(l01["summary"])

    # L2
    mode_label = "simulate" if args.simulate else "live"
    subheader(f"L2: Agent + gate feedback loop ({mode_label})")
    l02 = await validate_change.run_at_l02(
        {"file_paths": sample_files},
        {"max_retries": 3, "simulate": args.simulate, "model": args.model},
    )
    label("Type", str(l02["type"]))
    label("Mode", l02["mode"])
    label("Layers", layer_chip(l02["layers"]))
    label("Status", l02["result"]["status"])
    label("Attempts", str(l02["attempts"]))
    label("Resolved by", l02["result"]["resolved_by"])

    print(f"\n  {BOLD}Feedback Loop Trace:{RESET}")
    for entry in l02["loop"]:
        icon = f"{GREEN}PASS" if entry["outcome"] == "passed" else f"{YELLOW}RETRY"
        gate = "Gate passed" if entry["pipeline"]["passed"] else "Gate failed"
        print(f"    {icon}{RESET} Attempt {entry['attempt']}: {gate}")
        if entry.get("fix"):
            targets = ", ".join(entry["fix"]["targets"]) or "none"
            print(f"      {DIM}Fix: {entry['fix']['fix_type']} — targets: {targets}{RESET}")

    print(f"\n  {BOLD}GOVERNANCE:{RESET}")
    if l02["governance"]:
        label("  Events recorded", str(l02["governance"]["observability"]["total_executions"]))
        label("  Audit trail", f"{len(l02['governance']['audit_trail'])} entries")
    print_summary(l02["summary"])


async def demo_dispatch_work(args):
    header("/dispatch-work — Dispatch Path (L2 only)")

    work_items = [
        {"id": "work-001", "type": "review", "priority": "high",
         "source": {"trigger": "pr-opened", "repo": "platform-api"}},
        {"id": "work-002", "type": "validate", "priority": "critical",
         "source": {"trigger": "commit-pushed", "repo": "platform-api"}},
        {"id": "work-003", "type": "build", "priority": "medium",
         "source": {"trigger": "scheduled", "repo": "platform-api"}},
        {"id": "work-004", "type": "review", "priority": "low",
         "source": {"trigger": "pr-opened", "repo": "platform-utils"}},
        {"id": "work-005", "type": "remediate", "priority": "high",
         "source": {"trigger": "alert-fired", "repo": "platform-api"}},
    ]

    # L0-L1
    subheader("L0-L1: Human-driven (no dispatch)")
    l01 = await dispatch_work.run_at_l01(work_items)
    label("Path", l01["path"])
    label("Maturity", l01["maturity_level"])
    label("Type", l01["type"])
    label("Layers", layer_chip(l01["layers"]))
    label("Triggered by", l01["triggered_by"])
    label("Queue size", str(l01["dispatch"]["queue_size"]))
    label("Queue by priority", str(l01["dispatch"]["queue_by_priority"]))
    label("Items assigned", str(l01["dispatch"]["items_assigned"]))
    label("Assignment method", l01["dispatch"]["assignment_method"])
    label("HARNESS", "None")
    label("GOVERNANCE", "None")
    print_summary(l01["summary"])

    # L2
    mode_label = "simulate" if args.simulate else "live"
    subheader(f"L2: Agent dispatch ({mode_label})")
    l02 = await dispatch_work.run_at_l02(
        work_items,
        {"simulate": args.simulate, "model": args.model},
    )
    label("Path", l02["path"])
    label("Maturity", l02["maturity_level"])
    label("Type", str(l02["type"]))
    label("Mode", l02["mode"])
    label("Layers", layer_chip(l02["layers"]))
    label("Triggered by", l02["triggered_by"])
    label("Items received", str(l02["dispatch"]["items_received"]))
    label("Items assigned", str(l02["dispatch"]["items_assigned"]))
    label("Items escalated", str(l02["dispatch"]["items_escalated"]))
    label("Dispatch method", l02["dispatch"]["method"])

    if l02["dispatch"]["assignments"]:
        print(f"\n  {BOLD}Assignments:{RESET}")
        for a in l02["dispatch"]["assignments"]:
            path_target = a.get("target_path", "unknown")
            print(f"    {GREEN}ASSIGNED{RESET} {a['item_id']} ({a['type']}) → {a['assigned_to']} → {path_target}")

    if l02["dispatch"]["escalations"]:
        print(f"\n  {BOLD}Escalations:{RESET}")
        for e in l02["dispatch"]["escalations"]:
            print(f"    {YELLOW}ESCALATED{RESET} {e['item_id']} ({e['type']}) — {e['reason']}")

    print(f"\n  {BOLD}GOVERNANCE:{RESET}")
    if l02["governance"]:
        label("  Identity", l02["governance"]["identity"])
        label("  Security", l02["governance"]["security"])
        gov_obs = l02["governance"]["observability"]
        label("  Observability", f"{gov_obs['total_executions']} event(s) recorded")

    print(f"\n  {BOLD}Observability:{RESET}")
    if l02["observability"]:
        label("  Spans", str(l02["observability"]["spans"]))
        label("  Log entries", str(l02["observability"]["logs"]))

    label("Duration", f"{l02['duration_ms']}ms")
    print_summary(l02["summary"])


# ── Main ─────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="ADP in Action — L0/L1 to L2/L3 Transition Demo",
    )
    parser.add_argument(
        "path",
        nargs="?",
        choices=["ci-build", "pr-review", "validate-change", "dispatch-work"],
        help="Run a specific path (default: all paths)",
    )
    parser.add_argument(
        "--simulate",
        action="store_true",
        default=True,
        help="Use local heuristic analysis (default)",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Use Claude API for agent operations",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Anthropic model name (default: claude-sonnet-4-20250514)",
    )
    parser.add_argument(
        "--export-telemetry",
        type=str,
        default=None,
        metavar="DIR",
        help="Export observability data (traces, metrics, logs) to the specified directory",
    )

    args = parser.parse_args()

    if args.live:
        args.simulate = False
        if not os.environ.get("ANTHROPIC_API_KEY"):
            print(f"{RED}Error: --live mode requires ANTHROPIC_API_KEY environment variable.{RESET}")
            print("  Set it with: export ANTHROPIC_API_KEY=sk-ant-...")
            print("  Or use --simulate mode (default).")
            sys.exit(1)

    # Banner
    print(f"{BOLD}{CYAN}")
    print("  ╔══════════════════════════════════════════════════════════════╗")
    print("  ║                    ADP in Action                            ║")
    print("  ║  From IDP to ADP — L0/L1 to L2/L3 Transition Demo          ║")
    print("  ╚══════════════════════════════════════════════════════════════╝")
    print(f"{RESET}")
    mode = "simulate (local heuristics)" if args.simulate else f"live (Claude API: {args.model or 'claude-sonnet-4-20250514'})"
    print(f"{DIM}  Three-Layer Architecture: L01 Tooling | L02 Paths | L03 Agents")
    print(f"  Mode: {mode}")
    print("  Reference: The Platform Engineer's Handbook (Chankramath, 2026)")
    print(f"  Companion: github.com/achankra/peh{RESET}")

    runners = {
        "ci-build": demo_ci_build,
        "pr-review": demo_pr_review,
        "validate-change": demo_validate_change,
        "dispatch-work": demo_dispatch_work,
    }

    async def run():
        if args.path:
            await runners[args.path](args)
        else:
            for runner in runners.values():
                await runner(args)

        # Export telemetry if requested
        if args.export_telemetry:
            obs = ObservabilityStack(service_name="adp-demo")
            obs.logger.info("Demo run completed", mode=mode, path=args.path or "all")
            obs.export_all(args.export_telemetry)
            print(f"\n  {GREEN}{BOLD}Telemetry exported to: {args.export_telemetry}/{RESET}")
            print("    traces.json, metrics.json, logs.json, prometheus.txt")

    asyncio.run(run())

    print()


if __name__ == "__main__":
    main()
