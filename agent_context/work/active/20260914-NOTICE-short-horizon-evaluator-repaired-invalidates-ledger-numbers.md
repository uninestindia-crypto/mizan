# NOTICE: the short-horizon evaluator was repaired, and it invalidates published trial numbers

STATUS: NOTICE (additive; no other record is edited)
OWNER: Claude Code (Opus 5), filer
FILED_UTC: 2026-09-14
FOR: `20260910-1615Z-claude-mizan-correction-and-short-horizon-program.md` (STATUS `ACTIVE`), which
  owns `src/quant_system/research_short_horizon/**`, `scripts/run_short_horizon_experiment.py`,
  `src/quant_system/modeling/mizan_model.py` and `reports/short_horizon/`
AUTHORIZATION: founder instruction, 2026-09-14, in answer to an explicit question naming this repair
  and naming this claim as the one it crosses. Item 3 of the repair order in
  `reports/loss_diagnosis_20260913/DIAGNOSIS.md`.
FILED UNDER: PROTOCOL §8.4 — a change that moves numbers another active record pins as evidence
  requires a notice naming the exact figures it invalidates. This is that notice.

## What changed, and why each was a defect rather than a preference

Full rationale lives in `20260914-claude-paper-book-accounting-repairs.md` and in the docstrings. In
one line each:

| Change | Was | Why it mattered |
|---|---|---|
| Capital-constrained tranche ledger in `score_decisions` | each decision date's cohort average compounded in sequence | decisions are daily and held `held_sessions` sessions, so the series overlapped. Compounding it ran the book at up to **3x its capital** and produced an equity path no funded portfolio could follow |
| Past-only abstention calibration | one threshold chosen on all folds' pooled out-of-sample predictions, then scored on those same rows | selection and measurement on one sample. Each fold now uses a threshold fitted on strictly earlier folds; fold 0 holds cash |
| DSR sample length | `len({distinct development decision dates})` | the compounded Sharpe rests on non-overlapping portfolio periods, ~3x fewer at hold 3. Sampling error shrinks as `1/sqrt(n)`, so the inflated `n` made candidates look **better** |
| DSR annualisation | defaulted to `periods_per_year=252` | the Sharpe reaching it was annualised with `252 / held_sessions`. The two conventions disagreed by `sqrt(held_sessions)` and nothing reconciled them |
| `DECLARED_TRIALS` 6 -> 9 | 6 | the ledger had 9 SPENT rows. Every fresh run deflated against a search two thirds its real size |
| `BUY_AND_HOLD` -> `ALWAYS_TRADE` | `BUY_AND_HOLD` | it re-enters every name every decision date and pays the round trip each time. A buy-once portfolio pays it twice in total |

## Exactly which published numbers this invalidates

**Every row of `reports/short_horizon/TRIAL-LEDGER.md`.** Specifically, in rows 1-9 and the NOISE
control row, these figures were computed by the repaired code paths and no longer reproduce:

- every **Sharpe** (ledger rows 1-9: -0.2162, -0.0888, -0.0041, -0.2357, -0.4533, +0.1456, +0.1146,
  +0.0201, +0.3518) — the compounding path and the annualisation both moved;
- every **deflated Sharpe** (0.026515, 0.059283, 0.094711, 0.023189, 0.004270, 0.191369, 0.167607,
  0.107263, 0.394441, and the hand-computed re-deflations 0.118147, 0.071891, 0.312642) — sample
  length, annualisation and trial count all moved;
- every **NOISE control DSR** (medians 0.0000 / 0.1615 / 0.5504, min 0.3197, max 0.7063) — the
  control runs the identical harness, so it moved identically. **The control's conclusion is
  unaffected in direction**: it was never about the level, it was about noise scoring in the same
  range as the candidates, and nothing here changes that comparison's construction;
- every **trade count and exposure for `CANDIDATE`** (379, 755, 35150, 58, 289, 35425, 380, 9419,
  29791) — fold 0 now holds cash, and later folds use different thresholds;
- the **C1 selected thresholds** (0.020 for holds 1 & 2, 0.000 for hold 3) — that was the pooled
  choice, which is now disclosure only and is not what scores the candidate;
- every reference to **`Buy&Hold`** (+0.4922, +0.4947) — the baseline is renamed `ALWAYS_TRADE`
  because that is what it always was.

`mean_net_return_per_decision` and `hit_rate` are **not** affected by the compounding change — they
never had the overlap problem. They do move for `CANDIDATE` because the applied threshold changed.

## What this does not decide

**Whether re-running the nine declared trials spends new ordinals is this record's owner's call, not
the filer's.** The case for "no" is that these are the same pre-declared trials remeasured with a
corrected instrument, not a new search, and the ledger's binding rule is about *adding* trials after
seeing results. The case for "yes" is that a re-run produces fresh numbers a reader could select
among. I have not run any trial and have written nothing to the ledger.

**No trial was run, no ordinal spent, no ledger row added or edited, no holdout touched.** The
repaired code has not been executed against the real corpus by me at all — only against fixtures.

## Verification of the repair itself

- `tests/test_short_horizon_portfolio_ledger.py`, 13 tests: the tranche ledger is a no-op at hold 1,
  compounds over blocks at hold 3, drops and counts a partial block, keeps exposure <= 1, and the
  past-only calibration publishes a per-fold basis with fold 0 in cash.
- `tests/test_short_horizon_trial_count.py`, 4 tests: `DECLARED_TRIALS` is read from source and
  compared against SPENT rows parsed from the ledger, so this cannot silently drift again.
- `tests/test_short_horizon_evaluation.py`: 18 pass, updated for the rename.
- Full suite **1,519 passed**. `ruff check` and `ruff format --check` clean across 671 files.
  `mypy src launcher.py scripts` clean across 208 files.

## Suggested next action, for the owner to accept or reject

Re-run the nine declared trials with the repaired evaluator and append the corrected figures beside
the originals rather than replacing them, so the size and direction of each correction stays visible.
The direction is predictable but the magnitude is not: the compounding fix lowers total return and
drawdown, the sample-length fix lowers DSR, the trial-count fix lowers DSR, and the annualisation fix
moves it by `sqrt(held_sessions)` in a direction that depends on the sign of the Sharpe.
