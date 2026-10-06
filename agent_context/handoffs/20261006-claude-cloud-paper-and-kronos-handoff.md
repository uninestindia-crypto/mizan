# Handoff: cloud paper runner built, Kronos trial 10 run and scored, goal file added

STATUS: READY_FOR_ADOPTION  
FROM: Claude Code (cloud container)  
TO: unassigned (founder decisions listed below)  
DATE_UTC: 2026-10-06  
ACTIVE_RECORD: `agent_context/work/active/20261005-claude-cloud-paper-and-kronos-run.md`  
BRANCH: `claude/dazzling-brown-yn5qu3`, pushed. **No pull request, not merged**, as the founder asked.

## Objective and acceptance criteria

Founder decisions of 2026-10-05: (1) a cloud runner for the existing paper books with **no model change**;
(2) run Kronos zero-shot short-horizon trial 10 in the cloud exactly as declared and report the result
whatever it is; (3) **do not retrain Mizan**. Both laptop books stay a frozen system test until 2026-10-28.
Mid-session addition: a goal file in the codebase so every agent and staff member knows the final result.
Goal lines served: G4, G1 (`agent_context/GOAL.md`).

## Completed

- **Token check, against the real feed:** passes. INFY, RELIANCE and TCS priced, 3 of 3, through the paper
  session's own quote path. The market was closed, so these are last-traded prices, not an intraday feed.
- **`scripts/cloud_paper_session.py`** with `check`, `run` and `save-state`; `tests/test_cloud_paper_session.py`
  (37 tests, each guarantee mutation-checked); `.github/workflows/cloud-paper-session.yml`;
  `docs/CLOUD_PAPER_RUNBOOK.md`. The runbook states the 6-hour host limit and the Actions-secret requirement.
- **Kronos trial 10:** scored once. **`RESEARCH_ONLY`**: Sharpe -0.444, net -6.65%, DSR 0.0134 against 0.95.
  `reports/kronos_cloud_run/RESULT.md`. Notice for the claim owner:
  `agent_context/work/active/20261005-NOTICE-kronos-trial-run-from-cloud.md`.
- **`agent_context/GOAL.md`**, wired into `AGENTS.md`, `CLAUDE.md`, the Cursor rule and the context README.
- Gates: ruff, ruff format (940 files), strict mypy `--platform win32` (300 files), the new tests on Python
  3.12 and 3.13, the neighbouring suites forwards and in reverse, test-craft and code-craft clean.

## In progress

Nothing partial.

## What was NOT run, stated plainly

- **`cloud_paper_session.py run` has never run for real.** It starts a paper book. Its logic is tested with a
  fake session only.
- **The workflow has never run on GitHub.** The YAML parses; that is all that is known.
- The first cloud refresh's duration and any provider rate limit from a cloud IP are unmeasured.
- The PowerShell audits (`audit-agent-claims.ps1`, `audit-disk-layout.ps1`) were not run: there is no PowerShell
  in this container. CI's craft job runs them on Windows.
- The full test suite was not run here (CI runs it, about 28 minutes). Only the new tests and their neighbours.
- No release was cut, although `release_status.py` reports one **DUE** (30 user-visible changes, 2 security).
  That predates this work, needs the Windows installer build and `main`, and the founder said not to merge.

## Decisions waiting for the founder

1. **Whether to start the cloud book at all.** `20260924-NOTICE-paper-books-system-test-running.md` forbids another
   paper book without a written purpose, the decision it could change, a benchmark and an end date. Until those
   exist the schedule stays off: it runs only when the repository variable `CLOUD_PAPER_ENABLED` is `true`.
2. **Which host.** GitHub-hosted closes the session about 14:05 IST (6-hour limit) and needs the token as an
   Actions secret. A host with no limit runs to 15:30.
3. **The four open points in `agent_context/GOAL.md` section 7** (cloud versus the charter's non-goal, a numeric
   success measure for the wealth engine, one product or two documents, the word "profit").

## Next safe actions

1. Add the secret `UPSTOX_ANALYTICS_TOKEN` to GitHub Actions, then run the workflow by hand with `check_only`
   ticked (it places nothing). That proves the environment on GitHub.
2. Only after decision 1: one supervised non-check run.
3. The Kronos claim owner updates its ledger row 10 and decides about a stronger "scored once" guard. **Do not
   score the trial again**, whatever a laptop run produces. See the notice.
4. A coordinator reconciles `CURRENT.md` (claimed by two records, so not edited here) with trial 10's result.
5. A separate task was queued for a defect found on the way: `UpstoxClient.fetch_market_quote` cannot parse the
   real quote reply, because the provider keys it by symbol (`NSE_EQ:INFY`) and the client looks for the ISIN
   key. The paper session works around it and is not affected. Its unit test encodes the wrong shape.

## Known risks

- The Kronos run is Linux x86_64, not the declared ARM64 Windows machine, so it is not guaranteed bit-identical to
  a laptop run. Same trial, scored once. See `reports/kronos_cloud_run/AMENDMENT-1.md`.
- `AGENTS.md` is also named by `20260821-claude-concurrent-workspace-rule.md` (HANDOFF_REQUIRED). One reading step
  was added on founder instruction; a notice was filed.
- The scratch environment (venv, Kronos code, weights, logs) lived in the container's scratch directory and is
  not preserved. The rebuild steps are in the work record and are hash-pinned.
