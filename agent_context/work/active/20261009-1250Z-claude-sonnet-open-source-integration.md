# Active work: learn from Qlib and PyBroker and integrate what the platform is missing

STATUS: COMPLETED  
OWNER: Claude Code (Sonnet 5.5), founder session  
TOOL: Claude Code  
STARTED_UTC: 2026-10-09T12:50:00Z  
STARTING_REVISION: `09cfa6b0a4bd15a54a88b82095f558556a33fa1e` (continued from `74517c3f8`, see the worktree claim)  
WORKTREE_OR_BRANCH: branch `claude/open-source-integration`, worktree claimed in the install root by `20261009-1340Z-claude-sonnet-open-source-integration-worktree.md`

## Objective

GOAL_LINE: G5 (honest evidence) and G6 (real benefit to retail users), serving G1.

Founder instruction, 2026-10-09: "learn and integrate it so we can use it in our platform, learning is not copying, and
Qlib we can copy" (about the two projects under `Learn from open source codebase/`), then "continue complete it all so it
can be run tested and used". My first pass looked at them only against the broker feature and found nothing; that missed
the instruction. This is the real pass.

## What the survey found (2026-10-09)

Already in the platform before this work: Alpha158 factor formulas, a small dataset class and pooled IC/RankIC
(`research/qlib/`), the whole PyBroker engine as a vendored copy (`src/pybroker`), an adapter, a gap-flagging market index,
a deflated-Sharpe Lab verdict.

Missing, and now added:

1. **A defect in the existing bridge, fixed.** `QlibEvaluationReport.ic_ir` was `ic / 0.1`, a made-up constant, and
   `scripts/train_literature_alpha_model.py` printed it as "Information Ratio". Qlib's real definition (mean of the per-date
   IC over its spread across dates) is now used; with fewer than 3 dates the answer is `None` (not measurable).
2. **Qlib's per-date evaluation, copied** (`qlib/contrib/eva/alpha.py`, MIT) into `research/qlib/alpha_eval.py`, plus a new
   `ic_summary` (mean, spread, information ratio, t-statistic, share of positive dates).
3. **Qlib's shrinkage risk models, copied** (`qlib/model/riskmodel/{base,shrink}.py`, MIT) into `research/qlib/riskmodel.py`,
   and corrected where testing against the papers found upstream faults: the OAS parameter did not follow Chen et al. 2010
   eq. 23, the caller's returns were rescaled in place, a flat series made the whole matrix NaN.
4. **Portfolio risk, user-facing** (`server/v2/portfolio_risk.py`): the typical yearly swing of the whole portfolio, how many
   independent holdings it behaves like (never more than the number owned), and each holding's share of the risk next to its
   share of the money. Routes `GET /api/v2/portfolio/risk` and `GET /api/v2/broker/risk`; a card on Portfolio for the hand-entered
   holdings and under the broker holdings; a short version for the assistant, in its built-in answers and in the portfolio and
   broker tools. It uses the market index's data-break flags (days with a known break are left out and counted), leaves out a
   holding with too little history rather than shortening the others' window, and says plainly when nothing has moved.
5. **PyBroker's bootstrap idea, written fresh** (its licence is Apache 2.0 with the Commons Clause): `lab/ranges.py`, a seeded
   stationary bootstrap giving the middle 90 percent range of Sharpe, yearly return and worst fall. It is in every Lab result
   (`ranges`) and shown on the Lab run screen. The verdict is untouched.
6. **Licence compliance:** `THIRD_PARTY_NOTICES.md` carries Qlib's MIT text and records the open PyBroker question.

Rejected on purpose, with reasons in `research/qlib/README.md`: Qlib's deep-learning and tree models (they need torch or
lightgbm, which the factory-new installer does not carry, and each new model trial needs its own dated declaration under GOAL
tripwire 3); Qlib's data health script (the market index already does more, with corporate actions); Qlib processors and Alpha360
and `TopkDropoutStrategy` (no consumer in the platform: dead code, and the only consumer would be a running paper book, which
tripwire 8 forbids changing).

## Owned paths

All inside the worktree. New: `research/qlib/{riskmodel,alpha_eval}.py`, `server/v2/portfolio_risk.py`, `lab/ranges.py`,
`frontend/src/components/{RiskCard,LabRanges}.tsx` (+ tests), `THIRD_PARTY_NOTICES.md`,
`tests/test_{qlib_riskmodel,qlib_alpha_eval,portfolio_risk,portfolio_risk_routes,lab_ranges}.py`.
Edited: `research/qlib/{adapter,__init__,README}`, `scripts/train_literature_alpha_model.py`,
`server/v2/{router,broker_routes,copilot_wiring}.py`, `broker_view/summary.py`, `copilot/{rules,tools_user}.py`, `lab/runner.py`,
`frontend/src/pages/{Portfolio,LabRun}.tsx`, `frontend/src/components/BrokerAccountCard.tsx`,
`frontend/src/lib/{queries,types}.ts`, and two existing tests.
Claimed paths are covered by `20261009-NOTICE-open-source-integration-under-retail-redesign-claim.md`.

## Non-goals

No new model trial, sweep or retrain (tripwire 3). No change to what a paper book trades (tripwire 8). No new dependency. No
change to the vendored `src/pybroker`. No broker call. No commit, push, merge or release.

## Decision rationale

- Copy where the licence allows and the code is pure NumPy or pandas (Qlib, MIT); learn and rewrite where it does not
  (PyBroker, Commons Clause). Every copied line is named, with what was changed and why, at the top of its module.
- Test copied code against the published formulas, not against itself: independent restatements of Ledoit-Wolf and OAS, and a
  simulation that a shrunk estimate lands closer to a known true covariance than the raw sample (and that a 90 percent
  bootstrap range covers the truth most of the time).
- The risk and the ranges are descriptions of the past, and the screens say so in words. Nothing says buy, sell or should.
- An optional extra (the risk picture inside the assistant's answers) must never take the main answer down: it is guarded and
  logs only the kind of error.
- A real run against the real market index found a wording fault the unit tests did not: negatively correlated holdings
  scored above their own number, and a perfect hedge was reported as "not enough history". Both are fixed with tests.

## Commands and outcomes

| Command | Result | Evidence/notes |
|---|---|---|
| `pytest tests/` (full, in the worktree, a clean checkout, nothing else running) | PASS | 4,344 passed, 6 skipped (no symlink privilege on this laptop; one POSIX-only timezone test; two oas combinations Qlib itself does not support), 0 failed, 3m09s |
| New and changed Python tests, reverse file order, twice | PASS | 298 passed, 2 skipped each time |
| `mypy src launcher.py scripts` (strict) | PASS | "Success: no issues found in 389 source files" |
| `ruff check` and `ruff format --check` on the 20 Python files changed | PASS | repo-wide `ruff check .` is red for other trees (see Blockers) |
| `npm run typecheck`, `npx vitest run`, `npm run build` | PASS | 476 tests in 37 files, including the existing No-Terminal guard |
| `detect-secrets scan` on the 32 changed files | PASS | no findings |
| Real server from the worktree, isolated state, shared fixture market store, real browser pane | PASS | Portfolio shows the risk card from `/api/v2/portfolio/risk` (219 sessions); a Lab run carries `ranges` and its page shows "How much of this could be luck"; the assistant's built-in answer carries the risk lines; no console errors |
| `scripts/audit-disk-layout.ps1` | PASS | |
| `scripts/audit-agent-claims.ps1` | worktree and branch both `OK` | the remaining findings are other agents' legacy records |
| `scripts/release_status.py` | no release due | nothing is committed |

Two things the run taught, both fixed or recorded:

- A first full run in the worktree showed 4 supervisor tests failing. Cause: this shell sets `PYTHONDONTWRITEBYTECODE=1`, so a fresh
  checkout never gets compiled `.pyc` files and a spawned worker took 4.5 s to start against the supervisor's 5 s heartbeat limit
  (1.4 s on `main`, which has cached files). With bytecode caching on, all 10 pass. It is not a code defect, but those tests are
  fragile on a fresh checkout under that setting.
- My own change had also added scipy and pandas to every server and worker start-up (`portfolio_risk` imported the Qlib
  package at the top). That import is now lazy, so only a risk question pays for it.

## Files changed

See "Owned paths".

## Blockers and conflicts

- The repository-wide `ruff check .` is red for reasons outside this work: about 2,184 errors under `skills/` and thousands more
  in the tracked "Learn from open source codebase" folder, which `pyproject.toml` does not exclude. Every file this work touched
  is clean.
- Running the test suite rewrites tracked files (`data/pybroker_upstream_state.json`,
  `agent_context/handoffs/PYBROKER-UPDATE-BRIEFING.md`, `data/evidence/models/quant_slm_latest_signals.json`). They were put back
  with `git checkout`. Tests should not write into tracked files; that is a separate fix.

## Stop point

Everything planned is built and verified; nothing is committed.

## Next safe action

The founder decides: commit this branch (explicit paths, `feat(research): Qlib risk models and per-date evaluation, portfolio
risk and Lab ranges`), merge it after `feature/broker-view-phase1-and-qlib`, then `python scripts/release_status.py`.
