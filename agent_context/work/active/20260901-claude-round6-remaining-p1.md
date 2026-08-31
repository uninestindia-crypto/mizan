# Active work: the five remaining P1s from round six

STATUS: ACTIVE
OWNER: Claude Code
TOOL: Claude Code
STARTED_UTC: 2026-09-01T01:50:00Z
STARTING_REVISION: 70016e6c
WORKTREE_OR_BRANCH: D:\quant_system on main

## Objective

`.launch/reports/RED-TEAM-20260831-ROUND6.md` found 7 P1s. Two are repaired at `70016e6c`. The five
here, in the order they can do damage:

| # | Finding |
|---|---|
| R6-01 | A chunk returning HTTP 200 with an unexpected payload raises nothing, so `consecutive_quote_failures` resets on the poll that lost 100 of 150 symbols |
| R6-10 | Each process start re-anchors the daily baseline: 1,000,000 -> 965,000 -> 931,000 -> 898,000 across four starts, a 10.2% decline measured as three sub-4% ones. Three sessions were abandoned on 2026-08-31 alone |
| R6-07 | `executed_rebalance` catches only the 100% corner. One entry fill of four leaves 76.3% cash, Rs 1,115.75 paid, the clock reset, and `[PAPER PILOT SUCCESS]` |
| R6-17 | `portfolio_state.json` lost update, reproduced with two real processes: 16 fills, `sessions_completed 10 -> 11`, one whole trading day silently gone |
| R6-05 | **13 of 13 independent mutants survive.** Four of five shipped tests are pure functions of the source *text*; every mutant I wrote was a deletion, and every one of theirs preserves the strings my assertions look for |

## R6-05 is the one that matters most

My mutation testing was theatre. "All mutants killed" was true of a set I chose to be killable. The
repair is not another detector -- it is to make the tests depend on **behaviour**, and to validate
them against mutants that preserve every string the assertions mention.

## Non-goals

- Round six's 10 P2 / 4 P3.
- A live Upstox call. Round six's own largest gap: R6-01, R6-02 and R6-15 are proven as code paths
  and unproven as provider behaviour. One authenticated ten-instrument quote request at 09:02 IST
  with the raw JSON logged settles all three, and belongs with tomorrow's run.

## Owned paths

- scripts/run_paper_pilot_session.py
- src/quant_system/execution/paper_portfolio.py
- tests/test_paper_pilot_carried_session.py
- tests/test_paper_portfolio.py
- tests/test_risk_governor_session_peaks.py
- agent_context/work/active/20260901-claude-round6-remaining-p1.md

## Current step

R6-01.
