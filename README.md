# ADP in Action

**From Internal Developer Platforms to Agentic Developer Platforms**

This codebase demonstrates how platform paths transition from L0/L1 (human-driven) to L2/L3 (agent-driven) in a three-layer Agentic Developer Platform architecture. It is the companion implementation to the *ADP in Action* technical paper.

---

## What This Shows

Four platform paths, each implemented at two maturity levels:

| Path | Type at L2 | L0-L1 Behavior | L2 Behavior |
|------|-----------|----------------|-------------|
| `/ci-build` | Deterministic | Human triggers pipeline | Same pipeline, agent may author the code |
| `/pr-review` | Probabilistic | Human reads diff manually | Agent generates structured review with HARNESS |
| `/validate-change` | Hybrid | Single gate, human fixes | Agent + gate feedback loop with retry limit |
| `/dispatch-work` | Probabilistic | Human picks from backlog | Platform dispatches work to agents by capability |

The key structural insight: **deterministic paths stay on L01 at every maturity level.** Only probabilistic and hybrid paths activate L02 (path definitions) and L03 (agent infrastructure). Dispatch Work is a *new* path at L2 — it does not exist at L0-L1.

---

## Three-Layer Architecture

```
L03  Agent Infrastructure    HARNESS (Context, Capability, Execution, Evaluation)
     (only for agent paths)  GOVERNANCE (Identity, Security, Observability)
     ─────────────────────────────────────────────────────────────────────────
L02  Path Definitions        8 paths to outcomes, each typed as:
                             deterministic | probabilistic | hybrid
     ─────────────────────────────────────────────────────────────────────────
L01  Tooling (IDP)           CI pipelines, GitOps, observability (traces,
                             metrics, logs), identity, policy-as-code.
                             Does not change when agents arrive.
```

GOVERNANCE.Observability (L03) bridges to L01 observability infrastructure — agent events emit to the same traces, metrics, and structured logs that pipelines use.

For the L01 foundation -- Kubernetes runtime, GitOps, CI/CD pipelines, observability, policy-as-code -- see [*The Platform Engineer's Handbook*](https://peh-packt.platformetrics.com/) (Chankramath, Packt, 2026, ISBN 978-1-80638-013-8) and the companion repository at [github.com/achankra/peh](https://github.com/achankra/peh).

---

## Tech Stack

Every tool in the L01 deterministic layer is real -- not simulated. The linter runs real Ruff via subprocess, the build gate runs real `ast.parse`, the security scanner runs real regex pattern matching against actual file content. An optional `--live` mode connects to the Anthropic API for agent-driven paths.

| Technology | Version | Role in ADP | Layer |
|------------|---------|-------------|-------|
| **Python** | 3.11+ | Runtime. `asyncio` for async pipeline execution, `ast` for code analysis, `importlib.util` for dynamic module loading, `secrets` for ID generation. | All |
| **Ruff** | 0.4+ | L01 linter and formatter. Called via `subprocess` -- same binary your CI pipeline runs. Rules: E, W, F, I, S, B, SIM, UP. Also used as the deterministic gate in `/validate-change`. | L01 |
| **pytest** | 8.0+ | Test framework. 53 tests covering tools, layers, HARNESS, GOVERNANCE, and all three paths at both maturity levels. `pytest-asyncio` for async test support. | Testing |
| **anthropic** | 0.39+ | *(Optional)* Claude API SDK for `--live` mode. Provides model-backed PR review and fix generation. Not required -- `--simulate` mode uses local heuristics with zero external calls. | L03 |
| **ast** | stdlib | Build verification. Parses source files to extract public exports and detect syntax errors. The "can it compile?" gate. | L01 |
| **re** | stdlib | Security scanning. Pattern-based detection of `eval()`, `exec()`, `shell=True`, hardcoded secrets, `os.system()`, `pickle.loads()`, and other anti-patterns. | L01 |
| **argparse** | stdlib | CLI interface. `--simulate` (default) / `--live` mode selection, `--model` override, optional path argument. | CLI |

---

## Installation

### Prerequisites

Python 3.11 or later. Verify with:

```bash
python3 --version
```

### Install for development (simulate mode)

```bash
# Clone and enter the project
cd adp_paths

# Install with dev dependencies (Ruff + pytest)
pip install -e ".[dev]"
```

### Install with Claude API support (live mode)

```bash
# Install everything including the anthropic SDK
pip install -e ".[all]"
```

### Install dependencies only (no editable install)

```bash
pip install -r requirements.txt
```

---

## Usage

### Simulate mode (default, no API key needed)

Runs all three paths using local heuristics — real Ruff linting, real `ast`-based code analysis, real security scanning. No external API calls.

```bash
# Run the full demo (all three paths, L0-L1 then L2)
python -m src.cli --simulate

# Run a single path
python -m src.cli --simulate ci-build
python -m src.cli --simulate pr-review
python -m src.cli --simulate validate-change
python -m src.cli --simulate dispatch-work
```

### Live mode (requires Anthropic API key)

Uses Claude to generate PR reviews and code fixes. Set your API key first:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."

# Run with default model (claude-sonnet-4-20250514)
python -m src.cli --live

# Run with a specific model
python -m src.cli --live --model claude-sonnet-4-20250514

# Run a single path in live mode
python -m src.cli --live pr-review
```

### Using the entry point

If installed with `pip install -e .`, the `adp-demo` command is available:

```bash
adp-demo --simulate
adp-demo --live --model claude-sonnet-4-20250514
```

---

## How the Anthropic Integration Works

In `--simulate` mode, no API calls are made. The HARNESS execution component uses local heuristics — `ast.parse` to analyze source files, pattern matching to detect issues, Ruff `--fix` for auto-repairs. This is the default and requires no API key.

In `--live` mode, the codebase uses the `anthropic` Python SDK to call Claude at two points in the agent-driven paths:

**`/pr-review` (probabilistic path):** The HARNESS Context component gathers real file content, then the Execution component sends it to Claude with a structured prompt. Claude returns a JSON review with categories (style, correctness, security), findings, and a recommendation. The HARNESS Evaluation component then assesses the result (approve, request-changes, or pending-human-review based on confidence).

**`/validate-change` (hybrid path):** When the deterministic gate fails, the HARNESS sends the structured failure signals (lint errors, security findings) to Claude along with the source file. Claude generates a fix. The fix is written to the working copy, and the deterministic gate runs again. This loop continues until the gate passes or the retry limit is reached.

The default model is `claude-sonnet-4-20250514`. Override with `--model`:

```bash
python -m src.cli --live --model claude-sonnet-4-20250514
```

You can also set `ANTHROPIC_MODEL` as an environment variable. The model selection is handled by the HARNESS Capability component, which can vary the model based on change type (security-sensitive changes may warrant a different strategy).

The GOVERNANCE layer is identical in both modes — identity verification, policy enforcement, and observability recording wrap every agent action regardless of whether the execution is simulated or live.

---

## Observability

The codebase includes a full L01 observability infrastructure (`src/observability.py`) with three pillars:

- **Traces** — OpenTelemetry-compatible spans with parent-child relationships. Each pipeline run is a trace, each stage is a child span. Each dispatch cycle is a trace, each assignment is a span.
- **Metrics** — Prometheus-compatible counters, gauges, and histograms. Pipeline pass/fail rates, dispatch assignment counts, governance event tallies, cycle duration.
- **Structured Logs** — JSON event log entries with severity, message, timestamp, and arbitrary context fields.

GOVERNANCE.Observability (L03) emits to this L01 infrastructure when an ObservabilityStack is provided, bridging agent-level events to the same telemetry fabric that pipelines use.

### Exporting Telemetry

```bash
python -m src.cli --simulate --export-telemetry ./telemetry
```

This writes four files: `traces.json`, `metrics.json`, `logs.json`, and `prometheus.txt`.

### Grafana Dashboard

A pre-configured Grafana + Prometheus stack is provided in `grafana/`:

```bash
cd grafana
docker-compose up -d
# Open http://localhost:3000 (admin/admin)
```

The dashboard has three sections mapped to the three-layer architecture: L01 Pipeline Telemetry, L02 Dispatch Work, and L03 GOVERNANCE Events. See `grafana/README.md` for details.

---

## Project Structure

```
adp_paths/
├── pyproject.toml              # Project config, author, dependencies, entry points
├── requirements.txt            # Flat dependency list
├── ruff.toml                   # Ruff linter rules (same config the pipeline enforces)
├── README.md
├── src/
│   ├── __init__.py
│   ├── __main__.py             # Package entry point (python -m src.cli)
│   ├── cli.py                  # CLI runner — argparse, ANSI output, asyncio.run()
│   ├── tools.py                # L01 deterministic tools (Ruff, test runner, build, security)
│   ├── layers.py               # Three-layer architecture (L01, L02, L03)
│   ├── harness.py              # HARNESS: Context, Capability, Execution, Evaluation
│   ├── governance.py           # GOVERNANCE: Identity, Security, Observability
│   ├── observability.py        # L01 observability: traces, metrics, structured logs
│   └── paths/
│       ├── __init__.py
│       ├── ci_build.py         # Deterministic — stays on L01
│       ├── pr_review.py        # Probabilistic — activates L02 + L03 at L2
│       ├── validate_change.py  # Hybrid — agent + gate loop at L2
│       └── dispatch_work.py    # Dispatch — NEW at L2, assigns work to agents
├── sample/
│   └── src/
│       ├── __init__.py
│       ├── handler.py          # Platform API handler (the code pipelines operate on)
│       └── utils.py            # Platform utilities (validation, formatting, sanitization)
├── grafana/
│   ├── docker-compose.yml      # Grafana + Prometheus stack
│   ├── prometheus.yml          # Prometheus scrape config
│   ├── README.md               # Grafana setup instructions
│   ├── dashboards/
│   │   └── adp-dashboard.json  # Pre-configured ADP observability dashboard
│   └── provisioning/           # Auto-provisioned datasources and dashboard config
└── tests/
    ├── __init__.py
    ├── test_tools.py           # 12 tests — lint, test runner, build, security scan
    ├── test_governance.py      # 12 tests — identity, security policies, observability, wrap
    ├── test_harness.py         # 13 tests — context, capability, execution, evaluation, flow
    ├── test_observability.py   # 26 tests — spans, tracer, metrics, logger, stack
    └── test_paths.py           # 24 tests — ci-build, pr-review, validate-change, dispatch-work
```

---

## Running Tests

```bash
# Run all 87 tests
pytest

# Run with verbose output
pytest -v

# Run a specific test file
pytest tests/test_tools.py
pytest tests/test_harness.py
pytest tests/test_governance.py
pytest tests/test_paths.py
```

---

## Linting

```bash
# Check for lint errors
ruff check src/ tests/ sample/

# Auto-fix fixable issues
ruff check --fix src/ tests/ sample/

# Format code
ruff format src/ tests/ sample/
```

Ruff configuration is in `ruff.toml`. Target version is Python 3.11, line length is 100. Rules include pyflakes (F), pycodestyle (E, W), isort (I), bandit security (S), bugbear (B), simplify (SIM), and pyupgrade (UP).

---

## What the Tests Verify

**`/ci-build` (deterministic):** Same input produces the same pipeline result at L0-L1 and L2. Only L01 activates. No HARNESS, no GOVERNANCE. The deterministic invariant holds across maturity levels.

**`/pr-review` (probabilistic):** L0-L1 is manual-only (no context, no evidence trail). L2 engages full HARNESS (four components) and GOVERNANCE (identity, security, observability). Agent does not merge.

**`/validate-change` (hybrid):** L0-L1 is a single gate. L2 loops on failure with agent-generated fixes. Retry limit is enforced. Exhaustion triggers human escalation. The deterministic gate (L01 pipeline) is unchanged between levels.

**`/dispatch-work` (dispatch):** Does not exist at L0-L1 (humans pick from backlog, no dispatch logic). At L2, work items are queued by priority, matched to agents by capability, assigned with GOVERNANCE wrapping, and escalated when no capable agent is available. Priority ordering is verified (critical items dispatch first).

**Observability:** Spans nest correctly (parent-child trace trees). Metrics increment and export in Prometheus text format. Structured logs filter by level and include context fields. The ObservabilityStack exports all three formats to disk.

---

## PEH Chapter Mapping

For the L01 foundation -- Kubernetes runtime, GitOps, CI/CD pipelines, observability, policy-as-code -- see *The Platform Engineer's Handbook* and the companion repository at [github.com/achankra/peh](https://github.com/achankra/peh). The following chapters map directly to ADP layers:

| ADP Layer | PEH Chapters | What They Build |
|-----------|-------------|-----------------|
| L01 Tooling | Ch 1: Laying the Groundwork | Repository topology, CI, testing, security principles |
| | Ch 2: Scalable Platform Runtime | Kubernetes, service mesh, GitOps, deployment pipelines |
| | Ch 3: Securing Platform Access | OAuth, RBAC, policy-as-code with OPA |
| | Ch 4: Embedding Observability | Metrics, logs, traces, OpenTelemetry, SLOs |
| | Ch 8: CI/CD as a Platform Service | Pipeline playbooks, reusable workflows, golden paths |
| | Ch 9: Self-Service Infrastructure | Infrastructure blueprints, governance with guardrails |
| | Ch 11: Compliance and Policy as Code | Admission controllers, OPA, compliance dashboards |
| L02 Paths | Ch 8, Ch 10 | Golden paths, pipeline templates, starter kits |
| L03 Agents | Ch 14: Agentic and AI-Augmented Platforms | Agent design, governance, patterns and antipatterns |

### Module-to-Chapter Mapping

Every module in the codebase includes PEH chapter references in its docstring and inline comments. The code style follows the conventions in the PEH companion repository at [github.com/achankra/peh](https://github.com/achankra/peh).

| Module | PEH Chapters | Companion Path |
|--------|-------------|----------------|
| `tools.py` | Ch 3, 8, 11 | `ch08/pipeline.py`, `ch03/security_scanner.py` |
| `layers.py` | Ch 1, 2, 8, 9, 10, 14 | `ch08/`, `ch14/layers.py` |
| `harness.py` | Ch 14 | `ch14/harness.py` |
| `governance.py` | Ch 3, 4, 11, 14 | `ch03/identity.py`, `ch14/governance.py` |
| `observability.py` | Ch 4, 14 | `ch04/observability.py`, `ch04/tracer.py` |
| `paths/ci_build.py` | Ch 8 | `ch08/ci_build.py` |
| `paths/pr_review.py` | Ch 14 | `ch14/pr_review.py` |
| `paths/validate_change.py` | Ch 4, 11, 13 | `ch04/observability.py`, `ch13/feedback_loop.py` |
| `paths/dispatch_work.py` | Ch 8, 10, 14 | `ch14/dispatch.py`, `ch08/work_queue.py` |
| `sample/src/handler.py` | Ch 5 | `ch05/handler.py` |
| `sample/src/utils.py` | Ch 3 | `ch03/utils.py` |

---

## References

1. *[The Four Levels of Agentic Software Development in the Enterprise](https://weaveintelligence.io/research/the-four-levels-of-agentic-software-development-in-the-enterprise).* Weave Intelligence, 2025.
2. *[From IDP to ADP: Why Platform Engineers Now Build Agentic Development Platforms](https://weaveintelligence.io/blog/from-idp-to-adp).* Weave Intelligence, 2025.
3. Chankramath, A. *The Platform Engineer's Handbook.* Packt, 2026. ISBN 978-1-80638-013-8. [Book website](https://peh-packt.platformetrics.com/) · [Amazon](https://www.amazon.com/Platform-Engineers-Handbook-developer-focused-streamline-ebook/dp/B0FR59Z7Q2/)
4. Companion repository: [github.com/achankra/peh](https://github.com/achankra/peh)

---

## Author

**Ajay Chankramath** — ajay@platformengineering.org

CTO, Platform Engineering Advisory | PlatformEngineering.org

---

## License

MIT
