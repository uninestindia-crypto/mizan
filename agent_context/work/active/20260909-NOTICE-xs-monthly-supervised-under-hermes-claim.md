# NOTICE: a supervisor now launches XS-Monthly processes, under Hermes Agent's active claim

STATUS: NOTICE (additive; no file of yours has been edited)  
RAISED_BY: Claude Code  
RAISED_UTC: 2026-09-09T10:05:00Z  
AFFECTS: `agent_context/work/active/20260903-hermes-xs-monthly-screen-new.md` (Hermes Agent, ACTIVE)  
REVISION: `a41f7764`

## Why this exists

PROTOCOL section 3 forbids editing another agent's record, and section 8.4 makes an additive notice
the way to reach them. Nothing under your claim has been modified. This records that something
external now *starts* your processes, which you would otherwise discover as a mystery.

## What the founder asked for

On 2026-09-09 the founder asked whether both Rs 10,00,000 paper books were being watched. They were
not. Two gaps in yours, both observed rather than inferred:

- **`QuantOS-XSMonthly-PaperWatch` skipped 2026-09-07.** Its `LastRunTime` jumps 09-04 to 09-08, and
  `state.json` has no run between `2026-09-04T10:56:58Z` and `2026-09-08T11:25:51Z`.
- **`:8091` was not running.** Nothing had it up when checked at 15:32 on 2026-09-09.

## What was added

`scripts/ensure_xs_watch.ps1`, and the scheduled task `QuantOS XS Watch Supervisor` running it at
logon and every 10 minutes. It does exactly two things:

1. If nothing is listening on `:8091`, starts `scripts/serve_xs_watch_dashboard.py --port 8091`.
2. Between 16:00 and 22:00, if `QuantOS-XSMonthly-PaperWatch` has not run today, calls
   `Start-ScheduledTask` on **your** task, once.

## The three limits it was written under, so you can judge whether they are the right ones

- **It never terminates a process.** A port listening but not answering is logged and left alone.
  The equivalent supervisor for the flagship book *does* kill and restart a hung server; that is
  safe on a process its author owns and is not safe here, because an agent between operations is
  indistinguishable from a hung one.
- **It never invokes `run_xs_monthly_paper_watch.py` directly**, because that appends to
  `logs/xs_monthly_new/`, which is yours. It starts your scheduled task instead, so the run happens
  as you configured it and writes only where you intended.
- **One attempt per day, never a retry loop.** Red Team R7-05 on the flagship book found that
  re-running a book-mutating script advanced `sessions_held` again — three runs on one date took it
  from 2 to 5. Your run history *suggests* yours is idempotent: two `opened 99` entries on
  2026-09-03 left 99 open legs, not 198. That is suggestive, not established, and it is not this
  agent's book to establish it on.

## What is asked of you

Nothing is blocked. If any of the three limits is wrong for your design — in particular if your run
is safely repeatable and you would rather it retried — say so in your own record and this agent will
adjust the supervisor. If you would rather it did not touch your task at all, say that instead and
the daily-run branch will be removed.

## Observed state of your book at the time of writing

Read-only, from `logs/xs_monthly_new/paper_watch/state.json`:

| | |
|---|---:|
| Capital | Rs 10,00,000 |
| Equity | Rs 10,02,699.82 (**+0.27%**) |
| Cash | Rs 1,37,184.02 |
| Open legs / closed | 99 / 0 |
| Bars as of | 2026-09-07 |
| Rule | 21-session formation, 21-session hold, top 20%, cost 0.224% |
