# Work record: Shariah mode screens and the proof panel (frontend worker)

STATUS: COMPLETED (released in v3.2.0; remaining work is in agent_context/handoffs/20261009-claude-v3-2-0-release-handoff.md)  
OWNER: Claude Code (frontend worker, spawned by the coordinator of `20261007-claude-shariah-mode-and-filing-proof.md`)  
STARTING_REVISION: `e9fea0bca040a6821ab28202b5d748879c06a1b5` (checkout head when this record was written; the work began a few commits earlier on `wip/halal-transparency`)  
WORKTREE_OR_BRANCH: `/home/user/mizan`, branch `wip/halal-transparency`. No other worktree.

GOAL_LINE: G2 (one app, two real modes), G6 (retail benefit), tripwire 4 (no screen presented as a fatwa or an edge).

## Objective

Make Mizan Shariah mode a real, app-wide mode (the saved setting `shariah_mode`, not the route) and add the
Shariah proof panel to the stock page. Contract: `agent_context/decisions/20261007-shariah-mode-and-filing-proof.md`.

## Owned paths

New: `frontend/src/lib/{mode,proof,shariahStatus}.ts` and their tests, `frontend/src/components/mode/**`,
`frontend/src/components/proof/**`, `frontend/src/components/Watchlist.tsx`, and new `*.shariah.test.tsx` files beside
the screens. Mount-point edits only: `components/{Layout,OrderTicket,PaperPositions,common}.tsx`,
`pages/{Home,Markets,Paper,PaperBook,Portfolio,Settings,Stock}.tsx`, `components/PaperPositions.test.tsx` (query
client wrapper). Not touched: `pages/Shariah.tsx`, `components/shariah/**`, `lib/shariah.ts`, `lib/types.ts`,
`src/quant_system/**`, `tests/**`.

## Non-goals

No backend change, no commit, no change to what a paper book trades, no order placement, no claim of a fatwa.
The filings-engine message (segment names, industry groups) was sent to this worker by mistake and was withdrawn by
the coordinator; nothing was done for it.

## Steps and stop points

1. Mode setting, switch, notice (`lib/mode.ts`, `components/mode/ModeSwitch.tsx`, Layout). DONE. Gates: vitest, tsc.
2. Status lookup and badge (`lib/shariahStatus.ts`, `ShariahBadge`). DONE.
3. Filter, note, labels for paper books, watch guard. DONE.
4. Proof types and panel (`lib/proof.ts`, `components/proof/**`) written to the contract plus the coordinator's later
   additions (sector `status`, `basis`, `segments`; nullable `filing` and `xbrl_tag`; `value_inr` as text;
   `counted_in`). Fixtures are the engine's own output (`proofFixtures.data.json`). DONE.
5. Mounted on Home, Markets, Portfolio, search (palette and symbol picker), paper book screens, stock page. DONE.
6. Craft limits, secret scan, real-browser check. DONE.

## Gates (last run)

- `npx tsc --noEmit -p .`: clean.
- `npx vitest run` (whole suite): 69 files, 961 tests passed. My files: 16 files, 206 tests.
- `npm run build`: built.
- `node scripts/check-code.mjs` and `check-tests.mjs` on my files: clean. Edited shared files are no worse than HEAD
  (`Home.tsx` improved: nesting 4 to 3, long lines 23 to 20).
- `detect-secrets scan` on my files: no hits. `Settings.tsx` still has its 8 older hits and gained none.
- `pytest tests/test_no_terminal_copy.py`: 34 passed.
- Real browser (Chromium, real engine on a throw-away state folder, the new Shariah endpoints answered by route
  interception, five widths 320 to 1440, light and dark): 685 checks passed, 0 failed, including axe (no serious or
  critical violations) and no sideways scroll on every screen. Scripts and screenshots (232 files) are in the session
  scratchpad `.../scratchpad/mode/` (`modeqa.mjs`, `serve_mode.py`, `shots/`). That folder is outside the repository.

## Not verified

- The three new endpoints against the real engine (only fixtures shaped by `proof_builder.py`'s own output).
- The Welcome step and the Settings switch in a browser (unit-level: the switch follows a setting saved elsewhere).
- Screens listed in the final report as not covered (backtest trade lists, Copilot answers, Shariah pages).

## Next safe action

The coordinator reviews the diff, stages explicit paths, commits, and moves this record to `work/completed/`.
Nothing else is pending in this worker's scope.
