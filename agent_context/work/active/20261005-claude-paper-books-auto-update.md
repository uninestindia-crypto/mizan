# Active work: paper books keep themselves up to date

STATUS: ACTIVE  
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

## Files changed

(updated as work proceeds)

## Stop point / next safe action

(updated at completion)
