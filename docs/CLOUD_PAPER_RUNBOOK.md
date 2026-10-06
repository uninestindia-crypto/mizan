# Cloud paper session runbook

Goal line: G4 and G1 in `agent_context/GOAL.md` (buildable and verifiable in the cloud; a trustworthy
paper path). Founder decision, 2026-10-05: build a cloud runner for the existing paper books with **no model
change**. Work record: `agent_context/work/active/20261005-claude-cloud-paper-and-kronos-run.md`.

## Read these two limits first

1. **A GitHub-hosted job stops at 6 hours, so the session closes early on that host.** The session wants
   09:15-15:30 IST, 6 hours 15 minutes of market, plus a pre-open refresh. The workflow therefore ends the
   session on purpose, about 14:05 IST with the defaults, rather than let the host kill it mid-order, and the
   log says so in a `NOTICE` line. A host with no job limit runs to 15:30 as the laptop does. Every day on
   GitHub-hosted runners is a shortened day, and a shortened day is a different test from a full one.
2. **The Upstox token must also be a GitHub Actions secret if that host is used.** A token set in another
   cloud environment (for example a Claude Code cloud session) is invisible to GitHub. Set
   `UPSTOX_ANALYTICS_TOKEN` under Settings, Secrets and variables, Actions. It is a read-only market-data
   token: no order can be placed with it, and nothing in this repository places one.

## What it is

`scripts/cloud_paper_session.py` is a thin wrapper around `run_scheduled_paper_session._run`, which is
**unmodified**. The session, the model, the risk governor and the freshness rules are the laptop's. The
wrapper adds only what a headless Linux host lacks:

| Added | Why |
|---|---|
| Token check that fails closed | No token, an expired token or a refused token stops the run before any data is fetched. |
| Close time that honours the host | `--max-runtime-minutes` ends the session early and says so. |
| State that outlives the job | `logs/paper_runs` is untracked and a runner's disk is discarded. State is kept on its own branch. |
| Token never printed or saved | Every printed line is redacted. A state file that contains the token is refused (exit 14). |

It does not change what the book trades.

## This is a separate book

The cloud book starts from its own state, in a fresh checkout, so it **cannot overwrite either laptop
book**. Both would then run the same frozen model, and neither is evidence about it: paper P&L is market
plus costs (`agent_context/decisions/20260923-paper-books-system-test-end-date.md`).

The laptop books are a frozen system test until 2026-10-28
(`agent_context/work/active/20260924-NOTICE-paper-books-system-test-running.md`). That notice forbids
starting another paper book without a written purpose, the decision its result could change, a benchmark
and an end date. For that reason the schedule is **off by default**: it runs only when the repository
variable `CLOUD_PAPER_ENABLED` is `true`. Manual runs are always allowed. Do not set the variable until
those four things are written down.

## What was verified, and what was not

Verified on 2026-10-06 from a Claude Code cloud container, with the real token against the real provider:

| Claim | Evidence |
|---|---|
| The token reads live quotes through the session's own quote path | `check` exited 0: INFY, RELIANCE, TCS priced, 3 of 3. The market was closed, so these were last-traded prices, not an intraday feed. |
| It works on the workflow's interpreter | Same result on a `uv sync --frozen` environment under Python 3.13. |
| No token fails closed | Exit 10, nothing fetched. |
| A refused token is classified as the token's fault | A well-formed fake token got `HTTP Error 401: Unauthorized` from the provider and exit 11. |
| The wrapper's logic | `tests/test_cloud_paper_session.py`: 37 tests with fakes. Each guarantee was checked by breaking the code and watching a test fail. |
| The workflow on a **real GitHub runner**, with the repository secret | [Run 37415038898](https://github.com/uninestindia-crypto/mizan/actions/runs/37415038898), mode `rehearse-state`, 45 seconds, every step green. `check` priced 3 of 3 symbols at 10:13 IST, during market hours. |
| The token cannot reach the state branch, with the **real** secret | In that run a state file holding the secret was refused (`save-state` exit 14) and nothing was copied. GitHub masked the value as `***` in the log. |
| The state-branch mechanics | In that run the branch `cloud-paper-state-rehearsal` was created, checked out, written, committed and pushed (`d852743..5562fc4`). It holds one labelled dummy file and is safe to delete. |
| The real-session step stayed off | In that run it was `skipped`; no book was started. |

**Not verified:**

- **`run` has not been run for real.** Doing so starts a paper book. The wrapper's behaviour is tested with a
  fake session, not a real one.
- **Only part of the workflow has run on GitHub.** `check` and `rehearse-state` ran, through a temporary `push`
  trigger that has since been removed, so the version that ships differs by that trigger (and by the default of
  its fallback mode). Not yet run on GitHub: `workflow_dispatch`, which only works once the file is on the default
  branch (do one `check` run right after merging), the `schedule` trigger, and `session` mode.
- **Whether the refresh finishes inside the window from a cloud IP.** The session refreshes about 500 names
  from the tracked cache, which ends 2026-08-27, so the first run has about six weeks to fetch. The duration
  and any provider rate limiting are unmeasured.
- **Whether the session runs end to end on Linux.** `run_paper_pilot_session.py --help` imports and parses
  on Linux. Nothing past that was run.
- **That a job killed by the host still runs its last two steps.** The workflow is written to, with
  `always()`, and that is untested.
- **How long setup takes**, which moves the early-close time by that many minutes.

## One-time setup (GitHub-hosted)

The workflow takes a **mode**. Only `session` can start or continue a book.

| Mode | What it does | Places orders or starts a book? |
|---|---|---|
| `check` (default) | Installs from the lock file and proves the token reads live quotes. | no |
| `rehearse-state` | `check`, then proves with the **real** secret that `save-state` refuses a state file holding it, then runs the state-branch mechanics (create, check out, save, commit, push) on a throwaway branch `cloud-paper-state-rehearsal` with a labelled dummy file. | no |
| `session` | The real paper session. Writes `cloud-paper-state`. The only mode a schedule runs. | **starts or continues the cloud book** |

1. Add the secret `UPSTOX_ANALYTICS_TOKEN` (see the limits above).
2. Run the workflow by hand: Actions, `cloud-paper-session`, Run workflow, mode `check`, then `rehearse-state`.
   Green runs show the token, the environment and the state mechanics are right.
3. Only after the purpose is written down (above): one supervised `session` run. It creates the
   `cloud-paper-state` branch with an empty commit and pushes one commit per session.
4. To schedule it: set the repository variable `CLOUD_PAPER_ENABLED` to `true`. It then runs at 08:45 IST
   on weekdays, always in `session` mode. GitHub can delay a scheduled run by many minutes under load.

Account billing matters: the repository's CI has been red for billing reasons before
(`agent_context/work/active/20260918-NOTICE-ci-billing-failure-has-recurred.md`), and a job that cannot start
runs no session. A six-hour job on every weekday is about 7,900 job-minutes a month (6 h x ~22 days). Check
the current included minutes for the repository's plan before scheduling: the plan has been recorded as the
free `User` plan, whose private-repository allowance is far smaller than that figure.

## Exit codes

| Code | Meaning | Job result |
|---:|---|---|
| 0 | Session finished | green |
| 10 | No token | red |
| 11 | Token expired, malformed, or refused by the provider | red |
| 12 | Not a trading day (weekend or NSE holiday) | green, nothing run |
| 13 | Quote feed unreachable or returned nothing, token not shown to be at fault | red |
| 14 | A state file contained the token, so state was not saved | red |
| other | The scheduled session's own code, passed through (for example 4 for stale data) | red |

## State

State is on branch `cloud-paper-state`, folder `state/`, one commit per session. To read the book, check out
that branch. To restore it anywhere, `python scripts/cloud_paper_session.py run --state-dir <folder>`
copies it in before the session and out after, including after a failed session, because a half-finished
session's state is evidence. `save-state --state-dir <folder>` is the copy-out alone.

If the branch is deleted, the next run starts the book from cash. Do not delete it.

## A host with no job limit

Any Linux machine or VM that stays up from before 08:45 to after 15:30 IST works and runs to the close:

```bash
export UPSTOX_ANALYTICS_TOKEN=...        # set in the host's secret store, never in a file in the repository
uv sync --frozen
uv run python scripts/cloud_paper_session.py check
uv run python scripts/cloud_paper_session.py run --state-dir /var/lib/mizan-paper/state
```

Omit `--max-runtime-minutes`. Schedule it with that host's own scheduler, and keep its disk, or push the
state branch as the workflow does, because state must outlive the machine.

## Stopping it

Unset `CLOUD_PAPER_ENABLED` (or set it to anything but `true`). Nothing runs after the next trigger. The
`cloud-paper-state` branch keeps the book's final state. Record the stop in the work record.

## Token hygiene

- The token is read from the environment only, from `UPSTOX_ANALYTICS_TOKEN` then `UPSTOX_ACCESS_TOKEN`, and
  no other variable. It is never printed, logged, written or committed. Printed text is redacted, GitHub
  also masks secrets in logs, and `save-state` refuses to copy a state file that contains it.
- The analytics token lasts about a year. `check` prints the expiry it carries. Renew it before then.
- A standard Upstox access token expires at 03:30 IST the morning after it is issued and cannot run an
  unattended schedule. Use the analytics token.
