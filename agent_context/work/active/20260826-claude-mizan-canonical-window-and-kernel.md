# Mizan v3 canonical window and shared feature kernel

STATUS: IN_PROGRESS
AGENT: Claude Code
STARTED_UTC: 2026-08-26T00:00:00Z
STARTING_REVISION: `3d120730`
WORKTREE_OR_BRANCH: `D:\quant_system` on `main` (shared checkout)
AUTHORIZATION: founder instruction, 2026-08-26 ("set the window to 400 and build the kernel")

## Objective

Close the defect in `20260826-NOTICE-mizan-v3-reintroduces-window-dependence.md` by declaring a
canonical window for the v3 feature family, and promote the feature computation out of
`scripts/build_mizan_feature_store.py` into the library so training and execution share **one**
implementation rather than two that agree by accident.

## The two numbers, and why both are needed

| Constant | Value | Sizes |
|---|---:|---|
| `MIZAN_WINDOW_BARS` (existing, `pooled.py`) | 51 | The **minimum**: 50-session SMA warmup plus the decision bar. Every bounded feature is exactly reproducible from 51 bars |
| `MIZAN_CANONICAL_WINDOW_BARS` (new) | **400** | The **maximum trailing history the kernel consumes**, sized by the *recursive* member. Wilder RSI is an EMA with alpha=1/14, so seed influence decays as `(13/14)^n`; at n=400 that is `1.34e-13`, and measured worst-case error is `1.71e-12` of the feature's own standard deviation |

The kernel consumes `records[max(0, i - 399) : i + 1]` — trailing **up to** 400 bars. Below 400 that
is the full prefix, which is exactly what training used, so it reproduces the published store
identically there. Above 400 it is bounded and converged.

## Non-goals

- Rebuilding the published feature store. That is a campaign decision, not a contract change, and it
  would spend compute on a family with no measured edge. The kernel makes a rebuild *possible*.
- Promoting any model. Both Mizan models stay RESEARCH_ONLY.
- Changing `MIZAN_WINDOW_BARS`. Raising it to 400 would move the loop start in
  `pooled.build_mizan_feature_dataset`, drop rows the published store contains, and change every
  row's `preprocessing_input_hash` — silently invalidating immutable evidence. The minimum and the
  canonical window are different quantities and are kept separate.
- Editing `src/quant_system/modeling/__init__.py`. It is claimed by
  `20260820-codex-slice4-ridge-training.md` (STATUS: ACTIVE). The kernel is imported by module path.

## Owned paths

- `src/quant_system/modeling/mizan_features.py` (new)
- `tests/test_mizan_features.py` (new)
- `src/quant_system/execution/cross_sectional_strategy.py` (window constant; created by me)
- `agent_context/work/active/20260826-claude-mizan-canonical-window-and-kernel.md` (this file)

## Ownership check performed

- `git worktree list`: 3 worktrees; the 2 codex ones untouched (PROTOCOL 8.3).
- No active record claims `modeling/pooled.py` or names `mizan_features`. `20260820-codex-slice4-ridge-training.md`
  (ACTIVE) owns 12 `modeling/` files — **`pooled.py` is not among them**, but `modeling/__init__.py`
  **is**, hence the non-goal above.
- `scripts/build_mizan_feature_store.py` belongs to `20260825-1500Z-claude-mizan-pooled-model.md`,
  now in `work/completed/`; PROTOCOL 5 makes it releasable.

## Verification standard

The kernel is only correct if it reproduces what training actually produced. The published store
(`data/evidence/feature-store/mizan/mizan_feature_store.csv.gz`, 1,015,831 rows, 423 symbols) is the
oracle. Values are written `f"{value:.10f}"`, so agreement is asserted at that precision.

## Plan

1. Work record. (this step)
2. `modeling/mizan_features.py`: promote `wilder_rsi`, the per-instrument causal features, and the
   cross-sectional rank step verbatim; add the canonical window and a per-decision-bar entry point
   that an execution feature provider can call.
3. Verify against the published store on real symbols, all fifteen features.
4. Point `cross_sectional_strategy.CROSS_SECTIONAL_WINDOW_BARS` at the canonical window.
5. Tests, including the window-dependence regression that would have caught the original defect.
6. Full gate.

## Current step

Steps 2, 4 and 5 complete. Step 3 (verification against the published store) is running.

## What was built

`src/quant_system/modeling/mizan_features.py` (new). Arithmetic promoted **verbatim** from the store
builder, deliberately float rather than Decimal: fidelity to what training computed outranks
arithmetic purity, on the same reasoning that made `governed_strategy.score_row` call the validated
scorer instead of a Decimal reimplementation that disagreed by 4e-13 and flipped a decision.

| Export | Purpose |
|---|---|
| `MIZAN_MINIMUM_BARS` (51) | Fewest bars a row is computable from; imported from `pooled` so it cannot drift |
| `MIZAN_CANONICAL_WINDOW_BARS` (**400**) | Trailing history the kernel consumes, sized by the recursive member |
| `wilder_rsi` | Promoted verbatim |
| `canonical_mizan_window` | Trailing up to 400, ending at the decision bar; full prefix when shorter |
| `compute_mizan_feature_values` | The 13 instrument features for one decision bar |
| `apply_cross_sectional_ranks` | The 2 rank features, over a complete cross-section |
| `compute_mizan_cross_section` | Execution entry point a feature provider wraps |

`execution/cross_sectional_strategy.py`: `CROSS_SECTIONAL_WINDOW_BARS` now imports
`MIZAN_CANONICAL_WINDOW_BARS` (400) rather than the minimum. Documented reason: training legitimately
replays a symbol's early life on a short prefix, but execution is always at the present, so a name
served 60 bars would be ranked against names served 400 while carrying a different RSI convergence
state — not a comparison the model was fitted to make.

## Tests

`tests/test_mizan_features.py`, **23 tests**. The load-bearing one is
`test_features_are_identical_however_much_history_precedes_the_window`: the same decision bar must
score identically from 500 bars of history or from 2000. **Nothing in the repository asserted that
property before, which is exactly why nothing caught the original defect.**

Its companion `test_a_window_shorter_than_the_canonical_one_really_does_change_rsi` proves the
sensitivity is real rather than theoretical — at 51 bars `rsi_14_centered` differs while every
bounded feature is unchanged.

One fixture error of mine, caught by the suite: the first version built macro data keyed by index
within each supplied series, so the three macro features differed by construction and the test was
measuring the fixture rather than the kernel. The twelve price-derived features — RSI included —
were already identical, which is the property that mattered. Fixed by keying macro by date and
building it once.

## Commands and outcomes

| Command | Outcome |
|---|---|
| `pytest tests/test_mizan_features.py` | **23 passed** |
| `pytest tests/test_mizan_features.py tests/test_cross_sectional_strategy.py` | **59 passed** |
| `pytest` (full suite) | **1047 passed**, 0 failed |
| `ruff check` on owned paths | clean |
| `ruff format --check` on owned paths | clean, 3 files |
| `mypy --strict` on both modules | clean, 2 source files |

Repo-wide `ruff check .` reports 46 errors, **none in owned paths**. They are in
`scratch/test_upstox_env.py`, `scripts/run_paper_pilot_session.py`, `scripts/serve_live_dashboard.py`,
`scripts/view_live_pnl.py`, `server/app.py` and `tests/test_live_universe_robustness.py` — a peer's
in-flight work that appeared during this task. Left untouched per PROTOCOL 3.

## Blockers and conflicts

None. `modeling/__init__.py` was not edited, so the ACTIVE claim on it is untouched; the kernel is
imported by module path.

## Step 3 — verified against the published store

The oracle is `data/evidence/feature-store/mizan/mizan_feature_store.csv.gz`, what training actually
consumed. Kernel output compared against it directly.

### A. Instrument-level features — 12,129 rows across 5 symbols

| feature | worst \|kernel - published\| |
|---|---:|
| return_1, return_5, return_21 | **0.000e+00** |
| garman_klass_volatility, parkinson_volatility | **0.000e+00** |
| sma_20_distance, sma_50_distance | **0.000e+00** |
| volume_zscore, money_flow_multiplier | **0.000e+00** |
| india_vix_level, india_vix_change_5, nifty_return_5 | **0.000e+00** |
| **rsi_14_centered** | **1.000e-10** |

**Twelve of thirteen features are bit-identical in text.** Across 12,129 x 13 = **157,677 value
comparisons there were 3 exact-text mismatches** (1.90e-05 of comparisons), all in
`rsi_14_centered`, all of magnitude exactly `1e-10`.

`1e-10` is **one unit in the last place** of the store's own `{:.10f}` format. These are not kernel
errors: they are the trailing-400 window's convergence residual (~1e-13 in the feature) landing on a
rounding boundary in the tenth decimal. In the feature's own units that is **8.17e-10 standard
deviations**, against the **2.46e-01 sd** defect this work exists to fix — a factor of **3.0e+08**.

### B. Cross-sectional ranks — complete cross-sections

| date | published names | rebuilt | missing | worst diff | exact text |
|---|---:|---:|---:|---:|---:|
| 2019-06-14 | 416 | 416 | 0 | **0.000e+00** | **416/416** |
| 2024-03-15 | 423 | 423 | 0 | **0.000e+00** | **423/423** |

Both rank features reproduce **exactly** over the full cross-section, on two dates chosen years
apart. This also confirms the rank tie-break and the `(rank + 1) / count - 0.5` centring match the
builder, and that `count` is the whole cross-section rather than a subset.

## Conclusion

The kernel reproduces what training produced. Training and execution now have **one** implementation
rather than two that agreed by accident, and the window is sized by the estimator's mathematics
rather than by reading the feature list.

## Next safe action

This record's work is complete and independently checkable by re-running the verification. Remaining,
and **not** done here:

1. **An independent recheck.** I found the window defect, chose 400, wrote the kernel and verified it.
   That is author-adjudicates-own-work again; it needs a third party.
2. **Rebuilding the feature store under the canonical window** is still not done, and is a campaign
   decision rather than a contract change. Until it is, published Mizan models remain
   pre-canonical-window in the same sense the 40 v1 models were pre-v2: auditable research evidence
   that cannot execute.
3. Both Mizan models remain **RESEARCH_ONLY** and unpromotable. Nothing here changes that, and the
   verdict gate is untouched.
