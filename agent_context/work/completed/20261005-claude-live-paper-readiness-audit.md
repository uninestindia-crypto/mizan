# Active work: independent readiness audit of live-market paper trading and the product UI

STATUS: COMPLETED (PR #1 merged as e5a8be82; open items for the founder are in the handoff)  
OWNER: Claude Code session (founder request 2026-10-05, text below)  
TOOL: Claude Code  
STARTED_UTC: 2026-10-05T00:00:00Z  
STARTING_REVISION: 3e2be9f0531cecb6a7398f242cec9e4474015dbf  
WORKTREE_OR_BRANCH: `/home/user/mizan` (cloud container, single checkout, no extra worktree) on branch `claude/dazzling-brown-yn5qu3`

## Objective

The founder asked, verbatim in substance: check independently whether the platform is ready for
live-market paper trading (virtual money on live prices, automatic), with two delivery modes chosen by
the user: (A) the platform trades virtually and the owner copies the orders into their own trading
account by hand; (B) the owner optionally grants direct broker access. Test it, and make the
front end feel Apple-made for consumers and the infrastructure, workflow and operations feel
Microsoft-made for trading, investing and bank enterprises.

Deliverable: an evidence-backed readiness verdict (what runs, what does not, what is unproven), the
test and UI evidence behind it, and bounded repairs for defects found where a repair is in scope.

## Owned paths

- `agent_context/work/active/20261005-claude-live-paper-readiness-audit.md` (this record)
- `reports/live_paper_readiness_20261005/**` (new: findings report, screenshots, raw command output)

Repairs, claimed 2026-10-05 after checking all 129 active records for overlap. The only live claim
on `frontend/**`, `server/v2/**` and `tests/test_v2_*` is `20260928-claude-retail-redesign-build.md`
(HANDOFF_REQUIRED, "nothing committed yet" when written). That branch has since reached `main`
(`git log -- frontend` shows `f071d8f5`..`144d0600`, v2.3.0), so the claim no longer protects
unmerged work. The founder's request ("make sure ui ux frontend is like apple created it") is the
explicit instruction to edit these paths; precedent is `CURRENT.md`, "repair was made only after
explicit founder instruction". No other record names any path below.

- `src/quant_system/server/v2/paper_books.py`: order freshness fields, refuse a book whose
  reference series lags the price data
- `src/quant_system/server/v2/router.py`: log (not swallow) a failed Shariah router import only
- `src/quant_system/modeling/mizan_cli.py`: `handle_predict` treats an inline JSON string as JSON on
  Linux (OSError File name too long)
- `frontend/src/components/OrderTicket.tsx`, `frontend/src/lib/orderTicket.ts`,
  `frontend/src/lib/orderTicket.test.ts` (new)
- `frontend/src/pages/PaperBook.tsx`, `frontend/src/pages/Paper.tsx`, `frontend/src/pages/Home.tsx`,
  `frontend/src/pages/Shariah.tsx`, `frontend/src/lib/shariah.ts`, `frontend/src/lib/types.ts`,
  `frontend/src/components/Layout.tsx`, `frontend/src/components/ui.tsx`, `frontend/src/styles.css`
- `tests/test_v2_paper_order_freshness.py` (new)
- `tests/test_paper_books_api.py` (fixture relaxes the new lag guard; the store's benchmark lag is
  irrelevant to what those tests replay)
- `tests/test_cli_bridge.py`, `tests/test_first_run_usability.py` (six Windows-only tests marked
  `skipif(sys.platform != "win32")`; no other record names these files)
- `frontend/src/lib/shariah.test.ts` (new)
- `agent_context/handoffs/20261005-claude-live-paper-readiness-handoff.md` (new)

Second pass, claimed 2026-10-05 on the founder's "complete all": see
`20261005-NOTICE-live-paper-readiness-edits-under-other-claims.md` for every crossed claim.

- `src/quant_system/server/static/live_dashboard.js` (new), `src/quant_system/server/ui/live_dashboard.py`,
  `scripts/serve_live_dashboard.py`, `src/quant_system/server/app.py` (two read-only routes),
  `tests/test_live_dashboard_csp.py` (new)
- `src/quant_system/server/v2/state.py`, `schemas.py`, `paper_books.py`, `router.py`, `health.py` (new),
  `tests/test_v2_paper_placements.py` (new), `tests/test_v2_health.py` (new)
- `frontend/src/components/PlacementDialog.tsx`, `PlacementTrackingCard.tsx` (new), `OrderTicket.tsx`,
  `Layout.tsx`, `frontend/src/pages/Home.tsx`, `PaperBook.tsx`, `frontend/src/lib/queries.ts`, `types.ts`,
  `orderTicket.ts` (+ test)
- `scripts/run_paper_pilot_session.py`, `scripts/run_scheduled_paper_session.py`,
  `tests/test_paper_runner_log_clock.py` (new), `tests/test_paper_runner_wiring.py` (new),
  `tests/test_scheduled_paper_session.py`
- `src/quant_system/shariah/{schemas/screening.py,services/screener_service.py,api/v1/endpoints/screening.py}`,
  `tests/shariah/test_tier1_features.py`, `tests/shariah/test_m3_stress_challenger.py`
- `tests/test_release_packaging.py`, `tests/test_windows_installer.py`
- `reports/live_paper_readiness_20261005/round7_mutation_check.py`, `round7_mutation_results.json`

## Non-goals

- No live-money order routing. Mode B (direct broker access) is T4 money-movement work under
  `.launch/CHARTER.md` and `AGENTS.md` ("excluded unless the user separately authorizes T4"). This
  request describes mode B as an option; it is not a T4 authorization. The audit assesses it and
  does not build it.
- No change to what either running paper book trades (`20260924-NOTICE-paper-books-system-test-running.md`).
- No new paper book, no scheduled-task changes, no model retraining, no multiplicity ordinal spent.
- No edit to `.launch/STATE.md` or `agent_context/CURRENT.md` (claimed elsewhere).

## Plan

1. Startup sequence per AGENTS.md. DONE.
2. Baseline: install frozen deps (Python 3.12, scratch venv), full pytest, ruff, mypy, frontend
   typecheck and unit tests. IN PROGRESS.
3. Read the live paper path: retail paper books, scheduled session runner, realtime shadow runner,
   live feed, risk governor, order-copy surface. IN PROGRESS.
4. Drive the real app in Chromium against the e2e fixture store; capture screenshots; run the
   existing axe accessibility journey.
5. Write the verdict and the repair list. Repair only bounded defects in unclaimed paths.
6. Run `scripts/audit-agent-claims.ps1` and `scripts/audit-disk-layout.ps1` equivalents if possible
   (PowerShell may be absent in this container: record that instead of skipping silently).

## Current step

Complete. Committed and pushed to `claude/dazzling-brown-yn5qu3`. No pull request opened (not asked).

## Decision rationale

- Python 3.12 scratch venv at `/tmp/claude-0/venv312` (the project requires >=3.12; the container
  default is 3.11). Nothing is installed inside the checkout, so the tree stayed clean.
- The audit was read-mostly. The founder's two paper books run on their own laptop against local
  state; this container cannot and did not touch them.
- **Stale orders: refuse and withhold, do not just warn.** A copy workflow acts on quantities alone.
  Rejected alternative: a banner above a still-copyable table. It would leave the dangerous path one
  click away.
- **Creation guard threshold of 2 sessions** on the reference series' lag. The fixture store has a
  deliberate 20-session lag, so seven API tests relax the guard through a fixture; the refusal itself
  is pinned in `tests/test_v2_paper_order_freshness.py` and mutation-killed.
- **Holidays**: read from `authorities/nse-trading-holidays.json` beside the connected data, else
  weekdays only. The failure direction is "out of date too early", never "current too late".
- **Account-size scaling rounds down**, so a copy never spends more than the person chose.
- **Shariah**: relabel and disable rather than invent data. Wiring the dead export button would have
  produced share quantities from seeded prices roughly twice the real ones.
- **Not touched, though found**: `scripts/run_paper_pilot_session.py` (log label "IST", 25 claims),
  `tests/test_release_packaging.py`, `tests/test_windows_installer.py` (claimed), the Shariah backend's
  hardcoded `VERIFIED`.

## Commands and outcomes

| Command | Result | Evidence/notes |
|---|---|---|
| `uv sync --frozen --extra dev --python /usr/bin/python3.12` (scratch venv) | PASS | exit 0 |
| `pytest tests --ignore=tests/test_windows_installer.py` before changes | 2,492 passed, 8 failed, 9 skipped | all 8 Linux-vs-Windows |
| `pytest tests --ignore=tests/test_windows_installer.py` after changes | 2,513 passed, 1 failed, 15 skipped | the 1 is `tkinter`, claimed file |
| `ruff check .`, `ruff format --check .` | PASS | 920 files |
| `mypy src launcher.py scripts` | 17 errors, all Windows-only APIs | unchanged by this work; `--platform win32` leaves only `webview` |
| `npm ci`, `tsc --noEmit`, `vitest run`, `vite build` | PASS | 44 tests (31 before) |
| Browser audit, 13 routes x desktop/phone x light/dark | before: 15 pages with axe violations, 4 with errors; after: 0 and 0, 0 overflow | `reports/live_paper_readiness_20261005/ui_audit_*.json` |
| Order ticket in Chromium (scale, CSV, clipboard, bad input, stale state, phone) | PASS | `shots/` |
| `scripts/run_paper_pilot_session.py` with no token | fails closed | `QuoteFeedError: no Upstox token`; nothing written |
| Egress probe | Upstox public candles reachable; NSE blocked; Upstox auth API 401 | |
| `detect-secrets scan` on changed files | 0 candidates | |
| Mutation: `if missed == 0:` -> `if True:` | 4 tests failed, restored | |
| Mutation: guard `if lag > MAX...` -> `if False:` | 1 test failed, restored | |
| `scripts/audit-agent-claims.ps1`, `scripts/audit-disk-layout.ps1` | PASS in CI | the "Craft checkers and audits" job on PR 1 ran them on Windows and passed; not runnable in this container |
| Live dashboard in Chromium (app-served and supervised), no session and with a session | PASS | no console errors, no axe violations, hostile symbol rendered as text |
| Mode A flow in Chromium (inbox, record, skip, edit, clear, tracking, phone) | PASS | no console errors, no axe violations, 0 overflow |
| Round 7 mutants on a scratch mirror | 7 of 13 survived, then 0 of 13 | `round7_mutation_results.json` |
| `pytest tests` (full, Linux, final tree) | 2,614 passed, 0 failed, 17 skipped | measured after the last code change |
| `ruff check .`, `ruff format --check .` | PASS | 932 files |
| `mypy --platform win32 src launcher.py scripts` | only the Windows-only `webview` import | 298 source files |
| PR 1 Windows CI, first run | Tests (forward) failed on `test_stress_mixed_concurrency_under_load` (p95 62.6 ms) | cold-start in a wall-clock test; fixed by warming up in the measured shape |
| PR 1 Windows CI, run on `603318f3` | Static, Craft and audits, Tests (forward), Tests (reverse), `gates`: all PASS | |
| Clean clone of the pushed branch | frontend builds from the lockfile, 48 frontend tests, 102 new backend tests pass | |
| Orders reminder end to end against a local webhook | one message with counts only, then none | no external service available |
| `scripts/release.ps1` | NOT RUN | Windows-only; release is DUE per `release_status.py` |

## Files changed

- `src/quant_system/server/v2/paper_books.py`: order freshness, holiday list, creation refusal
- `src/quant_system/server/v2/router.py`: log a failed Shariah router import
- `src/quant_system/modeling/mizan_cli.py`: inline JSON is not a path
- `frontend/src/components/OrderTicket.tsx`, `frontend/src/lib/orderTicket.ts` (+ tests): order ticket
- `frontend/src/pages/PaperBook.tsx`, `Paper.tsx`: use the ticket; list badge for out-of-date orders
- `frontend/src/pages/Shariah.tsx`, `frontend/src/lib/shariah.ts` (+ test), `lib/types.ts`: 404, three-state status, honest labels
- `frontend/src/pages/Home.tsx`: not changed (the grid fix is global in `styles.css`)
- `frontend/src/components/Layout.tsx`, `ui.tsx`, `frontend/src/styles.css`: contrast, touch targets, one-column grids, non-wrapping badges
- `tests/test_v2_paper_order_freshness.py` (new), `tests/test_paper_books_api.py`, `tests/test_cli_bridge.py`, `tests/test_first_run_usability.py`
- `reports/live_paper_readiness_20261005/**`, the handoff, and this record

## Blockers and conflicts

- `20260928-claude-retail-redesign-build.md` still claims `frontend/**` and `server/v2/**` although its
  branch is on `main`. Edited on the founder's instruction (the request to fix the UI); recorded above.
  No edit was made to that record.
- Open items O1-O14 in the report need the founder or another owner.

## Stop point

Report written, gates run, committed and pushed. Working tree clean after the commit.

## Next safe action

Read `agent_context/handoffs/20261005-claude-live-paper-readiness-handoff.md`, then merge PR 1 once CI is green and the founder has looked at it.
