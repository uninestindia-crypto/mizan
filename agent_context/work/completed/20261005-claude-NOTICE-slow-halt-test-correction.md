# NOTICE (additive): correction to two statements in `20261005-claude-paper-books-auto-update.md`

STATUS: COMPLETED (a correction, nothing to do)  
OWNER: Claude Code session "Installer usability and updates" (562e52)  
UTC: 2026-10-05  
AFFECTS: `agent_context/work/completed/20261005-claude-paper-books-auto-update.md` ("Commands and outcomes", row "Gate in this dev checkout", and
"Not done", last bullet). That record is immutable, so this notice carries the correction instead of an edit.

## What I wrote, and what was wrong

I wrote that `tests/test_paper_pilot_carried_session.py::test_halted_portfolio_refuses_trading_at_startup`
"does not finish in 20+ minutes" in the dev checkout and is "instant on a clean tree", and that the full suite "cannot finish" here.

Both are wrong:

- The test is **slow everywhere**, not only in the dev checkout. `data/evidence/market-cache/**/store` is tracked in git (27,164 files in the
  `nifty500-refresh` store alone), so a clean clone holds identical data (I compared tracked and on-disk file counts: equal). The
  "tree with no market data" I contrasted it with does not exist for this repository.
- It **finishes**. The manager session (`20261005-claude-manager-antigravity-backlog.md`) measured it passing alone in about 13.5 minutes.
  I killed my own run at about 20 minutes and read a slow test as a hang. My 19 min 55 s clean-clone full run is consistent with that: the
  clone passed it, inside the 20 minutes.

## What was right

- The stack I captured is correct: `run_paper_pilot_session.py:1520` `load_mizan_cross_section` -> `EvidenceStore.list_verified` ->
  `_verify_blobs` (`evidence/store.py:437`). The halt check that the test is about is at `run_paper_pilot_session.py:1671`, after that load.
- My gate numbers at `51f0860ed` stand as measured: ruff and format clean, strict mypy clean (258 files), 2333 passed, 1 skipped.

## Where the fix lives

The manager session already built and independently reviewed the fix as ticket W2-T1 (stub `load_mizan_cross_section` in that one test;
13.5 min to 0.07 s), uncommitted on branch `antigravity/hermetic-halt-test`. I did not edit or commit it: it is another agent's
change on a path that record claims.
