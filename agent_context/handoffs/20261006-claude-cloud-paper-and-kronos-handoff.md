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
- **The workflow has only partly run on GitHub.** `check` and `rehearse-state` ran green on 2026-10-06 (run 37415038898, via a temporary push trigger since removed). `workflow_dispatch`, the schedule and `session` mode have not.
- The first cloud refresh's duration and any provider rate limit from a cloud IP are unmeasured.
- The PowerShell audits (`audit-agent-claims.ps1`, `audit-disk-layout.ps1`) were not run: there is no PowerShell
  in this container. CI's craft job runs them on Windows.
- The full test suite was not run here (CI runs it, about 28 minutes). Only the new tests and their neighbours.
- **A release claim I made earlier was wrong.** I reported a release as DUE with 30 changes and 2 security items;
  that came from a clone with no tags. With tags fetched the last release was `v2.3.0`, and `v2.4.0` has since
  been published by another session. Re-run `python scripts/release_status.py` after `git fetch --tags`. No release
  was cut by this work.

## Update, 2026-10-06 later: trial 11 (Kronos-base, five paths) is declared and not yet run

The founder asked for the biggest, best Kronos model and for a download he can run locally or on Kaggle. Declaration
`reports/kronos_trial11/TRIAL-LEDGER.md` was committed (`7a33c62c`) **before any forecast**. It runs the largest released
model with five averaged paths, judged against 11 attempts, scored once. **PR #4 is merged.**

- **Download:** `reports/kronos_trial11/kronos-trial11-package.zip` (inputs, runner, declared generator, README, ledger).
  Follow `reports/kronos_trial11/README.md`, Option A (Kaggle, private dataset, GPU on, internet on). One file comes back:
  `kronos-forecasts.json`.
- **Why it has not run:** no GPU, no Kaggle credential and an empty `LIGHTNING_API_KEY` in the build container. A CPU
  fallback was started on 2026-10-06 10:42 IST (about 102 hours); it is scratch-only and is superseded by any GPU run.
- **Scoring, once the file exists:** put it at `reports/kronos_trial11/kronos-forecasts.json` and run
  `python scripts/score_kronos_trial11.py`. It refuses a second scoring under any file name. **The first complete run is
  scored; any other is discarded unscored.** Never run with fewer paths or a smaller model.
- **Honest expectation:** it fails. Trial 10 lost to cash; a bigger model has to clear a 0.95 deflated Sharpe from 0.013.

## Update, 2026-10-10: trial 11 ran on a Kaggle GPU and was scored once. `RESEARCH_ONLY`.

Done by a laptop session on the founder's instruction, from a separate worktree, branch `claude/kronos-trial11-score`
(pushed, no pull request). Full write-up: `reports/kronos_trial11/RESULT.md`.

- **Run:** Kaggle notebook, private dataset, GPU T4, 5.3 hours, no out-of-memory. The first and only complete run.
  The forecast file's recorded fields match the declaration (Kronos-base, 5 paths, 23,805 forecasts, inputs SHA-256
  `fdbbdd15...cd9c4`). Forecasts SHA-256 `49e4fdca...e54dfe`.
- **Result:** candidate Sharpe +0.138, net +1.23%, deflated Sharpe 0.0773 against 0.95 (11 trials), max drawdown 6.6%,
  6,977 trades. Beats the best noise seed and ALWAYS_TRADE; the gate fails. Rank IC t 0.89 and top-quintile edge
  t -0.01, so no ranking edge. It sits slightly above cash with a t-statistic near 0.2; that is not evidence of an edge.
- **Trial 11 is spent.** `SCORED.json` exists in the trial folder and the scorer refuses a second scoring under any file
  name. **The cloud container's CPU backup run, if it ever finishes, must be discarded unscored.** Nothing follows
  trial 11: any further attempt is ordinal 12 with its own dated declaration.
- **Kaggle gotchas for whoever repeats a GPU run:** Kaggle unpacks a `.gz` upload, so the inputs file arrives as
  `kronos-inputs.json` and must be re-gzipped with `mtime=0` and an empty name to reproduce the declared hash (the notebook
  asserted the hash before any forecast); the built-in browser cannot attach files.
- **Not done:** no independent re-score; `agent_context/CURRENT.md` is not updated (claimed elsewhere, so a notice is
  filed instead); trial 10's ledger row in `reports/kronos_trial/TRIAL-LEDGER.md` is still "not yet run".

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
5. ~~A defect found on the way: `UpstoxClient.fetch_market_quote` cannot parse the real quote reply.~~ **Fixed
   2026-10-06** (`e52f4d86`). The provider keys the reply by symbol (`NSE_EQ:INFY`) and the client looked for the
   instrument key; it now accepts both, refuses an entry naming a different instrument, and treats a side of the
   book with nothing resting as an empty quote. Verified against the real feed during market hours.
   **Correction to what this handoff first said:** it claimed the unit test "encodes the wrong shape". It did not.
   No test parsed a quote body at all, so the success path was never exercised.

## Known risks

- The Kronos run is Linux x86_64, not the declared ARM64 Windows machine, so it is not guaranteed bit-identical to
  a laptop run. Same trial, scored once. See `reports/kronos_cloud_run/AMENDMENT-1.md`.
- `AGENTS.md` is also named by `20260821-claude-concurrent-workspace-rule.md` (HANDOFF_REQUIRED). One reading step
  was added on founder instruction; a notice was filed.
- The scratch environment (venv, Kronos code, weights, logs) lived in the container's scratch directory and is
  not preserved. The rebuild steps are in the work record and are hash-pinned.
