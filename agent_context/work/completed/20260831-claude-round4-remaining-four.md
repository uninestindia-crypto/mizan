# Active work: the four items round four left open

STATUS: COMPLETED
OWNER: Claude Code
TOOL: Claude Code
STARTED_UTC: 2026-08-31T15:30:00Z
STARTING_REVISION: cc92dd9a
WORKTREE_OR_BRANCH: D:\quant_system on main

## Objective

Close the four items from `.launch/reports/RED-TEAM-20260830-ROUND4.md`, per the plan at
`agent_context/handoffs/20260831-round4-remaining-repairs.md`. All four fire at session 11, the
first rebalance, roughly 2026-09-14.

1. **P1-3 (Blocker)** `rebalanced=rebalancing` records the *intent*. A rebalance in which every
   order was refused is persisted as one that happened, resetting the hold clock on an unchanged
   book. The plan notes a second case the obvious fix would miss: a rebalance that legitimately
   fills nothing because the selection equals the current book must also not reset the clock.
2. **P2-5** Risk marks to market, sizing still measures cost: `deployable =
   portfolio.ledger_funding()` at `:752`, forty lines from the marked baseline. On a drawn-down
   book that over-allocates and silently drops a selected name.
3. **P2-6** The halt reaches the exit code and console but not the markdown report or
   `live_paper_status.json`, which still read PASS and COMPLETED. Round three's P2-1 belongs with
   it: a session refused at the exit-8 gate writes no status update at all, so the dashboard serves
   the last completed session indefinitely.
4. **P2-7** `test_the_governor_is_seeded_from_marked_equity_not_a_cost_figure` asserts
   `"ledger_funding" not in ast.unparse(...)`; at `46c7bb67` the defect was written through a local,
   so the check passes against the very commit it names. Four of five mutants survive. **Third
   near-worthless test from me in two rounds** -- the replacement must be mutation-tested before it
   is claimed to work.

## Non-goals

- Round four's other P2s and P3s.
- The auto-sync behaviour. Real, and a separate change.

## Owned paths

- scripts/run_paper_pilot_session.py
- tests/test_paper_pilot_carried_session.py
- tests/test_paper_portfolio.py
- agent_context/work/active/20260831-claude-round4-remaining-four.md

## Blockers and conflicts

A peer session commits to `run_paper_pilot_session.py` concurrently (`88b78b9d`, `416f560c`).
Re-read before and after editing. Notices already raised for the Antigravity claim on this path.

## Current step

Implementing.

## Commands and outcomes

```
ruff check . / ruff format .  -> clean, 527 files
mypy src                      -> Success, 141 source files
pytest -q                     -> 1184 passed (was 1181)
all three entry points        -> import clean
```

## Mutation evidence for P2-7

The point of this item was that two previous versions of the test were worthless. The replacement
was mutation-tested **before** being claimed to work, which is what the plan required:

```
M1  verbatim P1-1 (seed from ledger_funding)      : KILLED
M1b P1-1 via a local (what defeated the old test) : KILLED
M2  seed from zero (disables the daily rule)      : KILLED
M3  seed from the carried peak                    : KILLED
M4  drop the carried trailing peak                : KILLED
```

An intermediate attempt is worth recording because it failed in a new way. Replacing the AST check
with a *behavioural* test of `PreTradeRiskGovernor` passed cleanly and killed **none** of the
mutants: it exercised the governor, while the defect is in the runner's wiring, so mutating the
runner could not fail it. That was the fourth worthless test in this sequence. The working version
resolves local names through their assignments -- following `opening_equity = ledger_funding()` to
`initial_equity=opening_equity` -- which is the difference between checking spelling and checking
meaning, and is exactly what the original check omitted.

## Repaired

| # | Repair |
|---|---|
| P1-3 | `executed_rebalance` replaces `rebalancing` at the persistence call. A rebalance counts only if something filled **or** the new selection equals the current book -- the second clause matters, because a re-rank that legitimately keeps everything is a completed rebalance and its clock should reset. A refused rebalance logs the counts and carries the clock forward |
| P2-5 | The marked opening equity is computed once, above both consumers. Sizing and the risk baseline now read the same number; they previously derived their own, forty lines apart, and only one was corrected |
| P2-6 | The markdown report leads with `RISK KILL SWITCH FIRED` / `SESSION ABORTED` above the figures, and the final `live_paper_status.json` writes `HALTED` / `ABORTED` with reasons instead of an unconditional `COMPLETED` |
| P2-7 | Replaced with a name-resolving AST check, mutation-tested against five mutants |

## Still open

Round four's remaining P2s and P3s, and the auto-sync committing whatever is in the tree.

## Next safe action

Round five, against everything since `46c7bb67`.
