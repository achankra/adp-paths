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
| `/iterative-refactor` | Hybrid | Single gate, human fixes | Agent + gate feedback loop with retry limit |
| `/dispatch-work` | Probabilistic | Human picks from backlog | Platform dispatches work to agents by capability |

The key structural insight: **deterministic paths stay on L01 at every maturity level.** Only probabilistic and hybrid paths activate L02 (path definitions) and L03 (agent infrastructure). Dispatch Work is a *new* path at L2 — it does not exist at L0-L1.

---

## Reading the Paper Alongside This Repo

This codebase is the companion to the *ADP in Action* paper. If you arrived from
the paper, this is how its concepts land in code:

| In the paper | In this repo |
|---|---|
| Figure-1: three layers (Tooling / Path Definitions / Agent Infrastructure) | `src/layers.py` (L01), `src/paths/` (L02), `src/harness.py` + `src/governance.py` (L03) |
| Listing 1 — `/ci-build`, deterministic | `src/paths/ci_build.py` (`run_at_l01` / `run_at_l02`) |
| Listing 2 — `/pr-review`, probabilistic | `src/paths/pr_review.py` |
| Listing 3 — `/iterative-refactor`, hybrid | `src/paths/iterative_refactor.py` → `src/paths/validate_change.py` |
| "What changes at each maturity level" table | every path exposes `run_at_l01()` (maturity L0-L1) and `run_at_l02()` (maturity L2) |
| Harness (context, capability, execution, evaluation) | `src/harness.py` |
| Governance (identity, security, observability) | `src/governance.py`, `src/observability.py` |
| The feedback-loop metrics (override rate, fix-on-first-attempt) | `Governance.observability.get_metrics()`, plus `resolved_by` in loop results |
| "Running the Code" section | `python3 -m src.cli --simulate --path iterative-refactor` (add `--step` to pace the output) |

Two scope notes the paper implies but the code makes explicit:

- **Paths.** The paper defines nine lifecycle paths. This repo implements four
  platform commands that demonstrate the three path types across those
  lifecycle paths: `/ci-build` (deterministic), `/pr-review` (probabilistic),
  `/iterative-refactor` (hybrid), and `/dispatch-work` (the path that is new at
  L2). Retrieve Context appears as the Harness Context component rather than a
  standalone command; deploy, observe, remediate, and secure are out of scope
  for the demo.
- **Models.** The paper's third Agent Infrastructure component (providers,
  inference endpoints, model hosting) appears here only as model selection in
  the Harness Capability component (`--model` / `ANTHROPIC_MODEL`). Full model
  provisioning is platform-specific and out of scope for the demo.

---

## Three-Layer Architecture

```
L03  Agent Infrastructure    HARNESS (Context, Capability, Execution, Evaluation)
     (only for agent paths)  GOVERNANCE (Identity, Security, Observability)
     ─────────────────────────────────────────────────────────────────────────
L02  Path Definitions        9 paths to outcomes, each typed as:
                             deterministic | probabilistic | hybrid
     ─────────────────────────────────────────────────────────────────────────
L01  Tooling (IDP)           CI pipelines, GitOps, observability (traces,
                             metrics, logs), identity, policy-as-code.
                             Does not change when agents arrive.
```

GOVERNANCE.Observability (L03) bridges to L01 observability infrastructure — agent events emit to the same traces, metrics, and structured logs that pipelines use.


---

## Tech Stack

Every tool in the L01 deterministic layer is real -- not simulated. The linter runs real Ruff via subprocess, the build gate runs real `ast.parse`, the security scanner runs real regex pattern matching against actual file content. An optional `--live` mode connects to the Anthropic API for agent-driven paths.

| Technology | Version | Role in ADP | Layer |
|------------|---------|-------------|-------|
| **Python** | 3.11+ | Runtime. `asyncio` for async pipeline execution, `ast` for code analysis, `importlib.util` for dynamic module loading, `secrets` for ID generation. | All |
| **Ruff** | 0.4+ | L01 linter and formatter. Called via `subprocess` -- same binary your CI pipeline runs. Rules: E, W, F, I, S, B, SIM, UP. Also used as the deterministic gate in `/validate-change`. | L01 |
| **pytest** | 8.0+ | Test framework. 92 tests covering tools, layers, HARNESS, GOVERNANCE, observability, metrics server, and all four paths at both maturity levels. `pytest-asyncio` for async test support. | Testing |
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
python3 -m pip install -e ".[dev]"
```

### Install with Claude API support (live mode)

```bash
# Install everything including the anthropic SDK
python3 -m pip install -e ".[all]"
```

### Install dependencies only (no editable install)

```bash
python3 -m pip install -r requirements.txt
```

---

## Usage

### Simulate mode (default, no API key needed)

Runs all three paths using local heuristics — real Ruff linting, real `ast`-based code analysis, real security scanning. No external API calls.

```bash
# Run the full demo (all four paths, L0-L1 then L2)
python3 -m src.cli --simulate

# Run a single path
python3 -m src.cli --simulate ci-build
python3 -m src.cli --simulate pr-review
python3 -m src.cli --simulate iterative-refactor
python3 -m src.cli --simulate dispatch-work

# The path can also be passed as a flag (equivalent to the positional form)
python3 -m src.cli --simulate --path iterative-refactor

# Demo pacing: pause for Enter between output sections instead of scrolling past
python3 -m src.cli --simulate --step iterative-refactor
```

### The seeded defect (why the refactor demo loops)

`sample/src/refactor_target.py` ships with intentional, auto-fixable lint
defects (unused imports, unsorted import block). This is deliberate: it makes
the `/iterative-refactor` demo genuinely loop. At L0-L1 the gate fails and a
human would have to fix it manually. At L2, attempt 1 fails the gate, the
agent applies a fix (Ruff `--fix` in simulate mode, Claude in live mode), and
attempt 2 passes. Do not clean the file up — its defects are the demo. Restore
it any time with `git checkout -- sample/`.

### Live mode (requires Anthropic API key)

Uses Claude to generate PR reviews and code fixes. Set your API key first:

```bash
export ANTHROPIC_API_KEY="sk-ant-..."

# Run with default model (claude-sonnet-4-5)
python3 -m src.cli --live

# Run with a specific model
python3 -m src.cli --live --model claude-sonnet-4-5

# Run a single path in live mode
python3 -m src.cli --live pr-review
```

### Using the entry point

If installed with `python3 -m pip install -e .`, the `adp-demo` command is available:

```bash
adp-demo --simulate
adp-demo --live --model claude-sonnet-4-5
```

---

## How the Anthropic Integration Works

In `--simulate` mode, no API calls are made. The HARNESS execution component uses local heuristics — `ast.parse` to analyze source files, pattern matching to detect issues, Ruff `--fix` for auto-repairs. This is the default and requires no API key.

In `--live` mode, the codebase uses the `anthropic` Python SDK to call Claude at two points in the agent-driven paths:

**`/pr-review` (probabilistic path):** The HARNESS Context component gathers real file content, then the Execution component sends it to Claude with a structured prompt. Claude returns a JSON review with categories (style, correctness, security), findings, and a recommendation. The HARNESS Evaluation component then assesses the result (approve, request-changes, or pending-human-review based on confidence).

**`/iterative-refactor` (hybrid path):** When the deterministic gate fails, the HARNESS sends the structured failure signals (lint errors, security findings) to Claude along with the source file. Claude generates a fix. The fix is written to the working copy, and the deterministic gate runs again. This loop continues until the gate passes or the retry limit is reached.

The default model is `claude-sonnet-4-5`. Override with `--model`:

```bash
python3 -m src.cli --live --model claude-sonnet-4-5
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

### Live Metrics Server

Run with `--serve-metrics` to start an HTTP server that exposes a Prometheus-compatible `/metrics` endpoint:

```bash
python3 -m src.cli --simulate --serve-metrics
python3 -m src.cli --simulate --serve-metrics --metrics-port 9090
```

The server runs in a background thread. After all demos complete, it stays alive for Prometheus scraping until you press Ctrl+C.

### Exporting Telemetry

```bash
python3 -m src.cli --simulate --export-telemetry ./telemetry
```

This writes four files: `traces.json`, `metrics.json`, `logs.json`, and `prometheus.txt`.

### Grafana Dashboard

A pre-configured Grafana + Prometheus stack is provided in `grafana/`. Two options:

**Homebrew (macOS, no Docker required):**

```bash
brew install grafana prometheus
prometheus --config.file=grafana/prometheus.yml &
brew services start grafana
# Open http://localhost:3000 (admin/admin)
# Add Prometheus data source (http://localhost:9090)
# Import grafana/dashboards/adp-dashboard.json
```

**Docker Compose:**

```bash
cd grafana
docker compose up -d
# Open http://localhost:3000 (admin/admin) — dashboard auto-provisioned
```

The dashboard has three sections mapped to the three-layer architecture: L01 Pipeline Telemetry, L02 Dispatch Work, and L03 GOVERNANCE Events. See `grafana/README.md` for details.

---

## Project Structure

```
adp_paths/
├── LICENSE                     # MIT
├── pyproject.toml              # Project config, author, dependencies, entry points
├── requirements.txt            # Flat dependency list
├── ruff.toml                   # Ruff linter rules (same config the pipeline enforces)
├── README.md
├── src/
│   ├── __init__.py
│   ├── __main__.py             # Package entry point (python3 -m src.cli)
│   ├── cli.py                  # CLI runner — argparse, ANSI output, asyncio.run()
│   ├── tools.py                # L01 deterministic tools (Ruff, test runner, build, security)
│   ├── layers.py               # Three-layer architecture (L01, L02, L03)
│   ├── harness.py              # HARNESS: Context, Capability, Execution, Evaluation
│   ├── governance.py           # GOVERNANCE: Identity, Security, Observability
│   ├── observability.py        # L01 observability: traces, metrics, structured logs
│   ├── metrics_server.py       # HTTP metrics server (Prometheus /metrics endpoint)
│   └── paths/
│       ├── __init__.py
│       ├── ci_build.py         # Deterministic — stays on L01
│       ├── pr_review.py        # Probabilistic — activates L02 + L03 at L2
│       ├── iterative_refactor.py # Hybrid — wrapper exposing /iterative-refactor
│       ├── validate_change.py  # Hybrid — agent + gate loop implementation
│       └── dispatch_work.py    # Dispatch — NEW at L2, assigns work to agents
├── sample/
│   └── src/
│       ├── __init__.py
│       ├── handler.py          # Platform API handler (the code pipelines operate on)
│       ├── utils.py            # Platform utilities (validation, formatting, sanitization)
│       └── refactor_target.py  # Seeded lint defects — makes /iterative-refactor loop
├── docs/
│   ├── ci-build.mermaid        # Sequence diagram — /ci-build path
│   ├── pr-review.mermaid       # Sequence diagram — /pr-review path
│   ├── validate-change.mermaid # Sequence diagram — /iterative-refactor path
│   └── dispatch-work.mermaid   # Sequence diagram — /dispatch-work path
├── grafana/
│   ├── docker-compose.yml      # Grafana + Prometheus stack
│   ├── prometheus.yml          # Prometheus scrape config
│   ├── README.md               # Grafana setup instructions
│   ├── dashboards/
│   │   └── adp-dashboard.json  # Pre-configured ADP observability dashboard
│   └── provisioning/           # Auto-provisioned datasources and dashboard config
└── tests/
    ├── __init__.py
    ├── test_tools.py           # 14 tests — lint, test runner, build, security scan
    ├── test_governance.py      # 13 tests — identity, security policies, observability, wrap
    ├── test_harness.py         # 15 tests — context, capability, execution, evaluation, flow
    ├── test_observability.py   # 27 tests — spans, tracer, metrics, logger, stack
    ├── test_metrics_server.py  # 6 tests — HTTP server, /metrics endpoint, lifecycle
    └── test_paths.py           # 22 tests — ci-build, pr-review, iterative-refactor, dispatch-work
```

---

## Troubleshooting

**`FAIL lint (ruff)` with a "Ruff not installed" message** — you installed with
`python3 -m pip install -e .` (which has no base dependencies). Install the dev extras:
`python3 -m pip install -e ".[dev]"`. The demo also falls back to `python3 -m ruff` when
the binary isn't on PATH, so a plain `python3 -m pip install ruff` in the same
environment works too.

**Lint gate fails with "unparseable output"** — Ruff ran but couldn't be
parsed (usually a config or version mismatch). The gate fails closed by
design; the stderr tail is included in the stage output.

---

## Running Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run a specific test file
pytest tests/test_tools.py
pytest tests/test_harness.py
pytest tests/test_governance.py
pytest tests/test_paths.py
pytest tests/test_metrics_server.py
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

**`/iterative-refactor` (hybrid):** L0-L1 is a single gate. L2 loops on failure with agent-generated fixes. Retry limit is enforced. Exhaustion triggers human escalation. The deterministic gate (L01 pipeline) is unchanged between levels.

**`/dispatch-work` (dispatch):** Does not exist at L0-L1 (humans pick from backlog, no dispatch logic). At L2, work items are queued by priority, matched to agents by capability, assigned with GOVERNANCE wrapping, and escalated when no capable agent is available. Priority ordering is verified (critical items dispatch first).

**Observability:** Spans nest correctly (parent-child trace trees). Metrics increment and export in Prometheus text format. Structured logs filter by level and include context fields. The ObservabilityStack exports all three formats to disk.

---

## GOVERNANCE Component Mapping

Every agent-driven path wraps execution with GOVERNANCE. The three sub-layers — Identity, Security, Observability — are implemented in `governance.py` and used by each path as follows:

| Component | Class | What It Does | Paths That Use It |
|-----------|-------|-------------|-------------------|
| Identity | `GovernanceIdentity` | `register()` + `verify()` — agent must be registered before execution | /pr-review, /iterative-refactor, /dispatch-work |
| Security | `GovernanceSecurity` | `add_policy()` + `enforce()` — policy functions checked before every action | /pr-review (repo-scope, no-merge), /iterative-refactor (retry-limit), /dispatch-work (capability-scope) |
| Observability | `GovernanceObservability` | `record()` + audit trail + metrics + L01 bridge via ObservabilityStack | /pr-review, /iterative-refactor, /dispatch-work |

`Governance.wrap()` orchestrates the sequence: verify identity → enforce policies → execute → record. If identity verification fails or any policy denies, the wrapped function never runs.

Deterministic paths (`/ci-build`) do not use GOVERNANCE — the pipeline does not know or care who wrote the code.

---

## HARNESS Component Mapping

Agent-driven paths that require probabilistic reasoning use HARNESS to orchestrate the agent's execution. The four components — Context, Capability, Execution, Evaluation — are implemented in `harness.py`:

| Component | Class | What It Does | Paths That Use It |
|-----------|-------|-------------|-------------------|
| Context | `HarnessContext` | Reads real files via `Path.read_text()`, loads failure signals, gathers change metadata | /pr-review (source files, ADRs), /iterative-refactor (failure signals + source) |
| Capability | `HarnessCapability` | Selects model + strategy based on change type (routine → standard, security-sensitive → deep-scan) | /pr-review, /iterative-refactor |
| Execution | `HarnessExecution` | Simulate: real AST analysis + pattern matching. Live: Claude API with structured prompts | /pr-review (generate-review), /iterative-refactor (generate-fix) |
| Evaluation | `HarnessEvaluation` | Assesses result quality → auto-approved / request-changes / pending-human-review | /pr-review (always pending-human-review at L2) |

`Harness.run()` chains all four in sequence: Context → Capability → Execution → Evaluation.

`/dispatch-work` uses HARNESS-like capability matching inline (the `_match_agent` function) rather than the full `Harness.run()` orchestrator, because dispatch is about routing work, not generating content.

Deterministic paths (`/ci-build`) do not use HARNESS — there is no probabilistic reasoning involved.

---

## References

As cited in the *ADP in Action* paper:

1. von Grünberg, K. and Galante, L. *Thinking in Platforms: Platform engineering as the operating model for work in the AI era.* Weave Intelligence, 2026. ISBN 978-3-9828877-0-8.
2. *[The Four Levels of Agentic Software Development in the Enterprise](https://weaveintelligence.io/research/the-four-levels-of-agentic-software-development-in-the-enterprise).* Weave Intelligence, 2025.
3. *[From IDP to ADP: Why Platform Engineers Now Build Agentic Development Platforms](https://weaveintelligence.io/blog/from-idp-to-adp).* Weave Intelligence, 2025.
4. Chankramath, A. *[The Platform Engineer's Handbook](https://www.amazon.com/Platform-Engineers-Handbook-developer-focused-streamline/dp/1806380137).* Packt, 2026. ISBN 978-1-80638-013-8.

---

## Author

**Ajay Chankramath** — ajay@platformengineering.org

CTO, Platform Engineering Advisory | PlatformEngineering.org

---

## License

MIT
