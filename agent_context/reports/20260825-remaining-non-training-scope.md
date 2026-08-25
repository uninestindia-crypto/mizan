# Remaining scope outside model training

REPORT_ID: 20260825-remaining-non-training-scope
AUTHOR: Claude Code (Opus 5), founder-directed
DATE_UTC: 2026-08-25
MEASURED_AT: `5127cf48` (main), working tree clean
QUESTION: With research/training set aside, how much of QuantOS is left?

## Answer in one paragraph

The **build** outside training is essentially finished; the **proof** and the **wiring** are not.
All 12 release slices are code-complete, 929 tests pass in normal and reverse file order, and every
subsystem the PRD names exists in `src/quant_system/` with tests behind it. What remains is three
things, in descending size: (1) **independent adjudication of slices 4-12**, which has never been
run and is the single largest gap; (2) **runtime wiring of five of the seven operator journeys**,
which today return typed unavailability rather than results; (3) **release and CI plumbing**, two
items of which only the founder can perform. My estimate is that **roughly 15-20% of non-training
work remains, and about two thirds of that is verification rather than new code.** The percentage is
a judgment, not a measurement; the item-level tables below are the measurement.

A fourth category exists and should not be counted as "left": several journeys cannot produce real
output because **no model is promotable** (best deflated Sharpe `0.397794` against a `0.95` gate).
That is a research result, not an engineering shortfall. Wiring cannot fix it.

## Subsystem inventory, measured

| Subsystem | Code | Tests | Independently adjudicated | Runtime-reachable | Remaining |
|---|---|---|---|---|---|
| Data acquisition (Upstox V3, point-in-time) | complete, 14 files / 2,822 lines | yes | **yes** (Slice 1) | **yes** — real 498-bar and 10-year acquisitions | none |
| Evidence store (content-addressed, atomic) | complete, 8 files / 1,648 lines | yes | **yes** (Slice 2) | yes | none |
| Feature/label datasets, purge/embargo | complete | yes | **yes** (Slice 3 + schema-v2 recheck) | yes | none |
| Holdout vault + promotion gates (Slice 5) | complete | 15/15 | **no** | **no** — API returns `HOLDOUT_EVALUATION_NOT_AVAILABLE` | adapter wiring + adjudication |
| Server API + supervisor (Slice 6) | complete, 13 files / 5,642 lines | 127 focused | **partial** — real-journey API PASS at `474795f` | yes for datasets/operations | adjudication of the merged tree |
| Financial calc: NSE rules, Decimal ledger, Greeks, risk governor (Slice 7) | complete | 30/30 | **no** | yes (backtest paths) | adjudication |
| Recorded shadow replay (Slice 8) | complete | 25/25 | **no** | **no** — `SHADOW_SESSION_NOT_CONFIGURED` | session registry + adjudication |
| Real-time shadow (Slice 9) | complete | 12/12 | **no** | runner exists; not exposed via API | same |
| Paper pilot, order-book sim, slippage (Slice 10) | complete, 12 files / 4,056 lines | 17/17 | **no** | **no** — `PAPER_CAMPAIGN_NOT_CONFIGURED`, UI inputs disabled | campaign lifecycle + adjudication |
| Desktop UI, 7 operator journeys (Slice 11) | complete | 23/23 | **partial** (real-browser evidence at `474795f`) | 2 of 7 journeys live | 5 journeys show truthful "unavailable" |
| Windows x64 release, SBOM, manifest (Slice 12) | complete, 5 files / 1,075 lines | 16/16 | **no** | yes; artifact rebuilt at `1762b229` | clean-clone release verify at current head |
| Portfolio (allocation, sizing, optimization) | 4 files / 327 lines | yes | no | reachable via API | blocked by the single-instrument dataset contract |
| Advisory / LLM panel | 6 files / 1,316 lines | yes | no | observer-only by decision | none — it records, it never decides |
| Live-money order routing | **absent by design** | — | — | — | **out of scope** (T4, unauthorized) |

## What is actually left, ranked

### 1. Independent adjudication of slices 4-12 — the largest gap

`.launch/STATE.md` records `PHASE: P5 (Release Certified)` and, in the same file, **"Zero slices
beyond 3 have a valid independent adjudication."** Both cannot be true. Since then three narrow
independent passes have landed — the governed execution path (Majors 4-9 recheck + Phase 2), the
canonical feature window (schema v2, rechecked twice), and the real-journey API at `474795f` — and
each of the three *found real defects in work its author had already declared done*. That is the
argument for the remaining nine: every time this programme has adjudicated something, it broke.

Nine slices of financial-correctness code — ledger, Greeks, risk governor, fills, slippage, holdout
gates — carry only their author's word. Estimated 4-6 independent sessions, each by an agent that
did not write the code under review.

### 2. Five operator journeys return unavailability instead of results

Truthful, not fake — that is deliberate and was independently verified. But it means the product
demonstrates two of seven journeys end to end.

| Journey | Endpoint | Current response | Blocked by |
|---|---|---|---|
| 1. Dataset ingestion | `POST /api/v1/datasets` | **works** — real acquisition, real evidence | — |
| 2. Feature explorer | `POST /api/features/explore` | `FEATURE_EVIDENCE_NOT_AVAILABLE` 404 | **wiring only** — the evidence already exists |
| 3. Governed training | `POST /api/v1/operations/train` | `MODEL_CONTRACT_INCOMPATIBLE` 409 | **wiring only** — the v2 adapter is certified (training-adjacent) |
| 4. Holdout + stress | `POST /api/holdout/evaluate` | `HOLDOUT_EVALUATION_NOT_AVAILABLE` 409 | wiring, then a promotable candidate |
| 5. Backtest | native canvas chart | **works** — 6 trades, 6 fill rows, real-browser evidence | — |
| 6. Shadow monitor | `/api/shadow/status`, `/api/shadow/control` | `SHADOW_SESSION_NOT_CONFIGURED` 404 | needs a server-side session registry |
| 7. Paper pilot | `/api/paper-pilot/*` | `PAPER_CAMPAIGN_NOT_CONFIGURED` 404 | needs campaign lifecycle; UI capital/DD inputs disabled |

Journey 2 is the cheapest real win: governed feature evidence already exists in the store, so this
is a read path, not new machinery. Journeys 6 and 7 need a session/campaign registry in the server —
the engines (`execution/realtime_shadow.py`, `execution/paper_pilot.py`) are built and tested, they
are simply not addressable over the API.

Estimated 3-5 sessions for journeys 2, 6 and 7 plus the disabled UI controls.

### 3. `main` is not gate-green right now

Measured at `0316410e` and unchanged in kind at HEAD:

```
ruff check .                   FAIL
ruff format --check .          FAIL
mypy src launcher.py scripts   FAIL (7 errors)
```

All of it is in six newly landed data-ingestion scripts (`ingest_all_market_data.py`,
`build_multidim_feature_store.py`, `analyze_market_universe.py`, and three others); the seven mypy
errors read like one mis-annotation propagating through attribute accesses. Tests are unaffected —
929 pass. **Anyone citing a green gate from this tree today would be wrong.** Owned by the ingestion
author; notice filed at
`agent_context/work/active/20260825-NOTICE-repo-gates-red-in-ingestion-scripts.md`. Half a session.

### 4. CI and branch protection — founder-only

The workflow file exists but sits unpushed on branch `ci-workflow-pending` because the token lacks
`workflow` scope. Branch protection on `main` requiring the `gates` check is a GitHub repository
setting no agent should make. Both are the founder's, and until they land the gate set only runs
when someone remembers to run it (`scripts/run-gates.ps1` does so locally).

### 5. Coordinator items on `.launch/STATE.md`

Three edits, blocked because that path is claimed by another record: resolve the P5-vs-adjudication
contradiction, mark Major #3 closed (artifact rebuilt at `1762b229`), mark Major #4 closed
(capability claims corrected at `5a0447b`). Minutes of work, gated on ownership rather than effort.

### 6. Structural debt and coordination hygiene

- **679 code-craft findings / 47 test-craft findings.** Composition matters more than the total: 677
  of 679 are `long-line`, `deep-nesting`, `long-function` and `god-file`, and 108 of them sit in four
  files that carry the programme's only independent PASS. Reshaping adjudicated source for style
  would mean the adjudicated artifact no longer matches the adjudicated code. Most `long-line` hits
  are embedded HTML the formatter cannot break. The urgent subsets are already closed:
  `sleep-in-test` at `fb0fc15f`, reachable `loop-in-test` at `ff51b631` (9 of the original 31 were
  regex false positives on comprehensions).
- **47 active work records** and 8 handoffs, many describing finished work. Retiring them is
  bookkeeping, but a stale claim blocks a real edit.
- **Two live worktrees** (`codex/real-journey-api`, `codex/release-manifest-integrity`). The first is
  already merged into `main`; the second is in flight. Neither may be pruned by anyone who did not
  create it.

### 7. Residual risks that no ticket closes

- **Shadow P&L does not equal backtest P&L.** The validated label enters and exits at session opens;
  the shadow runner fills on quotes. The maturity horizon closed the structural gap, not the pricing
  one.
- **The ungoverned-model guard reads a declaration, not the code.** A future strategy embedding an
  ungoverned model without `research_only = True` is not detected.
- **The session calendar, absent `--calendar-file`, is derived from provider data**, so a provider
  that silently drops a trading day yields a calendar agreeing with its own gap.
- **Portfolio is a stub in practice.** `modeling/labels.py:135` binds each feature row to one
  acquisition manifest, so no multi-instrument dataset can be built and `portfolio/` (327 lines) has
  nothing cross-sectional to optimise. Changing that reaches the dataset, label, fold and
  evidence-identity paths — a modelling-contract change, not a feature change.

## Rollup

| Category | Share of what's left | Can an agent finish it? |
|---|---:|---|
| Independent adjudication, slices 4-12 | ~45% | yes — a fresh agent per slice |
| Journey runtime wiring (2, 6, 7 + UI controls) | ~25% | yes |
| Release verification at current head, manifest integrity | ~10% | yes (one already in flight) |
| Gate-green repair in the ingestion scripts | ~5% | yes, by its owner |
| Craft/structural debt worth doing | ~10% | yes, selectively |
| CI push + branch protection | ~5% | **no — founder only** |

**Not counted as remaining work:** live-money routing (excluded by design, T4), promotion of any
model (no candidate passes the gate), and any new research campaign on this model class.

## The honest bottom line

If the goal is *a working, evidence-backed research and paper-trading platform*, the engineering is
roughly 85% done and the missing 15% is mostly proving what is already written. If the goal is *a
platform someone else would trust*, that missing 15% is the part that matters most: nine slices of
money-handling code have never been checked by anyone who did not write them, and every adjudication
this programme has run so far found something.
