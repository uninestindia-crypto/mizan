# Active work: learn from Qlib and PyBroker and integrate what the platform is missing

STATUS: HANDOFF_REQUIRED (step 2 of 6 done; stopped by the founder's usage limit, not by a blocker)  
OWNER: Claude Code (Sonnet 5.5), founder session  
TOOL: Claude Code  
STARTED_UTC: 2026-10-09T12:50:00Z  
STARTING_REVISION: `09cfa6b0a4bd15a54a88b82095f558556a33fa1e`  
WORKTREE_OR_BRANCH: the install root (the Mizan checkout), branch `main`. No worktree, for the same reason as `20261009-1000Z-claude-sonnet-broker-view.md`, whose uncommitted files this work builds on (Portfolio screen, query hooks)

## Objective

GOAL_LINE: G5 (honest evidence) and G6 (real benefit to retail users), serving G1.

Founder instruction, 2026-10-09: "learn and integrate it so we can use it in our platform, learning is not copying, and
Qlib we can copy" (about the two projects under `Learn from open source codebase/`). My first pass looked at them only
against the broker feature and found nothing; that missed the instruction. This is the real pass.

## What the survey found (2026-10-09)

Already in the platform: Alpha158 factor formulas, a small dataset class and pooled IC/RankIC (`research/qlib/`), the
whole PyBroker engine as a vendored copy (`src/pybroker`, with its `eval.py` bootstrap) and an adapter, a gap-flagging
index, a deflated-Sharpe Lab verdict.

Missing, and worth having:

1. **A defect in the existing bridge.** `QlibEvaluationReport.ic_ir` is `ic / 0.1`, a made-up constant, and
   `scripts/train_literature_alpha_model.py` prints it as "Information Ratio". Qlib's real definition is the mean of the
   per-date IC divided by its standard deviation across dates.
2. **Qlib's shrinkage risk models** (`qlib/model/riskmodel/{base,shrink}.py`, pure NumPy, MIT): no covariance estimator
   in the platform other than the raw sample one. Gives a real "how your holdings move together" view for the retail
   Portfolio (hand-entered and the new broker holdings) and for the Copilot.
3. **Qlib's per-date evaluation** (`qlib/contrib/eva/alpha.py`, pandas, MIT): per-date IC, long-short return and
   precision, and signal autocorrelation (turnover honesty).
4. **PyBroker's bootstrap idea, written fresh (its licence is Apache 2.0 with the Commons Clause; learning, not copying):**
   the Strategy Lab shows point estimates only; ranges for Sharpe, annual return and worst fall would show how much of a
   result could be luck.

Rejected on purpose: Qlib's deep-learning and tree models (they need torch or lightgbm, which the factory-new
installer does not carry, and a new model trial needs its own dated declaration under GOAL tripwire 3); Qlib's data health
script (the platform's gap-flagging index already does more, with corporate actions); Qlib processors and Alpha360 (no
consumer in the platform: dead code); `TopkDropoutStrategy` (the only consumer would be a running paper book, which tripwire 8
forbids changing).

## Owned paths

New:

- `src/quant_system/research/qlib/riskmodel.py`, `alpha_eval.py`
- `THIRD_PARTY_NOTICES.md` (repository root; Qlib's MIT text, and PyBroker's licence and condition)
- `src/quant_system/server/v2/portfolio_risk.py`, `frontend/src/components/RiskCard.tsx` (+ test)
- `src/quant_system/lab/ranges.py` (+ the Lab screen's range lines)
- `tests/test_qlib_riskmodel.py`, `tests/test_qlib_alpha_eval.py`, `tests/test_portfolio_risk.py`, `tests/test_lab_ranges.py`

Small edits:

- `src/quant_system/research/qlib/adapter.py` (real per-date ICIR), `__init__.py`, `README.md`
- `scripts/train_literature_alpha_model.py` (print the real figure, or say it cannot be measured)
- `tests/test_qlib_bridge.py` (new expectations for the fixed ICIR)
- `src/quant_system/server/v2/router.py`, `broker_routes.py`, `copilot_wiring.py`, `src/quant_system/copilot/tools_user.py` (risk summary)
- `src/quant_system/lab/runner.py`, `stats.py` (ranges in the result)
- `frontend/src/pages/{Portfolio,LabRun}.tsx`, `frontend/src/lib/{queries,types}.ts`, `frontend/src/components/BrokerAccountCard.tsx`

Claimed by `20260928-claude-retail-redesign-build.md`: `server/v2/**`, `lab/**`, `frontend/**`. See
`20261009-NOTICE-open-source-integration-under-retail-redesign-claim.md`.

## Non-goals

- Any new model trial, sweep or retrain (tripwire 3). Any change to what a paper book trades (tripwire 8). Any new
  dependency. Any change to the vendored `src/pybroker` code. Calling a broker.

## Plan

1. Survey both projects against the platform. DONE.
2. Notice. Qlib notice file and the two Qlib modules, copied with fixes, test first.
3. Fix the bridge's ICIR with them.
4. Portfolio risk: engine, route, screen card, Copilot summary.
5. Lab ranges: engine, result, screen lines.
6. Gates, secret scan, audits, release status, close the record.

## Current step

Between 2 and 3. Done: the survey, this record, the notice, `research/qlib/riskmodel.py` (copied from Qlib, MIT, corrected)
with `tests/test_qlib_riskmodel.py`, and `THIRD_PARTY_NOTICES.md`. Not started: `alpha_eval.py`, the ICIR fix in
`adapter.py` and `scripts/train_literature_alpha_model.py`, the portfolio risk engine, route and card, the Lab ranges, the
README and `__init__` updates.

## Decision rationale

Two upstream defects were found by testing Qlib's code against the published formulas, and are fixed in the copy: the OAS
shrinkage parameter (wrong factor and sign against Chen et al. 2010 eq. 23) and in-place mutation of the caller's returns and
of a caller-supplied target. A flat series no longer turns the matrix into NaN. The platform's existing `ic_ir` is
`ic / 0.1`, a constant, and is printed as "Information Ratio"; the real figure is the mean of the per-date IC over its
standard deviation across dates.

## Commands and outcomes

| Command | Result | Evidence/notes |
|---|---|---|
| `git status`; `git worktree list` | working tree holds the uncommitted broker-view work | nothing of anyone else's is touched |
| `pytest tests/test_qlib_riskmodel.py tests/test_qlib_bridge.py` | PASS | 46 passed, 2 skipped (oas with a non-constant target, as Qlib) in the new file; the existing bridge tests still pass |
| `ruff check`, `ruff format`, strict `mypy` on `riskmodel.py` and its test | PASS | |

## Files changed

- New: `src/quant_system/research/qlib/riskmodel.py`, `tests/test_qlib_riskmodel.py`, `THIRD_PARTY_NOTICES.md`, this record and
  `20261009-NOTICE-open-source-integration-under-retail-redesign-claim.md`.
- Nothing else yet. `riskmodel.py` has no caller yet, so it is not wired into the platform.

## Blockers and conflicts

None known.

## Stop point

`riskmodel.py` and its tests are green; nothing is committed; nothing is wired in.

## Next safe action

Plan step 3: copy `calc_ic`, `calc_long_short_return`, `calc_long_short_prec` and `pred_autocorr` from
`qlib/contrib/eva/alpha.py` into `research/qlib/alpha_eval.py` (test first, drop the joblib and logging imports), then use the
per-date IC in `QlibModelAdapter.evaluate` so `ic_ir` is real (or `None` when there are fewer than 3 dates), and fix the script
that prints it. Then plan steps 4 and 5. Files outside `research/qlib/` need the NOTICE already filed.
