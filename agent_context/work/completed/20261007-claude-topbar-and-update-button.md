# Active work: informative top bar and "Update and restart" dialog

STATUS: COMPLETED  
OWNER: Claude Code (worker for the coordinator session)  
TOOL: Claude Code  
STARTED_UTC: 2026-10-07T16:00:00Z  
STARTING_REVISION: 83ee000c3 (HEAD when the build began; exploration began at e9fea0bca)  
WORKTREE_OR_BRANCH: shared checkout `/home/user/mizan`, branch `wip/halal-transparency`. No worktree. The coordinator commits; this record never stages or commits.

GOAL_LINE: G3 (a non-technical person uses the installed app without a terminal) and G7 (releases reach the founder: the installed app
updates itself from GitHub releases). Founder's words: "when i am searching it shows blue line which feels noob like and top bar of
software is empty which makes it feels noob like" and "what will happen when new update comes how will platform get updated".

## Objective

Frontend only. Replace the nearly empty `TopHeader` with a real top bar: the current screen's name (with a small parent link),
a search field that opens the existing palette, and compact status chips (market hours, price freshness, live prices, update
available), the existing Copilot button, and on narrow bars one "Status" popover. Add a standalone update dialog with an
"Update and restart" button (`useInstallUpdate` hook plus `UpdateDialog`) that the Settings About section can mount later. The
backend (`/api/v2/updates/install`) is finished and committed at e9fea0bca and is not edited.

## Owned paths

- `frontend/src/components/Layout.tsx` (edited in place; code moves OUT of it so it gets shorter)
- `frontend/src/pages/Settings.tsx`: two lines only (mount of `UpdateNowButton`), added on the coordinator's message of 2026-10-09
- NEW `frontend/src/components/topbar/**`
- NEW `frontend/src/components/update/**`
- NEW tests beside the above, and NEW pure helpers under `frontend/src/lib/` named `marketHours*`, `screenName*`, `updateInstall*` if needed
- This record

Not touched, by design: `lib/queries.ts`, `lib/types.ts` (another worker has uncommitted edits), `components/copilot/**`, `components/settings/**`,
`components/agents/**`, `components/mode/**` (the mode switch is kept where it is and not reworked), `pages/Portfolio.tsx`.

## Non-goals

- No backend change. No git add, commit or format run. No new model, trial or data work.
- The Windows install path itself cannot be exercised in this Linux container.

## Plan

1. Read the code, the backend contract, the existing patterns. DONE.
2. Pure helpers: market status from India time, freshness wording, screen names, update words and notes. DONE.
3. Update: `useInstallUpdate` hook, `UpdateDialog`, `UpdateNowButton`. DONE.
4. Top bar components, status popover, mount in `Layout.tsx` (old TopHeader code moved out). DONE.
5. Tests. DONE (191 tests in 10 files).
6. Gates: tsc, vitest (files, then all), build, craft checks, detect-secrets. DONE (see Commands).
7. Real-browser check, widths 320/390/768/1024/1440/1920, light and dark, axe, screenshots, keyboard. DONE.
8. Final report through the hand-back. DONE.

## Current step

Finished. Nothing is half-edited. Nothing is staged or committed (the coordinator commits).

SCOPE CHANGE, recorded: the coordinator's message of 2026-10-09 says "UpdateDialog mounted in Settings About". When it came,
`pages/Settings.tsx` had no uncommitted change (the other worker's edits were committed in c9a0f9341) and no active record
claims it (`20261007-claude-ai-apps-card-plain-words.md` lists it as a non-goal). I made the smallest edit that mounts it: one import
and one line `<UpdateNowButton />` in `UpdateLine` (the About section's update line). `UpdateNowButton` is my own component
(`components/update/UpdateNowButton.tsx`). To undo: delete those two lines.

Built so far (all NEW unless noted):
- `components/topbar/`: `marketHours.ts`, `priceFreshness.ts`, `screenName.ts`, `statusItems.ts`, `useStatusItems.ts`, `Chip.tsx`,
  `StatusPopover.tsx`, `StatusArea.tsx`, `ScreenTitle.tsx`, `SearchField.tsx`, `useBarLayout.ts`, `TopBar.tsx`, and tests
  `marketHours.test.ts`, `priceFreshness.test.ts`, `screenName.test.ts`, `statusItems.test.ts`
- `components/update/`: `updateInstall.ts`, `useInstallUpdate.ts`, `UpdateProgress.tsx`, `UpdateDialog.tsx`, `UpdateNowButton.tsx`,
  `updateKit.tsx` (test kit), tests `updateInstall.test.ts`, `UpdateDialog.test.tsx`
- `components/Layout.tsx` EDITED in place: 486 -> 365 lines. Removed the `UpdateNotice` banner, `TopHeader`, `MarketPill`, the sidebar's
  duplicate search button; mounts `<TopBar/>`, and `<StatusArea layout="phone"/>` in the phone bar; hides the brand word under 380 px.
- `pages/Settings.tsx` EDITED: the two lines described above.
- I did not touch `lib/queries.ts` or `lib/types.ts` (they carry another worker's uncommitted edits; my types and hooks live in my
  own folders).

Known unrelated `tsc` errors at the time of writing: another worker's `components/portfolio/HoldingFormDialog.test.tsx`.

Browser scratch: `/tmp/claude-0/-home-user-mizan/aff93908-a1c4-5a3a-9504-299f72a4de62/scratchpad/topbar/` (`serve_topbar.py` on port 8883
over my own build, `lib.mjs`, `look.mjs`). My build output goes to `.../topbar/dist`, never to the shared `static/app`.

## Decision rationale

- The chips decide between "all shown" and "one Status popover" from the bar's measured width in script (one variant in the page at a
  time, testable with a pure function), while the mode switch and Copilot button keep their own CSS container-query breakpoints.
- The old full-width "QuantOS X is available" banner is replaced by the update chip; one place to learn about an update.
- A popover built as a disclosure (button with expanded state, Escape and outside click close, focus returns) because no popover
  library is installed and `package.json` is shared.
- Holidays: `data/authorities/nse-trading-holidays.json` exists on disk but no `/api/v2` response carries it, so the first version says
  "Market hours" style wording only from the clock and never claims "open" on a day it cannot rule out as a holiday (see below).

## Commands and outcomes

| Command | Result | Evidence/notes |
|---|---|---|
| `cd frontend && npx tsc --noEmit -p .` | PASS | whole frontend, no errors |
| `npx vitest run src/components/topbar src/components/update` | PASS | 10 files, 191 tests |
| `npx vitest run` (whole suite) | PASS | 90 files, 1294 tests (79 files / 1099 tests without mine at the first full run) |
| `npx vite build --outDir <scratch>/dist` | PASS | built to my scratch folder, not the shared `static/app`, so no one's running server was disturbed. `npm run build` is `tsc` plus this build; both parts pass |
| `node scripts/check-code.mjs` on `components/topbar` and `components/update` | PASS | clean, 29 files |
| `node scripts/check-tests.mjs` on the same | PASS | clean, 10 test files |
| `check-code` on `Layout.tsx` | no worse | findings 19 (HEAD) -> 16, the god-file finding is gone; 486 -> 365 lines |
| `check-code` on `Settings.tsx` | no worse | 106 -> 106 (two lines added) |
| `uv run --frozen detect-secrets scan` on my files | PASS for mine | `Settings.tsx` reports 8 "Secret Keyword" lines (456-519) that are the names of saved settings (rows that hold a name, never a value), not mine; my two lines add none; my two lines add none |
| real browser (`qa.mjs`): bar x 6 widths x 2 themes | PASS 48/48 | no sideways scroll, no spill, axe no serious or critical |
| real browser: Status popover x 5 widths x 2 themes | PASS 50/50 | opens inside the window, Escape closes and returns focus, axe clean with it open |
| real browser: update dialog idle/downloading/checking/installing/failed/409 x 4 widths x 2 themes | PASS 96/96 | axe clean in idle, downloading, installing, failed |
| real browser: short windows 320x568, 390x667, 1366x600 | PASS 3/3 | the dialog fits; its body scrolls on a short window |
| real browser: Tab walk, focus ring, Ctrl K | PASS 10/10 | order: sidebar, theme, bar (way back, search, mode, chips, Copilot), page |
| real browser: Settings, About with and without an update | PASS | one "Update and restart" button with an update, none without; axe clean; Escape returns focus to the button |

NOT verified: the real Windows install path (the installer is not run here; the engine refuses on Linux by design). Everything the
dialog shows for downloading, checking, installing, failed and "nothing newer" was driven by a stand-in for the engine's answers.

## Files changed

- NEW `frontend/src/components/topbar/`: `TopBar.tsx`, `ScreenTitle.tsx`, `SearchField.tsx`, `Chip.tsx`, `StatusPopover.tsx`, `StatusArea.tsx`,
  `useBarLayout.ts`, `useStatusItems.ts`, `statusItems.ts`, `marketHours.ts`, `priceFreshness.ts`, `screenName.ts`, and tests
  `TopBar.test.tsx`, `StatusArea.test.tsx`, `useBarLayout.test.tsx`, `statusItems.test.ts`, `marketHours.test.ts`,
  `priceFreshness.test.ts`, `screenName.test.ts`, kit `topbarKit.tsx`
- NEW `frontend/src/components/update/`: `UpdateDialog.tsx`, `UpdateProgress.tsx`, `UpdateNowButton.tsx`, `useInstallUpdate.ts`,
  `updateInstall.ts`, and tests `UpdateDialog.test.tsx`, `UpdateNowButton.test.tsx`, `updateInstall.test.ts`, kit `updateKit.tsx`
- EDITED `frontend/src/components/Layout.tsx`: mounts `TopBar` and the phone `StatusArea`; removed the old banner, `TopHeader`,
  `MarketPill` and the sidebar's duplicate search button
- EDITED `frontend/src/pages/Settings.tsx`: one import and one `<UpdateNowButton />` line in the About update line
- NEW (this record): `agent_context/work/completed/20261007-claude-topbar-and-update-button.md`

## Blockers and conflicts

None. `lib/queries.ts`, `lib/types.ts`, `pages/Portfolio.tsx`, `components/portfolio/**` carry another worker's uncommitted edits and
are not mine; do not include them in the commit for this work.

## Stop point

All work done and verified as listed. Working tree: my files are untracked/modified and uncommitted.

## Next safe action

The coordinator commits the paths listed under "Files changed" (explicit paths, no `git add -A`). Open for the founder: a holiday
list is not served by the engine, so the market chip says "Market hours", never "Market open"; if `/api/v2/status` ever carries the
NSE holiday list, pass it to `marketStatus(now, holidays)` and the chip will say "Market open" and "Market closed" on a holiday.
