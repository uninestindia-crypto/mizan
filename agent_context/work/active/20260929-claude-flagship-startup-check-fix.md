# Active work: flagship start-up check takes hours; fix it and start today's session

STATUS: ACTIVE  
OWNER: Claude Code session, on founder instruction 2026-09-29 ~10:10 IST: "Fix it, run today"  
TOOL: Claude Code  
STARTED_UTC: 2026-09-29T04:45:00Z  
STARTING_REVISION: e787ac462fe9c9d188ab8974109c3bdbd59b46b2  
WORKTREE_OR_BRANCH: `D:\quant_system` on `main` (shared checkout, disjoint paths with written claims)

## Objective

The restarted flagship book had not completed one session by 2026-09-29. One cause is in the code:
`newest_cached_bar_date()` in `scripts/run_scheduled_paper_session.py` verifies and parses **every**
dataset in the NIFTY 500 bars cache before the refresh starts. Make that check read only each
instrument's newest dataset. Then start today's session through its own scheduled task.

## Owned paths

- `scripts/run_scheduled_paper_session.py`. No active record owns it; see
  `20260918-CLAIM-paper-session-keep-awake-branch.md`, line 27.
- `tests/test_scheduled_paper_session_newest_bar.py` (new)
- `agent_context/work/active/20260929-claude-flagship-startup-check-fix.md` (this record)
- The notice, decision addendum and handoff this session filed for the system test:
  - `agent_context/work/active/20260924-NOTICE-paper-books-system-test-running.md`
  - `agent_context/decisions/20260923-paper-books-system-test-end-date.md`, additive section only
  - `agent_context/handoffs/20260924-claude-paper-books-restart-handoff.md`

## Non-goals

- Nothing the book trades changes: no model, rule, universe or sizing change.
- No task settings change. Today's session is started with `Start-ScheduledTask` on the existing
  task, the same command and wrapper as 09:00. The founder authorised the manual start.
- Nothing in the evidence store is deleted or rewritten.

## Evidence

The time from "scheduled paper session for" to "newest cached bar before refresh" in each day's log
(`logs/archive/paper-books-20260923/at-restart/flagship/`):

| Day | Seconds in the check | Datasets in the store (approx.) |
|---|---:|---:|
| 2026-09-01 | 70 | ~1,250 |
| 2026-09-03 | 149 | ~1,750 |
| 2026-09-08 | 822 | ~3,250 |
| 2026-09-11 | 1,057 | ~4,750 |
| 2026-09-18 | 1,536 | ~6,750 |
| 2026-09-21 | **13,880 (3 h 51 min), machine awake all day** | ~7,250 |
| 2026-09-29 | not reached | **8,236**, 474.5 MB |

- Every refresh adds 499 complete datasets, and the store never deletes. `list_verified` returns
  every verified dataset **with all its records at once**, so both the work and the memory held
  grow with each day. The cost grew faster than the dataset count.
- The restarted book's runs never got past this step:
  - 2026-09-25: started 20:16 as a catch-up and killed at a user shutdown, 0xC000013A.
  - 2026-09-28: started 10:28 as a catch-up. Nothing was logged for 84 minutes, then it was killed
    by a Start-menu shutdown at 11:52, 0xC000013A. The battery had died at 06:05 (event 6008).
  - 2026-09-29: 09:00 was missed while the machine was hibernated until 09:53.

## Plan

1. Fix: list manifests only, which reads no blob bodies. Keep the newest-created dataset per
   `provider_instrument_id`, and verify and parse only those, one at a time.
2. Unit tests. Time the new check against the real cache.
3. Gates: targeted tests, ruff, ruff format and strict mypy.
4. `Start-ScheduledTask "QuantOS Mizan Paper Session"`, then watch the log through the refresh.
5. Record the new dates; the test end moves to Thu 2026-10-29. Move the end-of-test reminder to
   match. Commit own paths.

## Current step

1.

## Decision rationale

- **Semantics.** The old check took the maximum date over every dataset ever stored. A refresh
  that wrote a truncated dataset could therefore never lower it, so the existing
  "newest cached bar went backwards" refusal was unreachable. Reading each instrument's newest
  dataset makes that refusal reachable. It reports what the newest data actually holds.
- **The date still comes from verified records**, not from a manifest's `received_range` claim.
  The manifest only selects which dataset to verify.

## Commands and outcomes

| Command | Result | Evidence/notes |
|---|---|---|

## Files changed

- This record.

## Blockers and conflicts

- The laptop is on battery (62% at 09:59 IST). The founder was asked to plug in.
- Another agent's full `pytest` run started at 10:00 IST and competes for CPU.

## Stop point

Record created.

## Next safe action

Edit `newest_cached_bar_date()`.
