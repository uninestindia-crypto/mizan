# Red Team adjudication — API boundary, shadow replay, realtime shadow, paper pilot

TASK_ID: 20260822-redteam-api-shadow-paper
AGENT: Claude Code (Opus 5) — INDEPENDENT Red Team adjudicator
ROLE: Adjudicator. Did not author any code under test.
STATUS: IN_PROGRESS
STARTED_UTC: 2026-08-22T00:00Z
STARTING_REVISION: 5067fa9e61d569bf31c5e37d83d4a8b318c7d808 (main)
TOOL: Claude Code

## Objective

Break, not review, the API trust boundary and the execution simulation. Adjudicate:
- Slice 6: `src/quant_system/server/**` (API, security, supervisor, schemas)
- Slice 8: `src/quant_system/execution/{shadow_replay,shadow_models,replay_feed}.py`
- Slice 9: `src/quant_system/execution/realtime_shadow.py`, `src/quant_system/data/live_feed.py`
- Slice 10: `src/quant_system/execution/{paper_pilot,orderbook_sim}.py`

Verdict PASS or BLOCKED, no middle.

## Non-goals

- Slices 4, 5, 7 (modeling, promotion, money/greeks/ledger) — concurrent Red Team agent
  `20260822-redteam-money-paths` owns those. Stay out.
- No fixes. No source modification anywhere.

## Owned paths (install root)

- `agent_context/work/active/20260822-redteam-api-shadow-paper.md` (this file)
- `.launch/reports/RED-TEAM-API-SHADOW-PAPER.md` (final report, single write at end)

Nothing else in the install root will be written.

## Workspace

WORKTREE_OR_BRANCH: clone via `scripts/new-workspace-clone.ps1 -Purpose redteam -Label apishadow`
CLONE_PATH: `D:\quant_system_workspaceserification_clonesedteam-apishadow-5067fa9-20260821-204358` (detached at 5067fa9)

## Plan

1. Create this record (DONE).
2. Read AGENTS.md, PROTOCOL.md, DISK-LAYOUT.md, LAUNCH-PROGRESS.md, .launch/STATE.md,
   .launch/SLICES.md, quarantine README, SLICE-06/08/09/10 contracts+evidence. (in progress)
3. Create clone; `$env:UV_PROJECT_ENVIRONMENT=".venv"; uv sync --frozen --extra dev --link-mode copy`.
4. Baseline: confirm gate genuinely green, record exact figures.
5. Attack families in order:
   A. Trust boundary: CORS/Host allowlist variants (evil.com, localhost.evil.com,
      127.0.0.1.evil.com, LOCALHOST case, trailing dot, [::1], missing Host, duplicate Host,
      Origin: null, punycode/unicode lookalikes). Prefix/suffix/`in` matching = Blocker.
   B. Idempotency + races: same request id concurrently from N threads; cancel-during-start,
      double cancel, cancel-after-complete, real worker process kill.
   C. Zero broker writes: module surface inspection for order-submitting methods across
      slices 8-10; attempt to reach any such path.
   D. Event integrity: stale, duplicate, out-of-order, replayed, clock-skewed events;
      typed halt reasons; duplicate-event P&L double count.
   E. Fill realism (Slice 10): zero liquidity, crossed quotes (ask<bid), wide spreads,
      partial fills, displayed-qty limits; price improvement; decision-bar fill (look-ahead).
   F. Money: any float touching money in these paths; costs reconcile to paise in Decimal.
   G. Input boundaries on all API schemas.
   H. Assumption archaeology across the four slices' diffs.
6. Write report in clone, copy to install root.

## Current step

Step 5 — attacking. Baseline gate confirmed GREEN in the clone: `483 passed, 1 warning in 57.21s` (exit 0).

## Findings so far

None recorded yet.

## Commands and outcomes

| Command | Result | Evidence/notes |
|---|---|---|
| `git rev-parse HEAD` (install root) | PASS | `5067fa9e61d569bf31c5e37d83d4a8b318c7d808` |
| `git worktree list` | PASS | only `D:/quant_system 5067fa9 [main]` |
| `new-workspace-clone.ps1 -Purpose redteam -Label apishadow` | PASS | clone at `redteam-apishadow-5067fa9-20260821-204358`, HEAD 5067fa9 |
| `uv sync --frozen --extra dev --link-mode copy` | PASS | exit 0 |
| `uv run --frozen python -m pytest -q` (clone) | PASS | **483 passed, 1 warning in 57.21s**, exit 0 — gate genuinely green before attack |

## Files changed

- `agent_context/work/active/20260822-redteam-api-shadow-paper.md`: this record.

## Blockers and conflicts

None yet.

## Stop point

Record created; docs being read. No clone yet.

## Next safe action

Create the clone with `scripts/new-workspace-clone.ps1 -Purpose redteam -Label apishadow`,
then sync the environment and take the baseline gate measurement.
