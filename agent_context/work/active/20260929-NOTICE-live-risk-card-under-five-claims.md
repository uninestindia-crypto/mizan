# NOTICE: the `/live` risk card, the terminal viewer and the runner's status now report measured values

STATUS: NOTICE (additive; no other record is edited)  
FILED_BY: Claude Code (Opus 5.5), `20260928-0520Z-claude-live-risk-card.md`  
FILED_UTC: 2026-09-29  
FOR — every record that claims a path this work edits:

| Record | Status | Claims |
|---|---|---|
| `20260826-antigravity-paper-trade-live-market-testing.md` | ACTIVE | runner, viewer, dashboard |
| `20260914-claude-paper-book-accounting-repairs.md` | ACTIVE | runner, viewer, dashboard |
| `20260915-0900Z-claude-paper-report-baselines.md` | ACTIVE | runner (report writer) |
| `20260829-claude-live-mizan-feature-provider.md` | IN_PROGRESS | runner |
| `20260829-claude-ruff-repair-unclaimed-files.md` | IN_PROGRESS | runner, viewer |

AUTHORIZATION: founder answers, 2026-09-28, to explicit questions naming Antigravity's claim on these
files: "Show real close check" and, for the viewer, "Yes, fix it too".  
BRANCH: `claude/amazing-lamport-e18bd1`, on top of the CSP fix `b79351813`. Not merged at filing.

## The defect, measured

The "Pre-Trade Risk & Reconciliation" card on `/live` was fixed text: "Kill Switch: NORMAL (SAFE)",
"Max 30% / Asset", "4.00% Max", "₹0.00 Paisa (Pass)", a "0.00 Paisa Exact" badge and "Min Buffer: 5%
(₹50,000)". Underneath:

- The runner's first status of every session (`run_paper_pilot_session.py:1771`) wrote the risk block
  as literals: an untripped kill switch, 30%, 5%, 4%, and a zero discrepancy.
- Every loop (`:2265`) read the switch and the limits from the governor, but still wrote the
  discrepancy as a literal zero. The ledger is reconciled only at the close (`engine.end_session`),
  and that measured result went only to the session JSON.
- The closing status (`:2740`) repeated the last loop's risk block, literal included, and never
  carried the measured reconciliation. Verified on the archived 2026-09-22 flagship status.
- `sprint_50k` enforces 50% / 3%; the page's own Start button defaults to it. The fixed tiles were
  right only for the scheduled `default` book.
- `scripts/view_live_pnl.py`, given a payload that reported nothing, printed: `Kill Switch: NORMAL
  (SAFE) | Max Pos Weight: 30% | Min Cash: 5%` and `Penny-Exact Discrepancy: Rs 0.00 (PASS)`.

## What changed

| File | Change |
|---|---|
| `scripts/run_paper_pilot_session.py` | Status writing only. New `risk_governor_status(governor)` for the first and every loop status; `reconciliation_summary(report)` shared by the session JSON and the closing status; `closing_status(...)` builds the closing status, now with a refreshed risk block and the measured `reconciliation`. Limits formatted `:g` instead of `int()`, which truncated (0.29 would have published as 28%; no current profile is affected) |
| `scripts/view_live_pnl.py` | Section 5 is `risk_lines` / `reconciliation_line`: the session's own values or "not reported" / "checked at session close"; never "SAFE" or "(PASS)" by default. `sys.stdout.reconfigure` moved from import time into `main()` |
| `src/quant_system/server/ui/live_dashboard.py` | Card and cash-tile defaults read "Not reported"; ids for the script |
| `src/quant_system/server/static/live_dashboard.js` | `riskCardView(data)` / `renderRiskCard`. `risk_governor.discrepancy_paisa` is ignored on purpose: older runners wrote it as a literal |
| `tests/test_live_risk_card.py` (new) | 44 tests across the runner, the page's script run under node as shipped, and the viewer |

**Status file shape, for anyone reading it:** `risk_governor` no longer has `discrepancy_paisa`. The
closing status gains `reconciliation: {reconciled, discrepancy_paisa, reconciliation_errors}` — the
same block, from the same helper, as the session JSON — and its `risk_governor` is the governor at the
close, not the last loop's. No key was renamed. The only readers found are the page and the viewer.

**Unchanged:** what either book trades; order generation, sizing, the hold clock, risk limits, the
governor, and `paper_pilot.py`'s reconciliation itself. The session JSON's `reconciliation` block has
the same keys and values as before. The pinned source text `"kill_switch_active": governor.is_killed`
(`test_paper_pilot_carried_session.py:389`) is kept.

## Verification

- Failing first: all 44 new tests failed on `b79351813` for the intended reasons (helpers absent,
  literals present, `riskCardView` absent, viewer functions absent). After: 44 passed.
- With the neighbouring files (CSP, carried session, report baselines, dashboard server, status
  endpoint): 170 passed. `ruff check .` clean; `ruff format --check .` 768 files;
  `mypy src launcher.py scripts` 218 files; `node --check` on the script.
- Browser, app served from the branch, five payloads built from the archived 2026-09-21 session with
  the branch's own helpers and swapped in without reload: default running (30% / 4%, "Checked at
  session close"); sprint running (50% / 3%); today's `main` shape with the literal zero (still
  "Checked at session close"); new closing shape ("₹0.00 — reconciled at close", the session's own
  measured result); old closing shape ("Not measured by this session"). No console message at any
  point. Start and Halt were never clicked.
- Full suite: 2,077 passed forwards and 1,807 in CI's reverse order. The one failure in each,
  `test_the_real_heg_demerger_is_left_unresolved_because_nothing_prices_the_entitlement`, is
  pre-existing on `main`: its input file is an empty list at `e787ac462`.

## What this invalidates

No number any record pins as evidence. The suite gains 44 tests.

## Operational note

Nothing reaches either paper book until this branch merges. After a merge, the next flagship session
writes the new shape: during the day the card says "Checked at session close", and after the close it
shows the measured result. Observed while doing this, and not caused by it: `QuantOS Mizan Paper
Session` last ran 2026-09-28 10:28 (result `0xC000013A`, interrupted), the 2026-09-29 run did not
happen, and `QuantOS Session Supervisor` is Disabled. The flagship book has not completed a session
since its restart.
