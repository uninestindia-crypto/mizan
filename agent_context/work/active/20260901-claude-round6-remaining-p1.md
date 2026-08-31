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

## Commands and outcomes

```
ruff check . / ruff format .  -> clean, 535 files
mypy src                      -> Success, 141 source files
pytest -q                     -> 1202 passed (was 1194)
```

Mutation results, run against **reproductions of the actual defects** rather than deletions:

```
R6-01  true original silent skip / log-only / status-key-only   -> 3 killed
R6-10  in-loop anchor disabled / every step / restart ignores the date / boot-time figure -> 4 killed
R6-07  one entry fill counts / exits alone count / threshold 0 / any overlap -> 4 killed
R6-17  unconditional overwrite / compare against the wrong thing -> 2 killed
```

## Two of my own tests were caught by mutation before shipping

- **R6-01, twice.** The first version used a single chunk and asserted the exception *type*: both
  the fixed and the broken code raise there, because when every chunk is bad `results` is empty and
  the older "no quotes for any" guard fires. It passed against a faithful reproduction of the
  defect. The second missed a status-only check; the payload that separates them is an error
  envelope that still carries a `data` key.
- **R6-07.** The first version asserted the flag's source text. Extracting `rebalance_executed` and
  driving the real shapes -- all exits 0.0, one of four 0.25, keep-everything 1.0, 97 of 100 0.97 --
  is what kills the historical originals.

## Repaired

| # | Repair |
|---|---|
| R6-01 | A non-success 200 is a failed chunk, so the retry budget sees it |
| R6-10 | `daily_anchor_on` / `daily_anchor_equity` persist (schema v4); a restart on the same date reuses the morning's baseline |
| R6-07 | `rebalance_executed` judges coverage of the selection, `MIN_REBALANCE_COVERAGE = 0.8` |
| R6-17 | `save_portfolio` takes an optional prior hash and refuses to overwrite a file that changed since the session loaded. Per-process staging filename |

## R6-17 is narrower than it sounds, deliberately

There is still **no lock**: two sessions can overlap. What is prevented is the silent *loss* -- the
second to finish now refuses and says so, leaving the other session's day intact and both sets of
artifacts on disk. Preventing the overlap needs a lock and a decision about what the loser should
do, which is a design question rather than a defect fix.

## Still open

R6-05: four of five shipped tests from the previous round are functions of the source text, and 13
of 13 independent mutants survived them. Two more of those were replaced here by extraction and
behavioural testing; the remainder are not yet re-examined.

Round six's 10 P2 / 4 P3 also stand.
