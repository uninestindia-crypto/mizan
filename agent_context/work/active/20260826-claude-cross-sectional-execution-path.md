# Cross-sectional governed execution path

STATUS: IN_PROGRESS
AGENT: Claude Code — cross-sectional execution gap
STARTED_UTC: 2026-08-26T00:00:00Z
STARTING_REVISION: `466d562b`
WORKTREE_OR_BRANCH: `D:\quant_system` on `main` (shared checkout)
AUTHORIZATION: founder instruction, 2026-08-26

## Objective

The governed execution path cannot express a cross-sectional model's decision. Close that gap so a
multi-instrument ranking model has a surface to execute on at all. This is an **engineering** gap and
is independent of whether any particular model is promotable.

## Why this is not "paper trade Mizan"

The founder asked to paper-execute Mizan on live data to measure accuracy. Three findings, measured
rather than assumed, redirected the work to the gap underneath it:

1. **Mizan cannot reach the verdict gate.** `scripts/run_governed_shadow_session.py --evidence-root
   data/evidence/models/mizan-v1` exits **2**, not 3: the bundle builder refuses a model with more
   than one published instrument, and Mizan publishes 43. It never got as far as the verdict.
2. **Accuracy is already measured with more power than a live run can reach.**
   `screen_mizan_out_of_sample.py` measured selection edge **-0.000022, t = -0.07** over 902,582
   rows and 2,413 rebalances. A live 10-session-horizon run yields ~24 rebalances/year. A live paper
   run cannot improve on that estimate; its value is **operational** (live feature computation, fill
   realism, cost model, session durability), not evidential.
3. **Both Mizan models are `RESEARCH_ONLY`** (DSR 0.1760 and 0.0009 against a 0.95 gate). Nothing
   here promotes them, and this record does not attempt to.

## Scope

Three layers must change for any cross-sectional model to execute:

| Layer | Current behaviour | Evidence |
|---|---|---|
| Bundle | `ModelEvidenceIdentityV1.symbol: str` is a single instrument; `PromotedModelBundleV1.__post_init__` pins `standardization.feature_names != FEATURE_NAMES_V1` and schema `quantos.ridge_technical_six` v2 | `governed_strategy.py:135,208,213` |
| Strategy | `generate_signals` reads one bound symbol and **raises** on any other symbol in the served history | `governed_strategy.py:340-347` |
| Shadow runner | `GOVERNED_BARS_KEY` is populated with exactly one symbol, the quote's own | `realtime_shadow.py:464-466` |

## Non-goals

- Promoting Mizan or any model. The verdict gate is untouched and stays fail-closed.
- Live-money routing. Excluded by AGENTS.md absent T4 authorization.
- Changing `GatePolicyV1` thresholds, or writing to any governed evidence store.
- Re-adjudicating or altering the single-instrument path's invariants.

## Design decision: a parallel module, not a generalization

`src/quant_system/execution/governed_strategy.py` is the target of an IN_PROGRESS Red Team record
(`20260823-redteam-governed-execution-path.md`) and carries invariants that a recheck specifically
hardened — the per-bar symbol binding that caught RELIANCE bars passing under an INFY key.
Generalizing it in place would put an adjudicated path back in flight.

Instead: a new `execution/cross_sectional_strategy.py` that **imports** the risky shared primitives
(point-in-time window selection, per-bar symbol verification, scoring) rather than copying them, and
adds only the cross-sectional layer on top. The single-instrument path keeps its behaviour
bit-for-bit.

## Owned paths

- `src/quant_system/execution/cross_sectional_strategy.py` (new)
- `tests/test_cross_sectional_strategy.py` (new)
- `agent_context/work/active/20260826-claude-cross-sectional-execution-path.md` (this file)
- `src/quant_system/execution/governed_strategy.py` — **additive only**: promote three private
  helpers to public names, keeping the private aliases so existing behaviour is unchanged

## Ownership check performed

- `git worktree list`: 3 worktrees, 2 belonging to `codex/real-journey-api` and
  `codex/release-manifest-integrity`. Neither touches `execution/**`. Left alone per PROTOCOL 8.3.
- 49 active records read. Records naming `execution/**`:
  - `20260823-redteam-governed-execution-path.md` (IN_PROGRESS) — owns **only** its own record and
    `.launch/reports/RED-TEAM-GOVERNED-EXECUTION.md`; states "Nothing else is written. The
    adjudication is read-only against the tree." No write claim.
  - `20260822-claude-model-execution-adapter-scope.md` (IN_PROGRESS) — owns **only** its own file;
    explicitly "no source edited".
  - `20260822-claude-governed-execution-adapter.md`, `-governed-shadow-wiring.md`,
    `-maturity-horizon.md`, `20260824-claude-remove-ungoverned-ridge-from-execution.md` — all
    COMPLETE. PROTOCOL 5: a COMPLETE record's paths are releasable.
- No active record claims write access to `execution/governed_strategy.py`.
- A notice will be filed for the Red Team record because its adjudication target list names a file
  this record edits, even though its pinned revision `1e5beb5` is already many commits stale.

## Plan

1. Work record + notice to the Red Team record. (this step)
2. Promote the three shared helpers in `governed_strategy.py` to public, additive.
3. New `cross_sectional_strategy.py`: evidence identity over a symbol **set**, schema-aware feature
   family validation, bundle with the same verdict gate, ranking strategy with a declared selection
   rule.
4. Fail-closed decisions on partial cross-sections and deterministic tie-breaking.
5. Tests, including the negative cases: RESEARCH_ONLY refused, foreign symbol refused, partial
   cross-section refused, tie determinism.
6. Full gate: pytest, ruff, ruff format --check, strict mypy, audit-agent-claims, audit-disk-layout.

## Current step

Steps 1-6 complete. The cross-sectional execution layer exists, is tested, and passes every gate on
its owned paths.

## What was built

`src/quant_system/execution/cross_sectional_strategy.py` (new, 478 lines):

| Type | Purpose |
|---|---|
| `CrossSectionalFeatureProvider` | Protocol supplying one decision date's cross-section of feature values. Values rather than bars, because cross-sectional ranks are not a function of one instrument's history |
| `CrossSectionalSelectionRuleV1` | The selection rule, carried on the bundle. `selection_fraction` has no default, for the same reason `score_threshold` has none on the single-instrument bundle |
| `CrossSectionalEvidenceIdentityV1` | Binds a **universe** rather than an instrument, and ties card, artefacts and threshold to one published record |
| `PromotedCrossSectionalBundleV1` | Schema-aware feature-family validation; the same verdict gate as the single-instrument path |
| `CrossSectionalModelStrategy` | Ranks the bound universe on a shared decision date and takes the declared fraction |

### Defect found and fixed during test-writing

`_rank` took the selection count from the **served** cross-section while `_strength` recomputed it
from the **bound universe**. The two agree only at full coverage; under a relaxed `min_coverage`
they diverge, so rank strengths would have disagreed with the selection that produced them. `take`
is now computed once and passed in, so the two cannot drift apart. Caught by
`test_min_coverage_relaxes_the_full_cross_section_requirement_deliberately`.

### Fail-closed choices, stated rather than implied

- A partial cross-section abstains rather than ranking the remainder: missing names move every rank,
  so scoring what is left would emit plausible signals from a strategy nobody measured.
  `min_coverage` relaxes this only by explicit declaration.
- A symbol outside the bound universe raises, because an extra name changes what every other name is
  ranked against.
- Ties break by symbol ascending, so two runs over identical input select identical names.
- The selection fraction is applied to the cross-section actually ranked, matching what each
  rebalance in the screen did.
- The per-bar symbol verification is **reused** from `governed_strategy.require_bar_sequence`, not
  reimplemented. That function is what caught RELIANCE bars passing under an INFY key.

## Commands and outcomes

| Command | Outcome |
|---|---|
| `python scripts/run_governed_shadow_session.py --evidence-root data/evidence/models/mizan-v1 --surface SHADOW` | **exit 2** — refused at single-instrument binding, 43 symbols found |
| `git worktree list` / `git branch --list` | 3 worktrees, 4 branches; 2 codex worktrees untouched |
| `pytest tests/test_cross_sectional_strategy.py` | **36 passed** |
| `pytest` (full suite) | **1011 passed**, 0 failed |
| `ruff check` on owned paths | clean |
| `ruff format --check` on owned paths | clean, 14 files |
| `mypy --strict src/quant_system/execution/` | clean, 13 source files |
| `audit-agent-claims.ps1` | **PASS** (exit 0) |
| `audit-disk-layout.ps1` | **PASS** (exit 0) |

## Blockers and conflicts

### Concurrency observed, not interfered with

Two Antigravity tasks landed in this shared checkout while this work was in progress:

- `20260826-antigravity-mizan-single-model-hub.md` (STATUS: COMPLETE) — its non-goals explicitly
  include "modifying `execution/cross_sectional_strategy.py`", so it coordinated around this work.
- `20260826-antigravity-platform-action-ai-assistant.md` — in flight, owns
  `src/quant_system/assistant/**`.

**A transient full-suite failure was traced and dismissed.** One run showed 6 failures across
`test_server_supervisor.py`, `test_server_governed_completion.py` and `test_server_governed_journeys.py`
with `TypeError: conversion from NoneType to Decimal` at collection. Stashing **only this record's
paths** (so the other agents' uncommitted work was never touched) reproduced the same errors without
this work present, and a later re-run passed 10/10 and then 1011/1011. The cause was a race with a
peer agent writing files mid-run, not a regression here.

**Repo-wide ruff and mypy are currently red, and not from this work.** 17 mypy errors and 5 ruff
findings, all in `src/quant_system/assistant/` — the in-flight Antigravity task above. Left
untouched per PROTOCOL 3: never reformat or clean up another agent's changes. Recorded as an
observation, not a finding against them; the directory is mid-write.

## The remaining gap, named precisely

This closes the **ranking** layer. Mizan still cannot paper-execute, and the reason is no longer the
ranking layer:

1. **No library kernel for the v3 fifteen-feature family.** It lives in
   `scripts/build_mizan_feature_store.py` (`_instrument_rows`, `_apply_cross_sectional_ranks`), in
   `float`, not Decimal. `modeling.pooled.build_mizan_feature_dataset` takes feature values as an
   *argument*, so training and execution have no shared kernel. Computing them a second time inside
   the adapter is exactly the defect `20260824-canonical-feature-window.md` exists to prevent, which
   is why this module takes a provider instead.
2. **Three of the fifteen features are market-wide macro values** (`india_vix_level`,
   `india_vix_change_5`, `nifty_return_5`) loaded from a macro directory at training time. A live
   provider needs a point-in-time source for them. The Mizan record already notes these three carry
   no cross-sectional information at all.
3. **`realtime_shadow.py:464` serves one symbol's bars per decision** — the quote's own. A
   cross-sectional model needs the whole cross-section in one `MarketContext`.
4. **Both Mizan models are RESEARCH_ONLY**, so even with 1-3 closed the verdict gate refuses them —
   correctly. `test_the_real_mizan_model_reconstructs_and_is_then_refused_as_research_only`
   reconstructs the real published model from its committed manifest, asserts it rehashes to the
   recorded `fitted_state_hash`, and proves the refusal.

## Next safe action

Items 1-3 above, in that order, if the founder wants Mizan to reach a shadow surface. Item 1 is the
load-bearing one and is a `modeling/**` change, which is claimed by
`20260820-codex-slice4-ridge-training.md` (STATUS: ACTIVE) — it would need the same handoff-audit
treatment `20260825-1500Z-claude-mizan-slice4-claim-audit.md` used.

Item 4 is not an engineering task and must not be worked around.

## Commands and outcomes

| Command | Outcome |
|---|---|
| `python scripts/run_governed_shadow_session.py --evidence-root data/evidence/models/mizan-v1 --surface SHADOW` | **exit 2** — refused at single-instrument binding, 43 symbols found |
| `git worktree list` / `git branch --list` | 3 worktrees, 4 branches; 2 codex worktrees untouched |

## Blockers and conflicts

None yet.

## Next safe action

Implement step 2.
