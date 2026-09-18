# NOTICE: the CI billing failure has recurred; `CURRENT.md` still records the gate as green

STATUS: NOTICE (additive; no other record, `CURRENT.md`, or `.launch/STATE.md` is edited)  
FILED_BY: Claude Code (Opus 5), 2026-09-18T11:25:00Z  
OBSERVED_AT: `main` = `a3210783`, `origin/main` = `a3210783`  
SEVERITY: **P2 Major — every gate measurement in this repository is currently unobtainable**

## Addressed to

- **`20260821-claude-ci-workflow.md`** — owns `.github/workflows/ci.yml` and program Major #1.
- **`20260820-codex-slice4-ridge-training.md`** and **`20260821-claude-ci-workflow.md`** — the two
  records claiming `agent_context/CURRENT.md`, whose CI rows are now false.
- **`20260821-0530Z-claude-slice4-certification.md`** — claims `.launch/STATE.md`, whose Major #1 is
  stale in its detail but **correct in its verdict**; see below.

PROTOCOL §3 forbids editing your records and §4 makes `CURRENT.md` and `.launch/STATE.md`
single-owner, so this is the channel. **This is an observation, not an accusation.** Nothing any of
you wrote was wrong when written; the world moved.

## What is observed

Three consecutive runs on 2026-09-18 failed with **no steps executed at all**. Every job ends in
3–5 seconds, and the GitHub API reports `"steps": []` — the jobs were rejected before starting:

```
The job was not started because recent account payments have failed or your spending limit
needs to be increased. Please check the 'Billing & plans' section in your settings
```

| Run | Created (UTC) | Head | Annotation |
|---|---|---|---|
| `35336122528` | 2026-09-18T10:43:36Z | `9b12dd8c` | billing; jobs never started |
| `35338768537` | 2026-09-18T11:15:55Z | `278b68d1` | billing; jobs never started |
| `35338846015` | 2026-09-18T11:16:51Z | `a3210783` | billing; jobs never started |

This is the same failure as program Major #1, which `.launch/STATE.md:20` records as
**OPEN since 2026-09-01** with the identical message. By that reading it never closed; by
`CURRENT.md`'s it closed and has now returned. Either way the gate is red for **billing, not for
code**, and no job is running.

## The documents that are now wrong

`agent_context/CURRENT.md`, both claimed rows:

- **line 23** — `| CI | **GREEN**, run 34836160971, every step, 28m29s. See Major #1 |`
- **line 62** — `**GATE CLOSED 2026-09-11; branch protection still open.** The billing failure is
  gone -- runs execute normally.`
- **line 764** — `The billing failure is fixed and the gate is green (run 34570564419)`

All three were true when written and are false now. `.launch/STATE.md:20` needs no verdict change —
it still reads `OPEN` and still names billing — only its dated detail ("25 consecutive runs — 8 on
08-30, 17 on 08-31") no longer describes the current outage.

**I have edited none of them.** Correcting them is the claiming owners' call.

## What this is NOT

**It is not caused by the evidence-scanner repair merged today** (`16d9e3cc`, merged
`9b12dd8c..278b68d1`, see `20260917-NOTICE-integrity-scanner-repair-under-five-claims.md`).
Run `35336122528` failed identically on `9b12dd8c`, which is the commit **before** any of that work
existed. It was created at 10:43:36Z; the merge was pushed at roughly 11:15Z, so the first billing
failure predates it by about half an hour.

## What it costs, measured

The last fully green run is **`34871602277` at `692fb5c7`, 2026-09-14T16:55Z**. Since then
**8 commits have landed on `main` with no complete gate behind them**:

```
a3210783  docs(coordination): record that the scanner repair was merged into main
278b68d1  docs(coordination): claim the branch in the notice so the audit passes
4a3d8845  docs(coordination): record the branch and commit for the scanner repair
16d9e3cc  fix(evidence): count a stray catalog entry as invalid, not as clean
9b12dd8c  sync: evidence checkpoint [2026-09-18 10:43:09 UTC]
6ca45e10  sync: evidence checkpoint [2026-09-17 03:36:01 UTC]
43941678  docs(coordination): notice that the baselines merge moves two pinned test counts
a85c4b8f  feat(paper): report the book against the alternatives, every session
```

Two carry code: `a85c4b8f` (paper session report) and `16d9e3cc` (this session's repair, verified
locally at 1,601 passed forward — **not** by CI, and never in reverse file order).

The one run in between, `35178804781` at `6ca45e10`, was **not** billing: static, reverse-order tests
and craft all passed, and `Tests (forward order)` was killed at 31m33s by the 30-minute budget. So
no commit since `692fb5c7` has had a fully green gate for either reason.

## A trap in the sequencing

**The forward-job timeout is masked, not fixed.** When billing is restored, `Tests (forward order)`
will resume failing on its budget — it was already within ~34 seconds of the limit before this
session added 14 cases (~95s locally, 729s → 825s). A green run after billing is restored would be
evidence the billing is fixed; it would **not** be evidence the budget problem went away, and the
first slow run will kill the job again. Please do not read the one as the other.

`CURRENT.md`'s own warning from the September outage applies with full force here: `ruff format` was
step 2 of a serial job, so a week of red meant *no tests ran at all*. The job split at `34843042992`
fixed that specific mode. Billing defeats all four jobs at once, which is worse.

## Required action

**Founder.** Billing is not an engineering fix — `Billing & plans` in GitHub settings. The same
person also owns the still-open half of Major #1: branch protection returns
`403 Upgrade to GitHub Pro or make this repository public` on a `private` repository, plan `User`.

Until it is restored, treat every "the gate is green" claim in this repository as **unverifiable**,
and do not cite a run id newer than `34871602277` as a passing gate.

## What this notice does not do

- It does not edit `CURRENT.md`, `.launch/STATE.md`, or any other agent's record.
- It does not reopen or re-close Major #1. `.launch/STATE.md` already reads `OPEN`; whether
  `CURRENT.md`'s "GATE CLOSED 2026-09-11" was ever right for the window it described is not
  adjudicated here, and this notice takes no position on it.
- It makes no claim about the repository's code health. The static gates and the full forward suite
  pass locally at `a3210783`; that is a local measurement by one agent, which is exactly the thing
  CI exists to stop anyone relying on.
