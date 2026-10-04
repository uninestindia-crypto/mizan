# Active work: in-app paper trading, quick data updates, and a standing release routine

STATUS: ACTIVE  
OWNER: Claude Code session (founder instruction 2026-10-04: "build in-app paper trading and make sure after every few
major updates a new release happens on GitHub, make it a rule so that every time I can update my software"; later: use the
Antigravity CLI on Gemini 3.8 Flash (high) for the less demanding work)  
TOOL: Claude Code (with `agy --model gemini-3.8-flash-high` for delegated mechanical pieces; its edits are reviewed and
verified here, and it is told not to run git)  
STARTED_UTC: 2026-10-04  
STARTING_REVISION: 67e6eba61 (main, pushed)  
WORKTREE_OR_BRANCH: the install root, branch `main` (shared checkout, no worktree; another agent's uncommitted
`scripts/generate_moonshot_pdf.py`, its PDF and a completed record are in the tree and are NOT mine)

## Objective

1. Paper trading inside the app: a person starts a "paper book" (a strategy from the Strategy Lab, a stock list or universe,
   virtual money) and the app follows it day by day on real prices with the lab's exact costs and next-open fills. No live
   orders, ever.
2. A quick "Update market data" (a recent window, not the full ten years) so a book can move forward each day.
3. A release routine: a rule in `AGENTS.md`, a status check that says when a release is due, scripts to bump the version
   everywhere, build, tag and publish a GitHub release, and an in-app "update available" notice.

## Owned paths

- `src/quant_system/lab/simulator.py` (optional queued-orders output only), `src/quant_system/lab/paper.py` (new)
- `src/quant_system/market/downloader.py`, `tests/test_market_downloader.py`
- `src/quant_system/server/v2/{state,router,schemas,paper_books,updates}.py`
- `frontend/src/pages/{Paper,PaperBook,PaperNew,LabRun}.tsx`, `frontend/src/App.tsx`, `frontend/src/lib/{queries,types}.ts`,
  `frontend/src/components/**` (update notice)
- `tests/test_paper_books.py`, `tests/test_release_tooling.py`, `tests/test_updates.py`, `tests/test_lab.py` (additive)
- `scripts/{bump_version.py,release_status.py,release_notes.py,release.ps1}`
- `AGENTS.md` (one added rule; founder-instructed), `agent_context/decisions/20261004-release-cadence.md`
- version files at release time: `pyproject.toml`, `src/quant_system/__init__.py`, `frontend/package.json`,
  `src/quant_system/server/static/index.html`, `uv.lock` (the project's own version line only)

## Non-goals

- No live order routing. No change to accounting, risk governor, evidence or modelling code.
- Not touching `scripts/generate_moonshot_pdf.py`, `docs/QuantOS_Moonshot_Strategic_Whitepaper.pdf` or
  `agent_context/work/completed/20261004-antigravity-quantos-moonshot-pdf.md`.
- No code signing (needs the founder's certificate).

## Design decisions (rationale)

- A paper book is a saved Strategy Lab spec that is re-simulated from its start session to the latest data each time the
  market data changes. The simulator is deterministic and already decides at a close and fills at the next open, so the
  replay equals what live paper trading would have done, and no second engine exists to disagree with the lab.
- A book starts at the latest session in the data at creation: its first decision uses only prices up to then and its first
  fills are the next session's real opens. Tomorrow's queued orders are shown (decisions taken at the last close).
- Each session's recorded equity is stored once and never rewritten; if the data provider later re-adjusts history and the
  replay disagrees with what was recorded, the book says so instead of silently changing its past.
- Books are stopped, never deleted, for the same reason lab runs are never deleted: failures stay visible.
- A held stock that has a demerger or rights issue inside the book's window cannot be valued; the book says so.

## Plan / current step

1. Claim (this record). 2. Release tooling delegated to Flash while the paper-trading core is written here.
3. Downloader: ten-year baseline as a history cache, updates as a recent refresh cache. 4. Simulator queued orders, paper
evaluation, storage, API. 5. Frontend. 6. Verification in a real browser. 7. First release `v2.1.0` with the new routine.

## Commands and outcomes

| Check | Result |
|---|---|
| `lab/paper.py` replay engine | 8 tests incl. the property that replaying with less future data gives the same past (no look-ahead), a book started on the last session shows tomorrow's queued orders, demerger inside the window flags ATTENTION |
| Paper-book API | 9 tests: create, list, stop (never delete), 20-book limit, survives restart, recorded equity never rewritten and a provider re-adjustment is reported, a book that cannot be replayed explains why |
| Real data (493 downloaded stocks) | a backdated trend book on INFY+TCS replayed 65 sessions with real fills, charges and slippage: -6.56% vs NIFTY -6.19% |
| Downloader: ten-year baseline + 3-year recent window | 19 tests; "update" mode re-reads only the recent window, keeps the baseline, prunes only caches carrying the download's marker; a same-day re-run resumes instead of updating |
| Bug found by driving the app | `/paper/new` and `/paper/<id>` 404 on reload because the server's page list did not include them; fixed, and a test now checks every route in `App.tsx` is served |
| Update notice | 8 tests; public GitHub API first, then the signed-in `gh` CLI (the repository is private); a failed check is silent |
| Release tooling | `bump_version.py` (+ `--next`, `--check`), `release_status.py` (+ suggested bump), `release_notes.py`, `release.ps1` (parses; `-DryRun` shows plan); tests for each; a repository-wide test that every version file agrees |
| Delegation | Antigravity CLI, `gemini-3.8-flash-high`, `--mode accept-edits`: wrote the three release scripts, their tests and the decision record (reviewed, one flaky read of a half-written file, otherwise correct), and the two paper pages `PaperNew.tsx` and `PaperBook.tsx` (typechecked and driven against real data, one backend shape bug of mine found in the process). The delegate was told not to run git or any command; I stopped its process after each run |

## Files changed

See the commits. New: `lab/paper.py`, `server/v2/{paper_books,updates}.py`, `frontend/src/pages/{PaperNew,PaperBook}.tsx`,
`scripts/{bump_version,release_status,release_notes}.py`, `scripts/release.ps1`, `tests/test_{paper_books,paper_books_api,updates,release_tooling}.py`,
`agent_context/decisions/20261004-release-cadence.md`. Rule added to `AGENTS.md`.

## Stop point / next safe action

(updated at completion)
