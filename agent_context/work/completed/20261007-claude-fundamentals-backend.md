# Work record: long-term fundamentals backend (facts from the company's own filings)

STATUS: COMPLETED (backend). Left in active/ for the coordinator to move at commit time.  
OWNER: Claude Code worker (fundamentals backend), spawned by the coordinator session  
TOOL: Claude Code  
STARTED_UTC: 2026-10-07  
STARTING_REVISION: e9fea0bca on `wip/halal-transparency` (shared checkout; other workers live in `frontend/**` and the
Shariah proof service)  
WORKTREE_OR_BRANCH: shared checkout, branch `wip/halal-transparency`, disjoint paths below  
RELATED: `agent_context/decisions/20261007-shariah-mode-and-filing-proof.md` (same honesty rules)

## Objective

GOAL_LINE: G6 (real benefit to retail users; the Portfolio is for long-term investing, so a person can read what a
company's own filings say). Serves the founder's request of 2026-10-07: "portfolio is for long term investment so add
more tools and features so users know what's best for investment, aka fundamental analysis" and "one person manages
many accounts".

The product gives **facts from the company's own filings, with proof and dates, and rules of thumb clearly labelled as
such**. It never says buy, sell, best, undervalued or recommend, and never promises returns (GOAL tripwire 4).

## Scope

1. `src/quant_system/fundamentals/` (models, extract, series, metrics, scorecard, store, service, views).
2. `scripts/build_fundamentals_snapshot.py` (developer/CI tool; NOT run in full, no `data/fundamentals/*.gz` written).
3. API `src/quant_system/server/v2/fundamentals_routes.py` (+ include in `router.py`), plus additive `lots` on the
   portfolio positions response (`portfolio.py`, `portfolio_accounts.py`).
4. Copilot read-only tool (`copilot/tools_fundamentals.py`, additive line in `copilot/tools.py`, one field in
   `copilot/registry.py`).
5. Tests `tests/fundamentals/**`, fixtures `tests/fixtures/fundamentals/**`, extended tool-catalog tests.

## Non-goals

No full snapshot build, no write to `data/fundamentals/`. No frontend. No network call in any test. No git add or
commit (the coordinator commits). No tax rates or tax amounts. No verdict words. Banks, lenders and non-Ind-AS
companies are reported `FORMAT_NOT_READ`, never guessed.

## Owned paths (new unless marked)

- `src/quant_system/fundamentals/**`
- `scripts/build_fundamentals_snapshot.py`
- `src/quant_system/server/v2/fundamentals_routes.py` (+ `fundamentals_jobs.py` if the job code needs its own file)
- `src/quant_system/server/v2/router.py` (ONE additive include line only)
- `src/quant_system/server/v2/portfolio.py`, `portfolio_accounts.py` (additive `lots` only)
- `src/quant_system/copilot/tools_fundamentals.py`; `copilot/tools.py` and `copilot/registry.py` (additive only)
- `tests/fundamentals/**`, `tests/fixtures/fundamentals/**`, additive cases in `tests/test_copilot_tools.py`

## Not touched

`frontend/**`, `src/quant_system/shariah/**` (read and reused only), `copilot/{cli_chat,ai_choice,conversations}.py`,
`server/v2/{copilot_ai,copilot_routes,updater,update_routes,state}.py`, `data/**`.

## Plan

1. Fixtures: one more real filing fetched ONCE, politely (September/March with balance sheet and the profit lines).
2. Models, extract (with tie-outs), series, metrics, scorecard, store (test-first).
3. Service, routes, jobs, portfolio fundamentals and lots.
4. Copilot tool and catalog tests.
5. Snapshot builder script; run with `--limit 2` to a temp output only.
6. Gates: pytest subset, ruff, mypy, check-code, check-tests, detect-secrets.

## Stop point (updated after each finished sub-step; newest first)

### FINAL (2026-10-09): backend complete, all gates green, nothing staged or committed

Ready to commit (new): `src/quant_system/fundamentals/` (23 modules), `src/quant_system/server/v2/{fundamentals_routes,holding_periods}.py`,
`src/quant_system/copilot/tools_fundamentals.py`, `scripts/build_fundamentals_snapshot.py`, `tests/fundamentals/` (19 files, 246 tests),
`tests/fixtures/fundamentals/` (4 real trimmed filings + README), this record.
Ready to commit (my hunks only in tracked files): `server/v2/router.py` (import + include line), `server/v2/portfolio.py` (import + `lot` key),
`server/v2/portfolio_accounts.py` (`lots`, `lots_note`), `copilot/tools.py`, `copilot/registry.py` (`fundamentals` field), `tests/test_copilot_tools.py` (4 cases).
Commands and outcomes (2026-10-09):
- `pytest tests/fundamentals tests -k "fundamental or portfolio or copilot or no_terminal"`: 1769 passed, 1 skipped (Windows-only), 3587 deselected.
- wider: `test_v2_*`, `test_live_routes`, `test_first_run_usability`, `test_portfolio_accounts`, `tests/shariah`: 1278 passed, 5 skipped.
- run again with a socket guard that refuses any non-local connection: 388 passed (no test touches the network).
- `ruff format --check` and `ruff check` on all 52 files: clean. `mypy --platform win32 src/quant_system/fundamentals server/v2 copilot scripts/build_fundamentals_snapshot.py`: no issues in 84 files.
- `check-code.mjs` on the 46 new files: clean (router.py keeps its old baseline findings, none on my lines). `check-tests.mjs`: clean. `detect-secrets`: 0 hits.
- Real run: `build_fundamentals_snapshot.py --only TCS,TATASTEEL --limit 2 --quarters 8` to a scratch folder: 16 filings read, all READ_OK, 0 failed; nothing written under `data/`.
Not done on purpose: the full snapshot build and `data/fundamentals/*.gz` (coordinator runs it); installer specs do not yet bundle `data/fundamentals`
(add it to `installer/quantos.spec`, `installer/quantos-studio.spec`, `quant_system.spec` once the snapshot exists, as for `data/shariah`).
Not run (Windows only): `scripts/audit-agent-claims.ps1`, `scripts/audit-disk-layout.ps1`.

### Earlier checkpoints


### After sub-step 4 (2026-10-09): Copilot tool and snapshot builder script written and tested

DONE: `copilot/tools_fundamentals.py` (+ `fundamentals` field in `ToolContext`, tool added to `default_registry`), additive
cases in `tests/test_copilot_tools.py`, `tests/fundamentals/test_fund_copilot_tool.py`; `scripts/build_fundamentals_snapshot.py`
+ `tests/fundamentals/test_fund_snapshot_script.py`. The prescribed pytest gate passes (1752 passed, 1 skipped).
NEXT: real `--limit 2 --out <scratch>` run against NSE, then gates (ruff format/check on my files only, mypy --platform win32,
check-code, check-tests, detect-secrets), final report.

### (earlier) After sub-step 3a (2026-10-09): jobs, runtime, routes, lots written and tested; 217 tests in tests/fundamentals green

DONE: `fundamentals/{jobs,runtime}.py`, `server/v2/{fundamentals_routes,holding_periods}.py`, one include line in
`server/v2/router.py`, additive `lot`/`lots` in `server/v2/{portfolio,portfolio_accounts}.py`, tests
`test_fund_{jobs,lots,routes,portfolio_routes}.py`, `jobs_support.py`. Existing `test_v2_api`, `test_portfolio*` still pass.
Coordinator note about `store.py` "not existing" was stale: it exists and the whole suite collects (182 then 217 tests).
NEXT: copilot tool (`copilot/tools_fundamentals.py`, additive lines in `tools.py`/`registry.py`) + catalog tests,
builder script + real `--limit 2` run to a temp output, gates (ruff format/check on my files only, mypy --platform win32,
check-code, check-tests, detect-secrets), final report.

### (earlier) After sub-step 2c (resumed 2026-10-09 after a second usage-limit reset): compare.py and portfolio_view.py written with tests

DONE: `fundamentals/{compare,portfolio_view}.py`, `tests/fundamentals/test_fund_{compare,portfolio}.py` (portfolio: one test
still failing on a test-setup omission, being fixed).
NEXT: jobs.py, runtime.py, `server/v2/fundamentals_routes.py` + one include line in `router.py`, lots, copilot tool,
builder script (+ `--limit 2` real run to a temp output), gates, then the final report with exact commit paths.

### (earlier) After sub-step 2b: scorecard, snapshot, store, reader, service, views, screen done and tested (144 tests green in tests/fundamentals)

Also DONE: `fundamentals/{scorecard,snapshot,store,reader,service,views,screen}.py`, tests `test_fund_{scorecard,store,reader,service,screen}.py`, `fakes.py`.
NEXT: compare.py, portfolio_view.py, jobs.py, runtime.py (default store paths), routes + router include line, lots
(portfolio.py/portfolio_accounts.py), copilot tool, builder script (+ `--limit 2` real run to a temp output), gates.

### (earlier) After sub-step 2a: fixtures, models, extract, series, metrics done and tested (62 tests green)

DONE: `tests/fixtures/fundamentals/*` (4 real trimmed filings + README), `src/quant_system/fundamentals/{__init__,models,lines,fmt,tieouts,extract,series,metric_types,metric_words,metrics_earnings,metrics_balance,metrics}.py`,
`tests/fundamentals/{support,test_fund_extract,test_fund_series,test_fund_metrics}.py`.
NEXT: scorecard.py, snapshot.py + store.py, reader.py (shared NSE reading), service.py + views, jobs.py, routes,
lots, copilot tool, builder script, gates (ruff format on my files only).

### Resumed after the usage-limit reset (coordinator message). Fixtures fetched.

Sub-step 0 result: record written, all reading done, design settled. Real filings fetched ONCE, politely (1.5 s pause,
through `NseFilingsClient`, 4 files) into the session scratchpad, NOT yet in the repository:
TCS 2024-09-30 consolidated (sha256 `af60aa3f...ccd461`), TCS 2024-12-31 consolidated (`6bdcf64f...e2160`),
TATASTEEL 2024-09-30 consolidated (`1cac16ef...fde8ab`, has debt and minority interest), HDFCBANK 2024-09-30 (bank
layout, for FORMAT_NOT_READ). Verified real tags: Income, Expenses, ProfitBeforeExceptionalItemsAndTax,
ExceptionalItemsBeforeTax, ProfitBeforeTax, TaxExpense, ProfitLossForPeriod, ProfitOrLossAttributableToOwnersOfParent,
ShareOfProfitLossOfAssociatesAndJointVenturesAccountedForUsingEquityMethod, EPS tag unit `INRPerShare` (reads as
INR/shares), balance sheet `Equity`, `EquityAttributableToOwnersOfParent`, `Liabilities`, `BorrowingsCurrent`,
`BorrowingsNoncurrent`. Quarter context is `OneD`; year-to-date is `FourD`. Identities hold exactly on both filings.
Nothing in the repository has been created or changed yet (git status shows only other workers' paths plus this record).
