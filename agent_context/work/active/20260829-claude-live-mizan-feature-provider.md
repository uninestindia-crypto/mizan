# Live Mizan feature provider: replace fabricated features with the shared kernel

STATUS: IN_PROGRESS
AGENT: Claude Code
STARTED_UTC: 2026-08-29T00:00:00Z
STARTING_REVISION: `e18a0e0e`
WORKTREE_OR_BRANCH: `D:\quant_system` on `main` (shared checkout)
AUTHORIZATION: founder instruction, 2026-08-29 — shown the finding below, answered "yes build it".
  This extends the same explicit override of the active Antigravity claim used for the ruff repair.

## The finding this exists to fix

`scripts/run_paper_pilot_session.py:606-631` builds the model's fifteen inputs by hand. **None of
them is computed the way training computed it.** Measured:

| Feature | What the runner does | Reality |
|---|---|---|
| `return_5`, `return_21` | `r1 * 1.5`, `r1 * 2.5` | rescalings of `return_1`, carrying no independent information |
| `rsi_14_centered` | `min(50, max(-50, r5*200))` | trained range is **[-0.4476, +0.4529], sd 0.1264** over 200,001 rows. The runner can emit values **110x outside** it |
| `india_vix_level`, `india_vix_change_5`, `nifty_return_5` | hardcoded `0.145`, `0.005`, `0.008` | real point-in-time macro |
| `cs_rank_volume_surprise` | `vol_zscore * 0.2` | a cross-sectional rank over the whole date |
| `garman_klass_volatility`, `parkinson_volatility`, both SMA distances, `money_flow_multiplier` | functions of `r1` alone | independent windowed statistics |

Decision rule is also invented: `scores[sym] > 0.035` against the trial's recorded
`score_threshold = 0.071454840454`, and `ranked_symbols[:2]` takes the top 2 whether the universe is
5 names or 490 — not the top 20% the model was screened at.

**Consequence, measured across the 8 recorded sessions:** universe 50 -> **0 proposals**; universe
488 -> **0 proposals**. Only the toy 5-name universe traded, and there it bought **all five** — a
cross-sectional ranking model taking 100% of its universe.

This is the defect class `.launch/` exists to prevent: the system that executes is not the system
that was validated.

## Objective

Feed the paper runner the **real** feature values from `modeling/mizan_features.py` — the kernel
verified bit-identical against the published training store across 157,677 comparisons — and let the
model's own recorded threshold and a declared selection fraction drive the decision.

## Design

Decisions are made on **completed daily bars** and executed at the next session's prices, which is
the contract the model was validated under (`decision_at` = session close, entry at next open). So
the live path needs no intraday feature computation:

1. For each symbol, take the trailing **400 completed daily bars** (`MIZAN_CANONICAL_WINDOW_BARS`).
2. Take real India VIX and NIFTY 50 closes by date for the same window.
3. Call `compute_mizan_cross_section()` — one implementation, shared with training.
4. Rank, take the declared top fraction, propose.

## Owned paths

- `src/quant_system/execution/mizan_live_features.py` (new)
- `tests/test_mizan_live_features.py` (new)
- `scripts/run_paper_pilot_session.py` (founder override of the Antigravity claim)
- `agent_context/work/active/20260829-claude-live-mizan-feature-provider.md` (this file)

## Non-goals

- Promoting Mizan. It stays RESEARCH_ONLY; this is an **ungoverned research harness**, no evidence
  store written and no multiplicity ordinal spent, the same standing this repository's screens have.
- Live-money routing. Paper fills only.
- Rebuilding the feature store.
- Claiming the result is evidence. Mizan's measured out-of-sample selection edge is -0.000022
  (t = -0.07) and a live run cannot improve on that; its value is operational.

## Delivered

| Piece | Where |
|---|---|
| Live cross-section provider | `execution/mizan_live_features.py` |
| Out-of-range refusal | `refuse_extreme_rows`, limit 25 standardized deviations |
| Authority-backed universe | `resolve_universe` in the runner |
| Fresh bars | NIFTY50 (50/50) and NIFTY500 (**499/500, 350,857 bars**) through 2026-08-27 |
| Fresh macro | India VIX + NIFTY 50 through 2026-08-27 |
| Tests | `tests/test_mizan_live_features.py`, 32 tests |

Monday 2026-08-31, decided from the 2026-08-27 close: **499/500 coverage (99.8%)**, 1 refused,
**56 proposals**. The old runner produced **0** on any realistic universe.

## A diagnosis of mine that measurement falsified

I reported BBTC's outlier as "272 standard deviations outside anything the model saw" and proposed an
out-of-domain guard on that basis. **Measured against the training store, that was wrong**: training
contains `volume_zscore` up to `|z| = 84,130`, 150x more extreme, so BBTC was well inside the
training domain and such a guard would not have fired.

The real mechanism, measured over 1,015,831 training rows:

| `volume_zscore` in training | |
|---|---:|
| median / p99 / p99.9 | -0.33 / 8.66 / 33.21 |
| max | **174,888.66** |
| actual stdev | **173.70** |
| **the model's standardization scale** | **2.0788** |

The scaler was fitted on a partition that never saw the tail. A live 565 divided by 2.08 becomes 272
standardized units, and a linear model collapses onto that single term. So the guard belongs on the
**standardized** value, not on the raw one.

Limit chosen by measurement, not taste: across the live 499-name cross-section the per-name maximum
standardized deviation has median **1.5**, p90 **2.1**, p99 **7.0**, and BBTC **271.8**. Every limit
from 25 to 200 refuses exactly that one name, so the choice is insensitive. It **refuses rather than
clips**: clipping would feed the model an input no data produced and silently change the question.

**This is a defect in the v3 feature family, not only in execution.** A ridge fitted on data
containing `volume_zscore` values up to 174,888 has its coefficient partly set by those events. That
is a finding for the model; the guard does not fix it.

## Other findings surfaced on the way

- **`universe.py` index lists are badly stale.** `NIFTY50_SYMBOLS` is 5 names out;
  `NIFTY500_SYMBOLS` holds 488 names of which **167 are no longer in the index and 179 current
  members are absent**. The runner now resolves membership from `data/authorities/`. `universe.py`
  itself was not edited -- it is claimed.
- **`ingest_all_market_data.py` reports success when it does nothing.** Two runs exited 0 having
  ingested zero bars: one parsed 0 targets from a CSV without an `Instrument Key` column, one had
  all 50 symbols fail the Upstox ten-year limit. Both printed `=== INGESTION COMPLETED ===`.
- **It also writes its summary to a fixed path regardless of `--cache-root`.** My 500-symbol run
  overwrote `market-analysis/all-market-ingestion-summary.json`, destroying 37,767 lines describing
  the full 3,267-symbol ingestion. **Restored from `HEAD`**; the file is not part of this commit.
- **My own loader silently preferred stale data**, selecting the longest series per symbol so a
  10-year cache ending 2026-08-21 beat a fresh 3-year one ending 2026-08-27. Now prefers the latest
  end date. It also scanned every fallback cache when one symbol was missing, costing a ten-minute
  timeout; it now stops once the coverage floor is met.

## Next safe action

An independent recheck. I found each of these and repaired them myself, which is the same
author-adjudicates-own-work boundary flagged elsewhere in this session.
