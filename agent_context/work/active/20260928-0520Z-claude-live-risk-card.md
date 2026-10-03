# Active work: `/live` risk card reports what the session measured, or says it did not

STATUS: ACTIVE  
OWNER: Claude Code (Opus 5.5)  
TOOL: Claude Code  
STARTED_UTC: 2026-09-28T05:20:00Z  
STARTING_REVISION: `b79351813` — the CSP fix of `20260928-0010Z-claude-live-dashboard-csp.md`,
committed first on this branch on founder instruction, on top of `e787ac462`  
WORKTREE_OR_BRANCH: `D:\quant_system\.claude\worktrees\amazing-lamport-e18bd1` on branch `claude/amazing-lamport-e18bd1`

## Authorization

Founder answers, 2026-09-28, to explicit questions naming Antigravity's claim on these files:

1. **"Show real close check"**: the runner writes its end-of-day reconciliation into the status file
   and stops writing the fake 0.00; during the day the tile says "checked at close". Edits
   `run_paper_pilot_session.py` (status writing only, nothing the book trades) and the page.
2. **"Yes, fix it too"**: `scripts/view_live_pnl.py` follows the same rule.
3. **"Yes, commit it first"**: the CSP fix is committed on this branch as its own commit before this
   work (no push, no merge).

Record and NOTICE copies into the install root use the shell copy the founder approved for this
session's records (the desktop app's isolation hook blocks the Write tool there).

## Objective

Every value on `/live`'s "Pre-Trade Risk & Reconciliation" card, and in the terminal viewer's
section 5, comes from what the session reported; a value it did not report says so, and never
defaults to the reassuring one. Source: task chip filed by `20260928-0010Z-claude-live-dashboard-csp.md`.

## Found before editing (read-only)

- `run_paper_pilot_session.py:1771-1777`: the first status of every session writes the risk block as
  literals: an untripped kill switch, 30%, 5%, 4%, and a zero discrepancy.
- `:2265-2273`: every loop reads the kill switch and limits from the governor, but still writes the
  discrepancy as a literal zero. The ledger is reconciled only at the close
  (`engine.end_session`, `:2319`), and that result goes only to the session JSON (`:2557`).
- `:2740-2765`: the closing status spreads the last loop's risk block, literal included, and never
  carries the measured reconciliation. Verified on the archived 2026-09-22 flagship payload: top-level
  keys include `kill_switch_active` and `closed_at_ist`, no `reconciliation`.
- Two profiles (`:1391`, `:1404`): `sprint_50k` enforces 50% / 3% daily / 8% total, `default` 30% /
  4% / 12%. The scheduled book runs `default`; the page's Start button defaults to `sprint_50k`. The
  fixed tiles were right only for the scheduled book, by coincidence.
- The limits were formatted `int(x * 100)`, which truncates (0.29 would publish as 28%). No current
  profile is affected.
- `view_live_pnl.py:115-117` printed "NORMAL (SAFE)" when the switch was not reported as active,
  defaulted limits to 30% / 5%, and printed "(PASS)" unconditionally.
- `tests/test_paper_pilot_carried_session.py:389` pins the literal source text
  `"kill_switch_active": governor.is_killed`; kept.

## Owned paths

Mine:

- `tests/test_live_risk_card.py` (new)
- `src/quant_system/server/static/live_dashboard.js` (created by the CSP work)
- this record and this work's NOTICE

Claimed elsewhere, edited on the authorization above:

- `src/quant_system/server/ui/live_dashboard.py` — `20260826-antigravity-paper-trade-live-market-testing.md`
  (ACTIVE), `20260914-claude-paper-book-accounting-repairs.md` (ACTIVE)
- `scripts/run_paper_pilot_session.py` (status writing only) — the two records above, plus
  `20260915-0900Z-claude-paper-report-baselines.md` (ACTIVE), `20260829-claude-live-mizan-feature-provider.md`
  (IN_PROGRESS) and `20260829-claude-ruff-repair-unclaimed-files.md` (IN_PROGRESS)
- `scripts/view_live_pnl.py` — Antigravity, paper-book accounting and ruff-repair records

## Non-goals

- No change to what either book trades, to order generation, sizing, risk limits, the governor, or
  `paper_pilot.py`'s reconciliation itself. The runner only writes what it already measures.
- No start, stop, or reconfiguration of any session or scheduled task; no write under
  `D:\quant_system\logs\`. Paper books run to 2026-10-28.
- No repository-wide formatter, no `git add -A`.

## Plan

1. Wait for the CSP work's full suite; commit the CSP fix. — DONE, `b79351813`
2. Failing-first test `tests/test_live_risk_card.py`. — DONE, 44 of 44 failed on `b79351813`
3. Runner: `risk_governor_status`, `reconciliation_summary`, `closing_status` helpers, used by every
   status write. Viewer: `risk_lines`, `reconciliation_line`. Page: ids plus `riskCardView`. — DONE
4. Gates, full suite, browser with payload copies in this worktree's `logs/`. — DONE
5. NOTICE; audits; stop point. — DONE
6. Second commit on this branch. — waiting for founder instruction

## Current step

Verified; uncommitted. The second commit waits for the founder ("this work on top as a second commit
when you say so").

## Decision rationale

- **Publish the close's own measurement; do not compute a new one.** `engine.end_session` already
  reconciles cash against the ledger. Writing its result into the closing status needs no change to
  `paper_pilot.py` or anything the book acts on. An intra-day reconciliation would have meant new
  money-path code during the paper system test; the card says "Checked at session close" instead.
- **Pure helpers, tested directly, plus AST wiring checks.** No test runs a session to its close (the
  existing harnesses stop at startup guards), and driving the model and market cache in a test would
  be heavy and brittle. The helpers are tested with a real `PreTradeRiskGovernor` and a real
  `SessionReconciliationReport`; AST checks prove every status write uses them.
- **The page's display logic runs under node, as shipped.** `riskCardView` is loaded from the real
  file into a `vm` context with a stub DOM, so the test exercises the code the browser runs.
- **The literal is ignored, not trusted, in old payloads.** A pre-change status file carries
  `risk_governor.discrepancy_paisa: "0.00"` that nothing measured; the page and viewer show "Checked at
  session close" or "Not measured by this session" for it.
- **Top-level `kill_switch_active` wins when present.** It is the switch at the close; the risk block
  of a running status can predate a halt.
- **Rejected:** removing the tile (loses a measurement that exists); labelling only (leaves the fake
  zero in every status file).

## Commands and outcomes

| Command | Result | Evidence/notes |
|---|---|---|
| CSP work's full suite, then `git commit` of its five paths | PASS | `b79351813`; see that record |
| `pytest tests/test_live_risk_card.py` on `b79351813` (viewer edit set aside, `git checkout` of my own change, restored after) | **44 failed** | runner helpers absent (18); page literals present (6) and `riskCardView` not a function (8); viewer `risk_lines` / `reconciliation_line` absent (12) |
| Original viewer on a payload reporting nothing | OBSERVED | printed `Kill Switch: NORMAL (SAFE) \| Max Pos Weight: 30% \| Min Cash: 5%` and `Penny-Exact Discrepancy: Rs 0.00 (PASS)` |
| same test file, after | **44 passed** | |
| with `test_live_dashboard_csp`, `test_paper_pilot_carried_session`, `test_paper_report_baselines`, `test_live_dashboard_server`, `test_live_status_endpoint` | **170 passed**, 13m50s | stderr traceback is the known stalled-client noise |
| `ruff check .` | PASS | |
| `ruff format --check .` | PASS after `ruff format` on my two files | 768 files; the reflow was in lines I wrote |
| `mypy src launcher.py scripts` | PASS | 218 files |
| `node --check static/live_dashboard.js` | PASS | |
| Browser, app from this worktree on :8767, five payloads built from the archived 2026-09-21 session by the branch's helpers (scratch script; reads the archive only) | PASS | default running: Not triggered / Max 30% / 4% Max / Min buffer 5% / "Checked at session close"; sprint: Max 50% / 3% Max; `main`'s literal shape: still "Checked at session close"; new closing: "₹0.00 — reconciled at close", badge "Reconciled at close"; old closing: "Not measured by this session". No console message. Copies deleted, config reverted |
| Scheduler, read-only, 2026-09-29 10:00 | OBSERVED | `QuantOS Mizan Paper Session` last ran 2026-09-28 10:28 (0xC000013A), no 2026-09-29 run, next 2026-09-30 09:00; Session Supervisor Disabled. Not changed |
| `audit-agent-claims.ps1` (install root), 2026-09-29 10:03 | FAIL, 3, none mine | this worktree and branch resolve. UNCLAIMED: `D:\quant_system\.claude\worktrees\magical-taussig-9dceb1` and branch `claude/magical-taussig-9dceb1` — another desktop-app session whose record (`20260929-0431Z-claude-backtest-engine-held-position-marks.md`) exists only inside that worktree, the same isolation-hook problem this work hit; it owns `backtest/engine.py` and a new test and excludes `server/app.py`, so no overlap. And `claude/retail-redesign` (branch named on a continuation line of its record). Observed, left alone (PROTOCOL §8.2) |
| `pytest tests/ -q`, forwards | **2,077 passed, 1 failed**, 14m05s | 2,033 before this work plus the 44 new tests. The failure is the pre-existing `test_the_real_heg_demerger_is_left_unresolved_because_nothing_prices_the_entitlement` (its input file is empty at `e787ac462`; see the CSP record) |
| `pytest` on `tests/test_*.py` sorted descending (CI's reverse job) | **1,807 passed, 1 failed**, 17m56s | 1,763 plus 44; same single pre-existing failure |

## Files changed

- `scripts/run_paper_pilot_session.py`: three helpers; four call sites (first status, loop status,
  session JSON reconciliation, closing status)
- `scripts/view_live_pnl.py`: `risk_lines`, `reconciliation_line`; stdout reconfigure moved to `main`
- `src/quant_system/server/ui/live_dashboard.py`: risk card and cash-tile defaults; ids
- `src/quant_system/server/static/live_dashboard.js`: `riskCardView`, `renderRiskCard`
- `tests/test_live_risk_card.py` (new, 44 tests)
- `20260929-NOTICE-live-risk-card-under-five-claims.md`, this record

## Blockers and conflicts

None open. The five claimants are listed in the NOTICE.

## Stop point

Implemented and verified: 44 new tests, gates, full suite forwards and reverse (one pre-existing
failure each), browser. Working tree holds the five paths below modified or new; nothing staged or
committed. Preview server stopped, temporary `.claude/launch.json` config reverted, scratch payload
copies deleted (`logs/studio_stdio.log` in this worktree is written by the suite's Studio tests, not by
this work).

## Next safe action

On founder instruction, commit exactly `scripts/run_paper_pilot_session.py`, `scripts/view_live_pnl.py`,
`src/quant_system/server/ui/live_dashboard.py`, `src/quant_system/server/static/live_dashboard.js`
and `tests/test_live_risk_card.py` as the second commit on this branch. Merging to `main` is a separate
decision: re-read the five claimant records first (PROTOCOL §8.4); the suite total moves by 69 tests
(25 + 44) across both commits.
