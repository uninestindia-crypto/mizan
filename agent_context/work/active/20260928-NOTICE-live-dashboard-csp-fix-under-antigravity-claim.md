# NOTICE: `/live` made to run under the app's CSP, under Antigravity's active claim

STATUS: NOTICE (additive; no other record is edited)  
FILED_BY: Claude Code (Opus 5.5), `20260928-0010Z-claude-live-dashboard-csp.md`  
FILED_UTC: 2026-09-28  
FOR:
- `20260826-antigravity-paper-trade-live-market-testing.md` (Antigravity, ACTIVE), which owns
  `src/quant_system/server/ui/live_dashboard.py`, `scripts/serve_live_dashboard.py` and
  `src/quant_system/server/app.py`
- `20260914-claude-paper-book-accounting-repairs.md` (Claude Code, ACTIVE, work complete), which also
  lists `live_dashboard.py`

AUTHORIZATION: founder answer, 2026-09-28, to an explicit question naming these claims ("Full fix").  
BRANCH: `claude/amazing-lamport-e18bd1`, base `e787ac462`. Not merged at filing.

## The defect, measured

`server/security.py:54-55` sends `script-src 'self'` (since `c5143c90a`). `/live` carried one
18,603-character inline `<script>` and five inline `onclick=` handlers, all refused. Under the app,
and so under the desktop Studio, which runs the app, none of the page ran: the header read
`--:--:-- IST` and every panel said "Loading..." indefinitely. The Google Fonts stylesheet was refused
by the same policy. The standalone :8080 script sends no policy, which is why the supervised
dashboard kept working and the defect went unseen.

Two further defects were behind it:

- The page polled `/api/status` and `/api/xs_status`. Only :8080 serves them; under the app every poll
  was a 404 that the script swallowed. Fixing the policy alone would have changed nothing visible.
- Start and Halt never checked the reply. Under the app a POST is refused by the CSRF middleware
  (403), and the page would have announced "Automated Trading Started…" / "Trading Session Halted: …
  Reconciled". Same on :8080 when start returns 500. Latent only because the script never ran.

## What changed

| File | Change |
|---|---|
| `static/live_dashboard.js` (new) | The inline script, moved verbatim except as listed below |
| `ui/live_dashboard.py` | `<script src="/static/live_dashboard.js">` instead of the inline block; `data-tab` instead of `onclick=`; Google Fonts `<link>`s removed; `LIVE_DASHBOARD_SCRIPT_URL` / `LIVE_DASHBOARD_SCRIPT_FILE` constants |
| `scripts/serve_live_dashboard.py` | serves `/static/live_dashboard.js` (`text/javascript; charset=utf-8`); answers `/api/paper-pilot/live-status` as a second name for `/api/status` |
| `server/app.py` | one read-only route, `GET /api/xs-monthly/status` (see the companion notice for `app.py`'s other claimants) |
| `tests/test_live_dashboard_csp.py` (new) | 25 tests against both servers |

**What the page now says or does differently** — every change beyond the move itself:

1. Polls `/api/paper-pilot/live-status` and `/api/xs-monthly/status`, which both servers answer.
   :8080 still answers `/api/status` and `/api/xs_status`; nothing was removed.
2. The header clock is a real IST clock (founder decision). The last-mark time stays on the page as
   `| Marked: <timestamp_ist>` in the subheader, now on every payload.
3. Start/Halt: a refusal says "Nothing was started/halted" with the HTTP status and the server's
   reason. A halt answered `NOT_RUNNING` says "No session was running" instead of "Halted".
4. No session: badge `NO SESSION`, "Session: none reporting", and a sentence in the signals panel,
   instead of "Loading..." for good. No XS state: "No book" instead of an equity of ₹0.00.
5. Static defaults that read as measurements: `LIVE STREAM` → `CONNECTING`; net P&L, unrealized and
   fees `₹0.00` → `₹--`; `0.00%` → `--%`; `99 active open legs` → `-- active open legs`.
6. One inline `font-family: 'JetBrains Mono'` → `var(--font-mono)`, like the rest of the page.

**Unchanged:** the Start/Halt request bodies, `build_pilot_launch`, token handling, the loopback bind,
the CSP, every payload writer, and — for the paper-book record — the XS unpriced-leg handling and the
lifetime-fee tile logic, which moved byte-for-byte.

## Verification

- `tests/test_live_dashboard_csp.py`: 18 of 25 failed before the change for the intended reasons,
  25 of 25 pass after.
- `ruff check .` clean; `ruff format --check .` 764 files; `mypy src launcher.py scripts` 218 files.
- Browser, app served from the branch: no console message at all; clock ticking; all three tabs
  switch on a real click; with no data, the no-session states render; with a copy of the archived
  2026-09-22 flagship payload and the current XS state in a scratch `logs/`, every panel fills (98
  positions, 498 signals, 99 XS legs). Start and Halt were never clicked.

## What this invalidates

No number either record pins as evidence. The suite gains 25 tests, so any pinned total moves.

## Operational note

A running :8080 process keeps serving the page it imported. After a merge it serves the new page and
its script only once restarted. Page and script then come from the same process, so nothing is served
half-updated. Observed on 2026-09-28: `QuantOS Dashboard Supervisor` is Disabled, so nothing will
restart it automatically.

## Not fixed, found on the way

The risk card's values are literals: "Kill Switch: NORMAL (SAFE)" ignores the payload's
`risk_governor.kill_switch_active`, and the runner publishes `discrepancy_paisa: "0.00"` as a literal
(`run_paper_pilot_session.py:2272`). Offered to the founder as a separate task.
