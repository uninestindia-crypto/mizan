# Active work: QuantOS 2.0 retail redesign — new frontend, real-data features, installer

STATUS: HANDOFF_REQUIRED (branch complete and verified; awaiting founder review before any merge)  
OWNER: Claude Code session (founder instruction 2026-09-28: "ok then execute it" after the
redesign explanation in `20260928-claude-redesign-discovery.md`)  
TOOL: Claude Code  
STARTED_UTC: 2026-09-28  
STARTING_REVISION: e787ac462 (main at worktree creation)  
WORKTREE_OR_BRANCH: `D:\quant_system_workspaces\worktrees\feature-retail-redesign-e787ac4-20260928-000443` on branch `claude/retail-redesign`

## Objective

Replace the engineer's console with a retail-grade product whose north star is helping Indian
retail investors and swing traders keep and make money honestly: real NSE data, real costs,
honest verdicts, paper-first, never implying an edge the evidence does not show. Then rebuild the
Windows installer with it and test end to end.

## Defaults taken (founder did not answer the six questions; safest option chosen for each)

1. Audience: long-term investors and swing traders first; no intraday or F&O signals.
2. Paper only. No live order routing (T4 not authorized).
3. Assume personal use; no feature that sells or publishes recommendations or black-box
   strategies to others (SEBI RA/IA/algo rules).
4. Look and feel: calm, data-dense, plain language; own design system (not a copy of any broker).
5. Web-first frontend (React + TypeScript + Vite) shown in the desktop window; Node needed only
   at build time.
6. Codex CLI image generation (founder's ChatGPT login) for illustrations only; every prompt and
   the reported model logged.

## Owned paths (in the worktree/branch only)

- `frontend/**` (new)
- `src/quant_system/server/v2/**` (new: API v2 + SPA serving)
- `src/quant_system/market/**` (new: read-only market data index built from the evidence store)
- `src/quant_system/server/app.py` — **claimed by several records**; only: include the v2 router,
  point `/` at the new app, keep the old console at `/classic`
- `src/quant_system/__init__.py`, `pyproject.toml` version fields (2.0.0)
- `scripts/build-windows-release.ps1`, `installer/quantos.spec` — frontend build step and static
  bundle only (claimed by the codex release-manifest record; NOTICE already filed 2026-09-26)
- `tests/test_v2_*.py`, `tests/test_market_*.py` (new)
- `docs/product/**` (new: PRD, design system, ADR)

## Non-goals

- No change to accounting, risk governor, execution, evidence, modeling or paper-book code.
- No change to `/live`, `live_dashboard.py`, `security.py` (task_c889215d is fixing the CSP bug
  in its own session), `quantos_studio.py`, `installer/setup_gui.py`.
- No live orders; no model promotion; no new research campaign.

## Plan

1-8. Worktree, PRD/ADR, market index, Strategy Lab, API v2, React frontend, Codex illustrations,
     browser tests — DONE (see previous checkpoint; unchanged).
9. Native window + installer — DONE on the branch (founder: "we should have native app").
   `src/quant_system/shell/native_window.py`: WebView2 through pywebview, single instance,
   fitted to the display, dark first paint, refuses the legacy IE engine, falls back to an
   Edge/Chrome app window. pywebview 6.2.1 added to `pyproject.toml` + `uv.lock` (Windows only).
   Release script builds the frontend first; version 2.0.0.

## Current step

Complete on the branch. Waiting for founder review before anything merges to `main`.

## Verification (all on branch `claude/retail-redesign`, HEAD `edac86cb6`)

| Check | Result |
|---|---|
| full `pytest tests/` (worktree venv built from `uv.lock`) | 2,108 passed; 3 failed: HEG real-data test (pre-existing, task_df2345fd) and two installer-version checks that raced my version bump mid-run, re-run: PASS |
| new tests | native window 24, market index 44, lab 37, API v2 21, installer/packaging 22, vitest 10 |
| mypy strict / ruff | market, lab, server/v2, shell: clean |
| Playwright in Edge, fixture store | 15/15: journeys, WCAG 2 AA axe in light + dark on 15 pages |
| Playwright on the user's real store | 5/5: index build 88-98 s, full-market re-sort 53-107 ms, lab 1.3 s / 6.4-6.9 s |
| release build | `dist/QuantOS_v2.0.0_Setup.exe` 49.2 MB, SHA-256 `35A8E295...D593C2`, unsigned; zip 84.9 MB; 325 files |
| installed app (frozen) | native window titled "QuantOS", first-run journey on real data passes over the WebView2 debugging port, 0 console errors |
| second launch | exits in 0.8 s, focuses the first window |
| close window | engine stops, port freed |
| upgrade over existing install | settings db and index kept; app reopens on Home |
| uninstall | program, shortcuts, registry removed; `data\` and `logs\` kept |

Defects found and fixed by these runs: fonts inlined as data: URIs (CSP), onboarding redirect race,
index trusted regardless of data folder, wrong folder ranked first, switch knob overflow, muted
text contrast, ARIA on a div, crushed refusal callout, unexplained demerger crash, duplicate button
names, window larger than a 150%-scaled laptop screen, probability shown beside a Lost verdict.

## Known limits (not fixed here)

- A fresh install has no market data: the user must point it at a QuantOS data folder. An in-app
  download from Upstox is the largest missing feature (prices cannot be bundled).
- NIFTYBEES ends 2026-08-21 while stocks run to 2026-09-28 (task_6bb127bc).
- Installer and app are unsigned (needs the founder's certificate).
- Real orders remain off; no model is promotable.

## Files changed (branch)

new: `frontend/**`, `docs/product/**`, `src/quant_system/{market,lab,shell,server/v2}/**`, tests
(`market_fixtures`, `test_market_index`, `test_lab`, `test_v2_api`, `test_native_window`).
edited (claimed elsewhere): `src/quant_system/server/app.py`, `tests/test_ui_journeys.py`,
`src/quant_system/server/static/index.html`, `src/quant_system/__init__.py`, `pyproject.toml`,
`uv.lock`, `quantos_studio.py`, `scripts/build-windows-release.ps1`, `tests/test_windows_installer.py`.
See `20260930-NOTICE-retail-redesign-branch-touches-claimed-paths.md`.

## Blockers and conflicts

- 25 active records claim UI/server paths; `quantos_studio.py` also has uncommitted edits in the
  install root from the 2026-09-25 sessions, so its hunk will conflict at merge.
- Paper-book system test runs to 2026-10-28; do not merge until the founder decides.
- Task chips raised: task_c889215d (live dashboard CSP; founder started it), task_ce869ba4
  (BacktestEngine single position; founder started it), task_6bb127bc (NIFTYBEES refresh),
  task_df2345fd (HEG test).

## Stop point

Branch committed (3 commits), not pushed, not merged. Worktree keeps its own `.venv` (built from
the lock) and `dist/` (gitignored).

## Next safe action

Founder reviews the branch and the installer; then merge notices are read, `quantos_studio.py`
conflict is resolved by hand, and the branch is merged after the paper-book test or by explicit
decision.
