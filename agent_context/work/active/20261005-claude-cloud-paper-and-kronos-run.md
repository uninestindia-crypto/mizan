# Active work: cloud paper runner and Kronos trial 10 in the cloud

STATUS: ACTIVE  
OWNER: Claude Code session (cloud container), on founder instruction 2026-10-05 ("go ahead with your proposal")  
TOOL: Claude Code  
STARTED_UTC: 2026-10-05T19:30:00Z  
STARTING_REVISION: eaba6da92c018a31160baa9f22d39a9d4fbe43fe  
WORKTREE_OR_BRANCH: `/home/user/mizan` (cloud container), branch `claude/dazzling-brown-yn5qu3`, restarted from `main` after
PR 1 and PR 2 merged. No worktree.

## Objective

Founder decision, 2026-10-05: run the platform in the cloud, with the Upstox token set there by the founder. Agreed
proposal, in order:

1. A cloud runner for the paper books that already exist. **No model change.**
2. Run **Kronos zero-shot, short-horizon trial 10**, exactly as declared in `reports/kronos_trial/TRIAL-LEDGER.md`, in
   the cloud, and report the result whatever it is.
3. **Do not retrain Mizan.** Recorded reason: 101 governed trials and 10 short-horizon trials found no edge after real
   costs; another run spends a multiplicity ordinal and cannot create one; both laptop books are a frozen system test
   until 2026-10-28 (`20260924-NOTICE-paper-books-system-test-running.md`).

## Owned paths

- `agent_context/work/active/20261005-claude-cloud-paper-and-kronos-run.md` (this record)
- `scripts/cloud_paper_session.py` (new)
- `tests/test_cloud_paper_session.py` (new)
- `.github/workflows/cloud-paper-session.yml` (new)
- `docs/CLOUD_PAPER_RUNBOOK.md` (new)
- `reports/kronos_cloud_run/**` (new): every output of the cloud Kronos run. Nothing is written under
  `reports/kronos_trial/**`, which `20260928-claude-kronos-trial.md` claims; its scripts take `--out`.
- `agent_context/work/active/20261005-NOTICE-kronos-trial-run-from-cloud.md` (new, additive)

## Read but not edited (claimed elsewhere)

- `scripts/generate_kronos_forecasts.py`, `scripts/run_kronos_trial.py`, `tests/test_kronos_trial.py`,
  `reports/kronos_trial/**`: `20260928-claude-kronos-trial.md` (ACTIVE). Run, never edited.
- `scripts/run_scheduled_paper_session.py`, `scripts/run_paper_pilot_session.py`: imported or invoked, never edited.

## Non-goals

- No change to either laptop paper book, its tasks, its state, or what it trades.
- No retraining, no new candidate, no threshold or horizon search. No second Kronos variant after a result.
- No live-money order routing (T4) and no broker account access. The token is read-only market data.
- No secret in the repository. The Upstox token lives only in the cloud environment's secrets.

## Plan

1. Record and claims. DONE.
2. Kronos environment in the scratch directory (not in the repo): CPU torch, pinned code and weights, SHA verified.
3. Kronos dry-run, then timing probe on synthetic bars, then the declared compute-scope rule.
4. Cloud runner: wrapper, state persistence, workflow, tests with a fake feed, runbook.
5. Forecast and score Kronos once. Report.
6. Gates (ruff, format, strict mypy `--platform win32`, tests), commit explicit paths, push, handoff.

## Current step

HANDOFF to a new cloud session that has the Upstox credential (founder instruction 2026-10-05: the first session
cannot see environment changes made after it started). State when this commit was made:

- DONE: record; Kronos pinned code cloned and its three SHA-256 values match the ledger; the three weight sets
  downloaded at the declared revisions and their SHA-256 values match the ledger; generator `forecast --dry-run`
  works on Linux (45 names, 529 decision dates, 23,805 forecasts); `reports/kronos_cloud_run/run_generator.py`
  launcher (disables only the laptop pause rule); `scripts/cloud_paper_session.py` written (`check`, `run`).
- NOT DONE: Kronos timing probe (was running, scratch output lost with the machine; rerun it), compute-scope
  choice and its Amendment, forecast, scoring; tests for `cloud_paper_session.py`; the workflow file; the
  runbook; gates; the real-feed token check. Scratch (venv, code, weights) lives outside the repo and must be
  rebuilt: pip CPU torch, `git clone shiyu-coder/Kronos` at 67b630e6, `snapshot_download` at the three
  declared revisions, write `pinned-revisions.json`.

## Decision rationale

- **Separate state.** The laptop flagship's live state is `logs/paper_runs/portfolio_state.json` (untracked). A cloud run
  starts from a fresh checkout with no such file, so it creates its own book; it cannot overwrite the laptop's. Both
  books then run the same frozen model, and the founder retires whichever host he chooses.
- **Same trial, not a new one.** The Kronos run in the cloud uses the same frozen declaration, code commit, weights and
  data. If the laptop also finishes it, that is the same trial run twice, so only one result is scored and published.

## Commands and outcomes

| Command | Result | Evidence/notes |
|---|---|---|
| | | |

## Files changed

- `scripts/cloud_paper_session.py` (new, untested)
- `reports/kronos_cloud_run/run_generator.py` (new)
- this record

## Blockers and conflicts

- The founder has not said whether the laptop's Kronos run produced forecasts. The repo shows the trial as "not yet run"
  and holds no forecast file.
- Upstox token not yet set in the cloud environment; the first real-feed run depends on it.

## Stop point

Committed and pushed to `claude/dazzling-brown-yn5qu3` as a work in progress. Not merged, no PR.

## Next safe action

In the new session: run `python scripts/cloud_paper_session.py check` first (proves the token, places nothing).
