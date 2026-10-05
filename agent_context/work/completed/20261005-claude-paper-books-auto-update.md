# Active work: paper books keep themselves up to date

STATUS: COMPLETED  
OWNER: Claude Code session (founder instruction 2026-10-05: "yes" to the plan: automatic daily update of paper books, a real-browser
check of the new-paper-book page, then a v2.2.0 release under the standing release rule)  
TOOL: Claude Code (mechanical UI pieces may go to `agy --model gemini-3.8-flash-high`; reviewed and verified here, told not to run git)  
STARTED_UTC: 2026-10-05  
STARTING_REVISION: 8c16bb488 (main, pushed)  
WORKTREE_OR_BRANCH: the install root, branch `main` (shared checkout, no worktree)

## Objective

1. Paper books follow the market without the person pressing "Update market data": once per trading day, after the close, the
   app fetches the recent window itself, only when it is safe (see decisions), and says plainly on the Paper page what it did
   or why it could not.
2. The new-paper-book page (`/paper/new`) driven end to end in a real browser (add a stock, start a book, see tomorrow's
   orders); defects found are fixed.
3. Release v2.2.0 through `scripts/release.ps1` if the release rule says due.

## Workspaces

- One detached **verification clone** at `51f0860ed` (my two local commits), created with
  `scripts/new-workspace-clone.ps1 -Purpose verify -Label auto-update-gate`, below
  `D:\Quant OS Project\quant_system_workspaces\verification_clones\verify-auto-update-gate-51f0860-20261005-074145`. The script's own checkout failed on a Windows long path (`core.longpaths` is not inherited by a fresh clone), so I finished that checkout myself with `core.longpaths=true` and `reset --hard 51f0860`; only my clone was touched. Why:
  the full suite cannot be measured in this checkout, because `tests/test_paper_pilot_carried_session.py::test_halted_portfolio_refuses_trading_at_startup`
  reads the dev tree's real ten-year evidence store through `load_mizan_cross_section` and does not finish in 20+ minutes here
  (stack: `evidence/store.py:_verify_blobs`), while it is instant on a tree with no market data. I own this clone and will retire it
  when the run is certified.

## Non-goals

- No live order routing, no change to accounting, risk governor, evidence or modelling code.
- No change to the lab simulator or the paper replay (`lab/`), which stay as released in v2.1.0.
- No edits to `server/app.py` (claimed by several older records): the background worker is attached through the v2 router's
  lifespan wrapper instead.
- No code signing.

## Owned paths

- `src/quant_system/server/v2/auto_update.py` (new), `src/quant_system/server/v2/{router,state}.py`
- `tests/test_auto_update.py` (new), `tests/test_paper_books_api.py` (additive)
- `frontend/src/pages/{Paper,PaperNew,PaperBook,Settings}.tsx`, `frontend/src/lib/{queries,types}.ts`
- `scripts/release.ps1` (lint gate fix only)
- version files at release time (see `AGENTS.md` Release rule)

## Design decisions (rationale)

- **When:** an update is attempted only when all hold: the setting is on (default on), at least one paper book is running,
  a ten-year baseline made by the in-app download exists, and the connected data folder is the app's own `data` folder. The
  last condition matters: a quick update writes into the app's folder and then connects it, so without the check a person who
  connected their own research data would be silently switched to another folder.
- **What is "due":** the latest completed weekday session. NSE closes at 15:30 IST; a session counts as available from 18:00
  IST, and before that the previous weekday is the target. Holidays are not known, so a download that finishes without
  advancing the data is treated as "maybe a holiday or a late provider", retried at most 3 times per target session, one hour
  apart. After that the app stops trying until the next session and says so.
- **Where it runs:** one daemon thread polling every 10 minutes (first look after 30 s), started by the router lifespan
  wrapper and stopped on shutdown. It reuses `MarketDownload` and the existing index rebuild, so there is no second download
  path. The decision is a pure function (`decide`) so it is tested without threads or the network.
- Status for the UI is a plain-language snapshot at `/paper/updates`; nothing is hidden when automatic updating is off or not
  possible.

## Plan / current step

1. Claim (this record). 2. `auto_update.py` + tests. 3. Wire into router/state, API tests. 4. Paper page status line and a
Settings toggle. 5. Drive `/paper/new` in a real browser. 6. Gates, release v2.2.0.

## Commands and outcomes

| Check | Result |
|---|---|
| `tests/test_auto_update.py` | 32 tests: which session is due (weekday evenings, mornings, weekends), every reason not to start (off, no running book, no baseline, not the app's own folder, busy, current), retry gap, 3-try cap, clean slate for a new session, someone else's download not counted, worker thread start/stop and server lifespan, API and the settings switch |
| Mutation check | removing the own-folder guard fails 1 test; removing the 3-try cap fails 3 |
| Real browser, `/paper/new` | typed "infy", Enter added the chip and cleared the box; "tcs" likewise; the name followed to "Buy and hold · INFY, TCS"; Start created the book and landed on `/paper/<id>` with tomorrow's orders (BUY INFY 480, BUY TCS 239). The earlier-unverified Enter-to-add path now verified |
| Real network, scratch data folder | with a running book and the data a session behind (1 Oct vs 2 Oct), the worker started a quick update by itself 30 s after launch: 495 stocks, mode `update`, shown on the Paper page as "Updating" with progress |
| Defects found by driving it | two stale sentences ("moves forward when you update your market data") on `/paper/new` and the book page; the pre-start status said "Updating" before anything had started. Both fixed |
| Defect in my own v2.1.0 tooling | `release.ps1` passed explicit file lists to ruff, which bypasses pyproject's `extend-exclude`, so its gate would fail on `.agents/` files that CI ignores. Fixed with `--force-exclude`; verified the tracked set then passes |
| Holiday handling found by the real run | 2 Oct 2026 was a market holiday, so a clean update ended with data still at 1 Oct and the first design reported "the latest session is 2 Oct" and would retry. Now two clean updates that find nothing newer settle as "no newer trading session, usually a market holiday"; failed runs keep the three-try path. Verified on the real network (status after the first clean run: "found nothing newer, which is normal on a market holiday. Next automatic try at 13:48") and by 3 added tests (35 total in the file) |
| Settings switch in a real browser | turned off: setting saved false, Paper page status OFF with its explanation; turned on again: updater resumed (clicked through the page's own control, because the browser pane's synthetic click needs the window on screen) |
| Gate in this dev checkout | not measurable: `test_halted_portfolio_refuses_trading_at_startup` reads the dev tree's real evidence store (`evidence/store.py:_verify_blobs`) and ran 20+ minutes. Not caused by this work (it imports nothing from `server/v2`) and instant on a clean tree |
| Gate in a clean clone at `51f0860ed` (CI-equivalent commands) | `ruff check .` clean; `ruff format --check .` 854 files clean; `mypy src launcher.py scripts` clean, 258 source files; `pytest tests` **2333 passed, 1 skipped** in 19m55s (skip: `test_windows_installer.py:140`, frontend not built in that clone). Frontend `npm test` 18 passed, `tsc --noEmit` clean |

## Files changed

New: `src/quant_system/server/v2/auto_update.py`, `tests/test_auto_update.py`. Edited: `server/v2/{router,state}.py`,
`frontend/src/lib/{queries,types}.ts`, `frontend/src/pages/{Paper,PaperNew,PaperBook,Settings}.tsx`, `scripts/release.ps1`.
Commits: `2354a80ae` (feature), `51f0860ed` (release gate fix).

Known limitation, not fixed here: a data folder downloaded by the pre-release v2.0.1 build has no `.quantos-download` marker, so
the app treats it as "not downloaded by QuantOS" (updates by hand, and a full download would sit beside it). Only a person who ran
the in-app download on that local build is affected; v2.1.0 was the first published release.

## Stop point / next safe action

**Completed 2026-10-05. v2.2.0 is released.** Release commit `dd7c8e200`, tag `v2.2.0`,
https://github.com/uninestindia-crypto/quant-system/releases/tag/v2.2.0 (installer, portable zip, SBOM, SHA256SUMS). The release was
founder-approved in this session's plan (item 4) and made with `-Force` because only 2 of 3 user-visible commits existed; the other
commit in the notes is Antigravity's `8c16bb488` (Lightning AI provider).

Verified after release: `bump_version.py --check` agrees on 2.2.0; `release_status.py` reports 0 of 3 since the new tag; the built
app (`dist/quantos/quantos.exe`, run on a scratch app root) reports 2.2.0, serves `/paper`, answers `/api/v2/paper/updates` and its
own update check; an installed 2.1.0 sees 2.2.0 and `QuantOS_v2.2.0_Setup.exe`. Working tree: tracked files clean, `main` equals
`origin/main`.

My verification clone was retired (it was mine). The manager session's clone `verify-gate-baseline-8c16bb4-...` was not touched.

**Not done, stated plainly**

- `Setup.exe` was not run (founder tests installs; it shares an AppId with the founder's install) and is not code-signed.
- The automatic update works only on data QuantOS downloaded itself. A person who connected their own research folder is told so on
  the Paper page and updates that folder themselves (a deliberate guard, tested).
- Exchange holidays are not known; they are detected after the fact (two clean updates that find nothing newer).
- The browser-pane synthetic click on the Settings switch needs the window on screen; the switch was exercised through the page's
  own control instead.
- Legacy v2.0.1 download folders lack the marker (see Files changed).
- In the dev checkout the full suite cannot finish because one paper-pilot test reads the real evidence store; the gate must be
  measured in a clean clone or CI. A follow-up worth filing: make that test not touch real data.

**Next safe action:** none required under this record. When `python scripts/release_status.py` says a release is due, run
`powershell -ExecutionPolicy Bypass -File scripts/release.ps1`.
