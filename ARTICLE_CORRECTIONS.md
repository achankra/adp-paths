# "ADP in Action" — Pre-publication Text Corrections

Apply to the article draft. Repo-side fixes are already done (tests green 92/92,
Ruff clean, seeded defect added, `--path` flag added, LICENSE added, model bumped).

---

## 1. Running the Code section (p.13–14) — command and output are wrong

**Command** — keep as printed; the repo now supports it. Both forms work:

```
$ python -m src.cli --simulate --path iterative-refactor
$ python -m src.cli --simulate iterative-refactor
```

Note: `git clone` creates a directory named `adp-paths` (hyphen). Change
`$ cd adp_paths` → `$ cd adp-paths`.

**Terminal output** — replace the entire printed output block with this real,
reproducible output (verbatim from a run):

```
════════════════════════════════════════════════════════════════════
  /iterative-refactor — Hybrid Path (at L2)
════════════════════════════════════════════════════════════════════

  L0-L1: Single gate
  ────────────────────────────────────────────────────────────
  Type: gate
  Layers: [L01 Tooling]
  Passed: False

  Pipeline:
    FAIL lint-check (ruff) — 4 error(s), 0 warning(s)
  Loop: None — human reads output and fixes manually
  HARNESS: None
  GOVERNANCE: None

  L2: Agent + gate feedback loop (simulate)
  ────────────────────────────────────────────────────────────
  Type: hybrid
  Layers: [L01 Tooling] [L02 Paths] [L03 Agents]
  Status: passed
  Attempts: 2
  Resolved by: agent-fix

  Feedback Loop Trace:
    RETRY Attempt 1: Gate failed
      Fix: ruff-autofix — targets: I001, F401, F401, F401
    PASS Attempt 2: Gate passed

  GOVERNANCE:
    Events recorded: 1
    Audit trail: 1 entries

  Layer Summary:
    L01 Tooling: Deterministic gate executed on each attempt (real Ruff, real security scan)
    L02 Paths  : Path defined as hybrid — agent + gate feedback loop
    L03 Agents : HARNESS generated 1 fix(es). GOVERNANCE tracked 2 attempt(s). Final status: passed.
```

Why this differs from the old draft output: the gate for this path is
lint → build → security (there is no `test` stage); the fix targets are lint
codes (I001/F401), not a "build ✗"; the agent id is `refactor-agent-001`; and
the demo now loops because `sample/src/refactor_target.py` ships with seeded,
auto-fixable defects. Add one sentence after the output:

> The sample repository seeds `refactor_target.py` with auto-fixable lint
> defects so the loop demonstrably runs: the gate fails on attempt 1, the
> agent applies a fix, and the gate passes on attempt 2. At L0-L1 the same
> file simply fails the gate and waits for a human.

## 2. Metrics paragraph (p.4) — code reference is wrong

Current: "In the code, that is the `governance.observability.get_metrics()`
call in the return dict. Those three numbers - override rate,
fix-on-first-attempt rate, false positive rate - are what tell you…"

Problems: (a) forward-references code the reader hasn't seen; (b) only
override rate lives in `get_metrics()` (now derived in the code as
`override_rate`); the other two come from elsewhere.

Replace with:

> In the companion code, the governance layer derives the override rate from
> its audit counters (`get_metrics()["override_rate"]`), the loop result
> records whether a change passed on the first attempt (`resolved_by:
> first-pass` vs `agent-fix`), and false-positive tracking falls out of the
> evaluation component's verdicts. Those three signals — override rate,
> fix-on-first-attempt rate, false positive rate — are what tell you whether
> L2 is working or just creating noise.

## 3. Maturity levels (p.3) — misstates the source

Current: "The Weave whitepaper defines five maturity levels of an organization
on its agentic journey, from L0 through L4."

The whitepaper explicitly does **not** count L0 among the levels ("Level 0…
is not counted among the four levels of agentic software development").

Replace with: "The Weave whitepaper defines four levels of agentic software
development (L1–L4) on top of an L0 baseline — the functioning IDP with no
agentic capabilities."

## 4. Nine paths (p.2) — attribution

Current text attributes "nine paths to outcomes" to the whitepaper/article.
The whitepaper defines **eight** (seven baseline paths plus Dispatch Work,
new at L2). *Secure System* is this article's addition. Replace with:

> These extend the eight "paths to outcomes" defined in the whitepaper — the
> seven baseline paths plus Dispatch Work, which appears at L2 — with a ninth,
> Secure System, which we add because in regulated environments security
> operates as a first-class path rather than a stage inside others.

Also: Dispatch Work is currently listed first among "the most common ones"
with no caveat. Add "(new at L2 — it has no L0/L1 equivalent)" after it, so
p.2 doesn't contradict p.4.

## 5. "Seven of nine" (p.4) — show the arithmetic

Current: "Seven of nine paths are new or altered."
The whitepaper's figure says six of eight. With Secure System added and
altered at L2, the count becomes seven of nine — say so explicitly:

> Seven of nine paths are new or altered (the whitepaper counts six of its
> eight; our added Secure System path is also transformed at L2, where
> periodic manual scanning becomes continuous automated enforcement).

## 6. Quotes and citations (p.12) — wrong ref numbers, inexact quote

- "As we discussed in the whitepaper [3] 'The bottleneck has shifted…'" →
  this quote is from the **whitepaper**, which is reference **[2]**, not [3].
  Change "[3]" to "[2]" (and "the whitepaper" now matches).
- The block quote "In a majority of failed AI initiatives… no observability
  into what was actually running [3]" is a paraphrase presented as a quote,
  and also mis-cited. The whitepaper's actual text: "In a majority of failed
  AI initiatives, the cause wasn't the models themselves. It was the failure
  of the platform's deterministic fabric to provide the necessary guardrails,
  checks, and balances during execution." Either quote that exactly (cite
  [2]) or keep your expanded version unquoted as prose.

## 7. References (p.14)

- Ref [1]: "Von Grunberg" → "von Grünberg" (umlaut, lowercase v per byline).
- Refs [2] and [3]: dated 2025 → **2026** (both Weave publications are 2026).

## 8. L01/L02/L03 vs L0/L1/L2 — disambiguate once, early

The article uses L0–L4 for **maturity levels** and L01/L02/L03 for
**architecture layers**; `run_at_l01()` refers to maturity while
`"layers": ["L01"]` refers to the tooling layer — same token, two meanings,
sometimes in one code block. Add a note box right after the three-layer
introduction (p.2):

> **Notation.** L0–L4 (no leading zero) are maturity levels. L01/L02/L03
> (leading zero) are the three architecture layers: Tooling, Path
> Definitions, Agent Infrastructure. In code, `run_at_l01()` /
> `run_at_l02()` refer to maturity levels; the `layers` field lists
> architecture layers.

## 9. Listings — make them match the repo

- **Listing 1** references `lint_stage`… functions that are never defined and
  imports `tools` unused. Replace the `pipeline_stages` block with the repo's
  factory call: `stages = create_default_stages(input_data)` and note the
  factories wrap real tools (Ruff subprocess, importlib assertions,
  ast.parse, pattern scanner). Or excerpt `src/paths/ci_build.py` verbatim.
- **Listing 2**: restore the dropped `options = options or {}` line (as
  printed it crashes on the default argument); `file_paths` must come from
  `_resolve_file_paths(pr)`; the result access is
  `governed_result["result"]["components"]`, not `result.get("components")`;
  policy checks are async functions in the repo, not sync lambdas.
- Simplest fix for both: caption them "abridged from the repository —
  runnable versions in `src/paths/`" AND fix the two crash-level bugs
  (undefined names, missing `options or {}`).
- Listing 1 caption "deterministic, L01 only" — keep, but it now reads
  cleanly with the notation box from item 8.

## 10. Figures and tables

- Figure numbering jumps 2 → 4. Renumber (Figure-3 = the /ci-build figure)
  or restore the missing Figure-3.
- /pr-review is the only path with no figure — consider adding its HARNESS
  flow (context → capability → execution → evaluation) for symmetry.
- Table-1 caption: "What change at each maturity level" → "What changes…".

## 11. Small text fixes

- Intro: "The transition from an IDP … to an ADP where … thinking we used
  earlier. It has to structurally evolve." — sentence fragment; suggested:
  "The transition from an IDP — where humans build for humans — to an ADP —
  where the consumers are autonomous agents — cannot be handled with the
  same criteria we used before. The platform has to structurally evolve."
- p.3: "The context of the nine paths described above are shown" → "is shown".
- p.2: "execution,and" → "execution, and".
- p.5: "Figure-4 shows how different paths lead to pretty much the same
  results" → "Figure-4 shows how the same deterministic path produces the
  same result regardless of who triggers it."
- p.6 caption spacing: "Figure-4:Deterministic" → "Figure-4: Deterministic".
- p.7 heading spacing: "/pr-review :From Manual" → "/pr-review: From Manual".
- p.13: default model is now `claude-sonnet-4-5` (repo updated); mention
  `ANTHROPIC_MODEL` env override if you name a model at all.
- Delete the trailing blank page 15.
- p.14 "tests we have provided will verify … that dispatch assigns work by
  capability" — dispatch is a fourth path in the repo but the article says
  "three paths"; add one line earlier: "(the repo also implements
  /dispatch-work, which we do not walk through here)".

## 12. Verify before publish (external)

- Confirm https://github.com/achankra/adp-paths is public and pushed with
  these fixes (pyproject `Repository` URL now points there; LICENSE added).
- Re-run `pip install -e ".[dev]" && pytest` from a fresh clone: expect 92
  passed. `ruff check src tests`: expect clean.
