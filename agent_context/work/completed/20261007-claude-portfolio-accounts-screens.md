# Active work: Portfolio multiple-accounts screens

STATUS: COMPLETED (all gates passed; the coordinator stages and commits)  
OWNER: Claude Code (portfolio accounts worker)  
TOOL: Claude Code  
STARTED_UTC: 2026-10-07T15:20:00Z  
STARTING_REVISION: 082db3a15bef833e24bd2612dde73b325ae7edbe  
WORKTREE_OR_BRANCH: /home/user/mizan (shared checkout), branch wip/halal-transparency. No worktree created.

## Objective

GOAL_LINE: G6 (real benefit to retail users: one person manages many accounts and sees each one and all of them).

Build the Portfolio multiple-accounts screens on the finished backend (`/api/v2/accounts`, `/api/v2/portfolio?account=`):
account switcher (URL `?account=`, remembered), per-account summary cards, By stock / By lot views, Manage accounts
dialog (add, edit, delete with move-holdings step), holding form with an Account choice, and a `PortfolioTabs` registry
as the extension point for a later Fundamentals tab. Shariah-mode filtering on Portfolio stays exactly as it is.

## Owned paths

- `frontend/src/pages/Portfolio.tsx`
- `frontend/src/components/portfolio/**` (new)
- `frontend/src/lib/queries.ts`, `frontend/src/lib/types.ts` (append only, via Edit; another worker also appends)
- `frontend/src/pages/Portfolio*.test.tsx` and tests under `frontend/src/components/portfolio/**`
- my scratch folder only for the browser check (outside the repository)

Not touched: `frontend/src/components/HoldingDialog.tsx` (shared with Stock.tsx, not mine; the portfolio gets its own
form in `components/portfolio/`), `components/copilot/**`, `components/settings/**`, `components/agents/**`,
`components/Layout.tsx`, `components/topbar/**`, `components/update/**`.

## Non-goals

- Fundamentals tab (only the extension point).
- Any backend change. No git add / commit (the coordinator commits).

## Plan

1. Types and queries (append only). DONE (types.ts: PortfolioRow/Portfolio extended, Account types appended; queries.ts: HoldingInput.account_id; new hooks in components/portfolio/accountQueries.ts)
2. Account state: URL param + remembered choice. DONE (useAccountChoice.ts)
3. Switcher, summary cards, views (By stock, By lot), tabs registry. DONE (compiles; not yet tested)
4. Manage accounts dialog; holding form with Account. DONE (compiles; not yet tested)
5. Page restructure under 400 lines per file. DONE (pages/Portfolio.tsx now 55 lines)
6. Tests. DONE: written and green: pages/Portfolio.accounts.test.tsx (15), components/portfolio/{HoldingsViews,ManageAccounts,DeleteAccount,HoldingFormDialog}.test.tsx (+kits portfolioKit.tsx, managerKit.tsx); existing pages/Portfolio.shariah.test.tsx fixture updated to the new answer shape (3 tests still green). TODO: AccountSwitcher/Picker, AccountCards, PortfolioTabs tests.
7. Gates: DONE
8. Real-browser check: DONE

## Current step

Steps 1-5 written and `npx tsc --noEmit -p .` clean. Next: update the existing Shariah test fixture to the new answer
shape, write the tests (step 6), then craft-check long lines/functions, then gates and the real-browser check.

## Decision rationale

- Old account-less answers: `GET /api/v2/portfolio` with no query means all accounts, so "All accounts" keeps calling
  that exact URL and shares the Home page cache; one account calls `?account=<id>`.
- The switcher list comes from the portfolio answer (`accounts` is returned even for one account and for an empty
  one), so the page never needs a second call just to draw the switcher. `GET /api/v2/accounts` is used by Manage
  accounts (it carries the fixed list of kinds).
- One account only: no switcher, no cards, no Account column (no clutter); the Manage accounts button stays.
- `components/HoldingDialog.tsx` is shared with the stock page and is not in my owned paths, so the portfolio gets a
  sibling form with the Account choice.
- Observed 2026-10-07: the Shariah worker's edits to `pages/Portfolio.tsx` appear as uncommitted changes against HEAD
  (their record says COMPLETED_UNCOMMITTED). I build on the working-tree version and keep that behaviour exactly.

## Commands and outcomes

| Command | Result | Evidence/notes |
|---|---|---|
| (none yet) | | |

## Files changed

- `frontend/src/lib/types.ts`: PortfolioRow gains account_id/account_name; Portfolio gains scope/accounts/positions; Account types appended.
- `frontend/src/lib/queries.ts`: `HoldingInput.account_id?` (one line).
- `frontend/src/pages/Portfolio.tsx`: rewritten as a thin page (keeps the Shariah filter behaviour via the new tables).
- `frontend/src/components/portfolio/*`: new (switcher, picker, cards, tables, tabs, manage dialog, holding form, queries,
  phone layout hook, tests and two test kits).
- `frontend/src/pages/Portfolio.accounts.test.tsx`: new page-level tests.
- `frontend/src/pages/Portfolio.shariah.test.tsx`: fixture only (adds scope, accounts, positions, account fields so it
  matches the engine's answer); its three tests and assertions are unchanged.
- `agent_context/work/active/20261007-claude-portfolio-accounts-screens.md`: this record.

## Blockers and conflicts

- `pages/Portfolio.tsx` carried the Shariah worker's edits; preserved (filter, badges, hidden count, totals sentence).
- `components/HoldingDialog.tsx` (shared with the stock page) was not touched, so "Add to portfolio" on a stock page
  still sends no account and the engine puts it in the first account. Needs a decision (see report).

## Stop point

(2026-10-09) DONE. Nothing staged or committed.
Gates (all run in `/home/user/mizan/frontend` unless stated): `npx tsc --noEmit -p .` clean; `npx vitest run` 90 files,
1295 tests pass (my 10 files: 104 tests); `npm run build` passes; `node scripts/check-code.mjs` clean on 34 files and
`node scripts/check-tests.mjs` clean on 10 files (repository root); `uv run --frozen detect-secrets scan` found nothing.
Real-browser check (real engine, scratch build, 4 seeded accounts): 456 view checks (6 widths x light/dark) and 60 flow
checks pass, axe no serious or critical issue, no sideways scroll. Screenshots in the scratchpad `accounts/shots/`.
Fundamentals tab: NOT built (backend not ready); `PortfolioTabs` + `tabRegistry.tsx` is the extension point.
Not run: `scripts/audit-agent-claims.ps1` and `audit-disk-layout.ps1` (PowerShell, not available here).

### Earlier stop point

Steps 1-5 done and tsc clean. Step 6: 70+ tests green (see plan line 6). A resume writes the remaining tests (switcher/picker, cards, tabs), then runs craft checks (long lines > 120 and functions > 50 lines in the new files), then gates (step 7) and the browser check (step 8).

## Next safe action

Coordinator: stage and commit the paths listed under "Files changed". Next round: Fundamentals tab, by adding a line to `tabRegistry.tsx` once its backend lands.
