# Active work: Fundamentals screens (Portfolio tab, Stock page section, Fundamentals screen)

STATUS: COMPLETED (all gates passed; the coordinator stages and commits)  
OWNER: Claude Code (fundamentals screens worker)  
TOOL: Claude Code  
STARTED_UTC: 2026-10-09T12:12:00Z  
STARTING_REVISION: de5347b1d (HEAD on wip/halal-transparency; Portfolio accounts commit 995acbaa4 and fundamentals backend commit b34b236f6 are both in it)  
WORKTREE_OR_BRANCH: /home/user/mizan (shared checkout), branch wip/halal-transparency. No worktree created.

## Objective

GOAL_LINE: G6 (real benefit to retail users: a long-term investor can read what a company's own filings say).

Build the three fundamentals screens on the committed backend (`/api/v2/fundamentals*`, `/api/v2/portfolio/fundamentals`):

1. Portfolio "Fundamentals" tab (added through `components/portfolio/tabRegistry.tsx`), plus each position's `lots` in the
   By-stock expander.
2. Stock page section "Results from the company's own filings", with a "Get the latest results" button (start, progress,
   cancel, failures, refresh), and "Add to portfolio" on the Stock page switched to the account-aware holding form.
3. A "Fundamentals" screen (filters, sort, results with counts, compare view), one route and one sidebar entry.

Honesty rules (GOAL tripwire 4): facts with proof and dates only. No ranking, no good/bad colouring, no buy/sell/best/
cheap/undervalued/target/should, no tax amounts or rates, no invented numbers. Labels, thresholds and the header line
come from the engine exactly as sent.

## Owned paths

- `frontend/src/lib/fundamentalsTypes.ts` (new), `frontend/src/lib/fundamentalsQueries.ts` (new)
- `frontend/src/components/fundamentals/**` (new)
- `frontend/src/components/portfolio/tabRegistry.tsx` (one line), and new files under `frontend/src/components/portfolio/`
  named `Fundamentals*` / `Lots*` (new); small edits to `StockTable.tsx` (lots in the expander) only
- `frontend/src/pages/Stock.tsx` (the new section and the Add to portfolio dialog only)
- `frontend/src/pages/Fundamentals.tsx` (new) and its tests
- `frontend/src/App.tsx` (one route), and the one nav entry plus screen-name entry in `frontend/src/components/Layout.tsx`
  and `frontend/src/components/topbar/screenName*` (only if the screen-name table needs the entry)
- `src/quant_system/server/v2/spa.py` (ONE line: `"/fundamentals"` added to `CLIENT_ROUTES`), claimed on the coordinator's
  instruction of 2026-10-09 (the page list test `test_every_page_the_web_app_defines_is_served_on_reload` needs it)
- tests for all of the above

Not touched: `lib/types.ts`, `lib/queries.ts`, `components/HoldingDialog.tsx` (other users keep it), `components/topbar/**`
beyond the screen-name entry, `components/copilot/**`, `components/settings/**`, `components/agents/**`, `components/update/**`.

## Non-goals

- Any backend change. No git add or commit (the coordinator commits).
- Tax amounts or rates; any ranking, scoring of "good/bad", recommendation wording.

## Plan

1. Read the backend contract and examples. DONE
2. `fundamentalsTypes.ts`, `fundamentalsQueries.ts`. DONE
3. Shared pieces under `components/fundamentals/`. DONE
4. Stock page section + fetch job + Add to portfolio switch. DONE
5. Portfolio Fundamentals tab + lots in the expander. DONE
6. Fundamentals screen (filters, results, compare) + route + nav entry. DONE
7. Tests for each. DONE
8. Gates: DONE
9. Real-browser check: DONE

## Current step

Steps 1-4 written and compiling (types, queries, `components/fundamentals/*`, Stock page section and Add-to-portfolio switch).
Now: engine-built fixtures + tests for the Stock section, then the Portfolio tab, then the Fundamentals screen.

## Decision rationale

(filled in as decisions are made)

## Commands and outcomes

| Command | Result | Evidence/notes |
|---|---|---|
| (none yet) | | |

## Files changed

New: `frontend/src/lib/{fundamentalsTypes,fundamentalsQueries}.ts`; `frontend/src/components/fundamentals/**` (26 files incl. 5 test
files, a test kit and the engine-built fixtures); `frontend/src/components/portfolio/{FundamentalsTab,FundamentalsSummary,
FundamentalsHoldings,FundamentalsNoData,SectorWeights,LotsList}.tsx` + `FundamentalsTab.test.tsx`, `StockLots.test.tsx`;
`frontend/src/pages/Fundamentals.tsx`, `frontend/src/pages/Stock.fundamentals.test.tsx`; this record.
Edited: `frontend/src/pages/Stock.tsx`, `frontend/src/App.tsx` (route), `frontend/src/components/Layout.tsx` (nav entry),
`frontend/src/components/topbar/screenName.ts` + `.test.ts` (one row each), `frontend/src/components/portfolio/{tabRegistry,
StockTable,HoldingFormDialog,useAccountChoice}.ts(x)` + `PortfolioTabs.test.tsx`, `src/quant_system/server/v2/spa.py` (one line).

## Blockers and conflicts

None yet.

## Stop point

(2026-10-09, after the 17:10 UTC reset) DONE. Nothing staged or committed. No git merge/pull/checkout/stash was run.
Gates, all run in this shared checkout:
- `cd frontend && npx tsc --noEmit -p .`: clean.
- `npx vitest run` (whole suite): 99 files, 1493 tests pass. My 7 new test files: 129 tests (CompareView 13, FundamentalsScreen 19,
  FundamentalsSection 59, GetResults 9, FundamentalsTab 16, StockLots 8, Stock.fundamentals 5). The No-Terminal copy guard passes.
- `node scripts/check-code.mjs` clean on 71 files of mine; shared files no worse than HEAD (Stock.tsx 18 -> 17 findings,
  Layout.tsx 16 -> 16, App.tsx 4 -> 4). `node scripts/check-tests.mjs` clean on 16 test files.
- `uv run --frozen detect-secrets scan` on every path I touched: none. (The fixtures' 64-character filing fingerprints were
  swapped for simple stand-ins because a secret scanner flags them; they are public hashes, not secrets.)
- `uv run --frozen pytest tests/test_v2_api.py`: 21 passed, 1 skipped (Windows only), including
  `test_every_page_the_web_app_defines_is_served_on_reload` with `/fundamentals` now in `spa.py`.
  `tests/test_copilot_routes.py::test_status_lists_providers_and_never_returns_a_key` fails for a reason outside my paths
  (`live_prices.message` is None; another helper's staged market-holiday/router work).
- Scratch `vite build` (never the shared static folder) served with the real engine on a throw-away state folder, seeded
  with filings and four accounts: 400 view checks pass (320/390/768/1024/1440 x light/dark), axe no serious or critical
  issue, no sideways scroll, plus the real "Get the latest results" run at two sizes (8 checks).
Not verified: a successful NSE read (only a plain-words refusal "NSE lists no quarterly results filing ..." for an ETF was
seen); the bank layout on a stock page (no bank symbol is in the fixture market data, covered by unit tests and the API);
any browser except Chromium; the installer specs do not yet bundle `data/fundamentals` (backend record says so).

## Next safe action

Coordinator: stage and commit the paths listed under "Files changed". Not for this release (the founder's merge to main is
done in a separate clone).
