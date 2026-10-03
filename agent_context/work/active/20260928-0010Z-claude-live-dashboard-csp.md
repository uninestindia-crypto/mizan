# Active work: `/live` refused by its own CSP — move the script out, keep the policy

STATUS: COMPLETED ON BRANCH — commit `b79351813` on `claude/amazing-lamport-e18bd1`; not pushed, not merged. Kept in `active/` so the claim stays visible while the branch holds unmerged changes to claimed files  
OWNER: Claude Code (Opus 5.5)  
TOOL: Claude Code  
STARTED_UTC: 2026-09-28T00:10:00Z  
STARTING_REVISION: `e787ac462fe9c9d188ab8974109c3bdbd59b46b2` (main). The branch was fast-forwarded
from `3957937ac`, where the bug was reproduced, so it builds on the 425-line Antigravity redesign of
`live_dashboard.py` that landed in `0a2548123` rather than on the older copy.  
WORKTREE_OR_BRANCH: `D:\quant_system\.claude\worktrees\amazing-lamport-e18bd1` on branch `claude/amazing-lamport-e18bd1`

## Authorization

Founder answers, 2026-09-28, to an explicit question naming every claim crossed (Antigravity on
`live_dashboard.py` and `serve_live_dashboard.py`; Antigravity, Codex and the retail-redesign session
on `app.py`):

1. **"Full fix"**: move script and handlers, drop Google Fonts, point the page at status URLs the app
   serves (one read-only route in `app.py`), show a real no-session state instead of endless
   "Loading…", and make Start/Halt report the real result. NOTICE per crossed claim.
2. **"Real IST clock"**: the header clock ticks every second; the last-mark time stays in the
   subheader.
3. **"Yes, copy them"**: this record and this work's NOTICE files are copied into
   `D:\quant_system\agent_context\work\active\` by shell, because the desktop app's worktree-isolation
   hook blocks the Write tool there. Only new files in that directory; nothing else in the install
   root is touched.

## Objective

`/live` on the FastAPI app runs none of its JavaScript. Its one 18,603-char inline `<script>` is
refused by `script-src 'self'` (`server/security.py:55`, since `c5143c90a`). Fix it **without
weakening the CSP**: move the script to `server/static/`, replace inline handlers with
`addEventListener`, drop the CSP-blocked Google Fonts link, add a regression test, and confirm in a
real browser. Source: task chip from `20260928-claude-redesign-discovery.md` (defects 1 and 3).

## Found before editing (read-only, at `e787ac462`)

1. **Inline handlers.** Five `onclick=` attributes (three tabs, Start, Halt) are also refused by
   `script-src 'self'`. Moving the `<script>` alone would leave the tabs dead.
2. **Endpoint mismatch.** The script polled `/api/status` and `/api/xs_status`. Only
   `scripts/serve_live_dashboard.py` (:8080) serves them. The app serves `/api/paper-pilot/live-status`
   and nothing for XS. Under the app every poll was a 404 that `if (!res.ok) return;` swallowed, so a
   CSP-only fix would have left the page looking exactly as it did.
3. **False success.** Start/Halt never checked `res.ok`. Under the app a POST is refused by the CSRF
   middleware (403), yet the page would have alerted "Automated Trading Started…" / "Trading Session
   Halted: … Reconciled". Same on :8080 when start returns 500.
4. **The header "clock" was not a clock.** `#live-time` showed the payload's `timestamp_ist`.
5. **Fonts.** Only `/live` linked Google Fonts, and since the 2026-09-25 redesign no font stack names
   Inter; JetBrains Mono was a third fallback plus one inline style.
6. `HTML_DASHBOARD` is a plain string with no backslashes and no Python interpolation, so the script
   needed no server-side values and nothing had to move into `data-` attributes.
7. `scripts/serve_live_dashboard.py` serves the same `HTML_DASHBOARD` with no CSP on :8080. It must
   serve the new file too.
8. The desktop Studio serves this same app and `templates.py:67` links to `/live`.

## Owned paths

Unclaimed, mine:

- `src/quant_system/server/static/live_dashboard.js` (new)
- `tests/test_live_dashboard_csp.py` (new)
- this record; `20260928-NOTICE-live-dashboard-csp-fix-under-antigravity-claim.md`;
  `20260928-NOTICE-app-py-xs-status-route-under-codex-and-redesign-claims.md`

Claimed elsewhere — edited on the founder authorization above:

- `src/quant_system/server/ui/live_dashboard.py` — `20260826-antigravity-paper-trade-live-market-testing.md`
  (ACTIVE) and `20260914-claude-paper-book-accounting-repairs.md` (ACTIVE, work complete)
- `scripts/serve_live_dashboard.py` — the Antigravity record above
- `src/quant_system/server/app.py` — one read-only route only. Antigravity record above,
  `20260824-codex-real-journey-api-wiring.md` (HANDED_OFF_CERTIFIED_PENDING_INTEGRATION), and
  `20260928-claude-retail-redesign-build.md` (ACTIVE; claims only the v2 router include and the `/`
  → `/classic` change, and lists `/live`, `live_dashboard.py` and `security.py` as its non-goals
  because this session owns the CSP fix)

Read, not edited: `src/quant_system/server/security.py` (Codex claim). The CSP is unchanged.

## Non-goals

- No change to the CSP or to anything else in `security.py`.
- No start, stop, or reconfiguration of any paper session or scheduled task, and no Start/Halt click
  while testing. Both books run to 2026-10-28 (`20260924-NOTICE-paper-books-system-test-running.md`).
- No write to `D:\quant_system\logs\`. Browser checks read copies placed in this worktree's
  gitignored `logs/`, deleted afterwards.
- No change to what either book trades, to any model or risk limit, or to any payload a book writes.
- No repository-wide formatter, no `git add -A`, and no edit to the install root's working tree
  beyond the authorized record/NOTICE copies.

## Plan

1. File this record; run the claim and layout audits. — DONE
2. Ask the founder to approve editing the claimed paths. — DONE, full fix approved
3. Failing-first regression test. — DONE, 18 of 25 failed for the intended reasons
4. Implement. — DONE
5. Gates: ruff check, ruff format, mypy, focused tests, full suite. — DONE except the full suite,
   running
6. Browser: serve the app from this worktree; confirm no CSP errors, tabs, panels, polling. — DONE
7. NOTICE records; audits; stop point. — DONE
8. Commit on this branch. — DONE, `b79351813`, on founder instruction ("commit it first")

## Current step

Done on the branch. Follow-up work on the same branch: `20260928-0520Z-claude-live-risk-card.md`.

## Decision rationale

- **A static file, not a nonce or hash.** A nonce needs per-response templating and a CSP change in
  `security.py` (Codex claim); the page is a constant served by two processes, one of which sends no
  CSP at all. A hash would also change `security.py` and must be recomputed on every script edit. A
  same-origin file runs unchanged under both servers and keeps `script-src 'self'` exact.
- **`data-tab` plus listeners** instead of `onclick=`: attributes are inline script to the policy.
- **Drop the fonts rather than self-host.** No font stack selects Inter; JetBrains Mono was a third
  fallback. Shipping font files the design never picks would be weight for nothing.
- **Align the URLs rather than add `/api/status` to the app.** The page uses the descriptive names;
  :8080 already answered `/api/xs-monthly/status`, gains `/api/paper-pilot/live-status` as an alias,
  and the app gains the one XS route. Both servers now answer both; nothing was removed from :8080.
- **Real clock** on founder decision; the mark time moved to the subheader on every payload, so
  freshness is still visible.
- **Rejected:** `'unsafe-inline'` in `script-src` (the one-line "fix"; the page has a token field);
  hiding Start/Halt under the app (needs server detection; the controls now report honestly instead).

## Commands and outcomes

| Command | Result | Evidence/notes |
|---|---|---|
| `git status`, `git worktree list`, `git branch --list` (install root) | PASS | main `e787ac462`; install root dirty only in other agents' record moves; 3 worktrees besides the root at start |
| `git merge --ff-only main` (this worktree) | PASS | `3957937ac..e787ac462`; no commits of mine existed |
| Write this record to the install root with the Write tool | BLOCKED | desktop app isolation hook; copied by shell on founder instruction |
| `audit-agent-claims.ps1` (install root), after the copy | FAIL, 1 | only `claude/retail-redesign` (the redesign session's branch name) unclaimed; this worktree and branch resolve |
| `audit-disk-layout.ps1 -Fast` | PASS | lists this worktree as `STRAY` (inside the install root) but passes |
| `pytest tests/test_live_dashboard_csp.py`, before the fix | 18 failed, 5 passed, 2 skipped | failures: inline script ×3, handlers ×3, cross-origin fonts, no script src, static file absent ×3, XS route 404 ×4, :8080 alias 404 ×2, no `data-tab`. Skips: empty parameter sets, guarded by `names_its_script` |
| same, after | **25 passed** | |
| `ruff check .` | PASS | all checks passed |
| `ruff format --check .` | PASS | 764 files already formatted |
| `mypy src launcher.py scripts` | PASS | 218 source files |
| `pytest` on `test_live_dashboard_csp`, `test_live_dashboard_server`, `test_live_status_endpoint`, `test_ui_journeys`, `test_xs_watch_dashboard` | **79 passed** | |
| `pytest tests/ -q`, forwards | **2,033 passed, 1 failed**, 14m48s | the failure is `test_corporate_actions.py::test_the_real_heg_demerger_is_left_unresolved_because_nothing_prices_the_entitlement`, pre-existing: its input `data/evidence/market-cache/nifty500-refresh-20230828-20260827/corporate-actions/nse-corporate-actions-HEG.json` is an empty list at `e787ac462` (committed so by auto-sync `d445b29f7`, 2026-09-25) and in the install root. Not touched by this work |
| `pytest` on `tests/test_*.py` sorted descending (CI's reverse job) | **1,763 passed, 1 failed**, 15m03s | same single failure. The lower count is CI's glob: it lists top-level files only, so the 270 tests in `tests/test_xs_portfolio_alpha/` do not run in reverse |
| `git commit` (five explicit paths) | PASS | `b79351813`. The first attempt passed the message to `git commit -F -` as a PowerShell 5.1 here-string, which arrived as a pathspec; nothing was committed then, and the retry used a message file |
| Browser, app from this worktree on :8767, no book data | PASS | fresh tab: no console message at all; clock 10:27:21 → 10:27:23 IST; `NO SESSION`, "Session: none reporting", XS "No book"; 0 inline scripts, 0 external stylesheets; tabs XS / Directory / Mīzān each switch on a real click |
| Browser, same tab, copies of the archived 2026-09-22 flagship payload and current XS state in this worktree's `logs/` | PASS | filled within 4 s without reload: equity ₹9,88,174.15, 98 positions, 155 fills, "498 of 500 Scored", subheader ends `Marked: 2026-09-21 15:01:32 IST`; XS 99 legs, cash ₹94,409.99. Copies deleted afterwards; originals untouched |
| Scheduled tasks, read-only | OBSERVED | `QuantOS Mizan Paper Session` last ran 2026-09-25 (0xC000013A), next run 2026-09-29 09:00: **today's flagship session did not run**; `QuantOS Session Supervisor`, `Dashboard Supervisor`, `XS Watch Supervisor` Disabled since 2026-09-15. Reported to the founder; nothing changed |

## Files changed

- `src/quant_system/server/static/live_dashboard.js` (new): the page's behaviour, moved verbatim except
  the clock, the two status URLs, the no-session/no-book states, the honest Start/Halt results, and
  the listeners that replace `onclick=`
- `src/quant_system/server/ui/live_dashboard.py`: `<script src>`, `data-tab`, fonts removed, honest
  static defaults, script URL/file constants, docstring
- `scripts/serve_live_dashboard.py`: serves the script; `/api/paper-pilot/live-status` alias
- `src/quant_system/server/app.py`: `GET /api/xs-monthly/status`
- `tests/test_live_dashboard_csp.py` (new): 25 tests against both servers
- the two NOTICE files and this record

## Blockers and conflicts

- None open for this work. The claimed paths were crossed on the founder authorization above; one
  NOTICE per owner group.
- **Workspace location.** This worktree was created by the Claude desktop app inside the install root
  (`.claude/worktrees/`), not by `new-workspace-clone.ps1`. Not relocated: the desktop session is
  bound to it.
- **Concurrent redesign.** `claude/retail-redesign` edits `app.py` below this insertion (the `/`
  block). Expected to merge cleanly; the NOTICE names the exact lines.
- **Not fixed, handed on:** the risk card's values are literals ("Kill Switch: NORMAL (SAFE)" ignores
  `risk_governor.kill_switch_active`; the runner publishes `discrepancy_paisa: "0.00"` as a literal).
  Offered as a separate task chip.

## Stop point

Committed as `b79351813` (the five product and test paths; this record and the two NOTICEs are not in
the commit: `agent_context/` is committed from the install root, where these copies are
authoritative). Full suite green apart from one pre-existing failure. Preview server stopped;
temporary `.claude/launch.json` config reverted; scratch `logs/` copies deleted.

## Next safe action

Merging to `main` is a separate founder decision. Before it: re-read the Antigravity, Codex and
retail-redesign records (PROTOCOL §8.4), and note that the suite total moves by 25 tests.
