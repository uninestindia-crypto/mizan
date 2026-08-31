# Red Team round six — adjudication of the round-five repairs

STATUS: COMPLETED
AGENT: Claude Code (Red Team, independent — authored none of the work under test)
STARTED_UTC: 2026-09-01
STARTING_REVISION: d6fde28b
BRANCH: main (shared checkout, read-only against source)
WORKTREE_OR_BRANCH: install root D:\quant_system, branch main

## Objective

Execute `.launch/RED-TEAM-BRIEF-20260831-ROUND6.md`: adjudicate nine claims against commits
`739859a1..d6fde28b`. Sixth independent adjudication.

## Owned paths

- `.launch/reports/RED-TEAM-20260831-ROUND6.md`  (created by me, exclusively mine)
- `agent_context/work/active/20260831-redteam-round6.md`  (this record)

## Non-goals

- No repairs. No commits. No edits to any source file.
- No modification of `data/evidence/`, `logs/paper_runs/`, `.env`.
- No worktree/branch creation or removal.

## Plan

1. Skeleton report with all nine claims NOT TESTED. (done first, per brief)
2. Claim-by-claim, rewriting each section immediately on completion.
3. Triage order if budget short: 6, 8, 7.

## Scratch

Probe scripts under the session scratchpad directory, never in the repo.

## Current step

Skeleton written; beginning claim work.

## Outcome

STATUS: COMPLETED
FINISHED_UTC: 2026-09-01
ENDING_REVISION: d6fde28b (no commits made; no source file modified)

All nine claims adjudicated. Report at `.launch/reports/RED-TEAM-20260831-ROUND6.md`.

Result: 7 P1, 10 P2, 4 P3.

Headline findings:
- R6-04 (P1, Blocker) F23 left a fifth and sixth consumer of a missing quote, in
  `core/ledger.py:552`, reached from `run_paper_pilot_session.py:1233` and `:1388`. The second is
  outside the abort handler, so the session produces no report and never persists the book.
- R6-14 (P1) the 09:00 refresh authenticates with `UPSTOX_ACCESS_TOKEN`, whose expiry claim is
  2026-09-01 03:30 IST. The scheduled run refuses at exit 4 and no session happens.
- R6-17 (P1) `portfolio_state.json` has no lock and no compare-and-swap. Reproduced: two sessions,
  16 fills, one session recorded.
- R6-07 (P1) a rebalance filling one entry of four, leaving 76% cash, counts as executed.
- R6-05 (P1) 13 independently written mutants across all five fixes; 13 survivors. The same harness
  passes on HEAD and kills all 12 of the author's own mutants.
- R6-01 (P1) a chunk lost to HTTP 200 is not counted as a failed chunk, so the poll succeeds and the
  retry budget resets - the round-five F1 defect, reachable on the repaired code.
- R6-10 (P1) restarting a session re-anchors the daily drawdown baseline.

## Verification commands run

    .venv/Scripts/python.exe -m pytest -q            -> 1191 passed in 89.38s
    .venv/Scripts/python.exe -m ruff check .          -> All checks passed!
    .venv/Scripts/python.exe -m mypy src              -> Success: no issues found in 141 source files

## Files changed

- `.launch/reports/RED-TEAM-20260831-ROUND6.md` (new, mine)
- `agent_context/work/active/20260831-redteam-round6.md` (this record, mine)

Nothing else. `git status --short` confirms no source file, no `data/evidence/`, no
`logs/paper_runs/`, and no `.env` was touched. All probe scripts and all session runs were written
to the session scratchpad with `PORTFOLIO_STATE_PATH` and `output_dir` redirected there.

## Next safe action

Hand the report to the gate. Do not repair from this record; the report carries the reproductions.
The single cheapest next probe is item 1 of NOT PROBED: one authenticated ten-instrument
`market-quote/quotes` call at 09:02 IST with the raw JSON logged. It decides R6-01, R6-02 and R6-15.
