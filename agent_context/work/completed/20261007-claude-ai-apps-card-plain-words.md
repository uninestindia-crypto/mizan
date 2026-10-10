# Active work: Settings > AI assistants > "Set up AI apps on this computer" card in plain words

STATUS: COMPLETED  
OWNER: Claude Code (worker spawned by the coordinator session)  
TOOL: Claude Code  
STARTED_UTC: 2026-10-07T19:59:00Z  
STARTING_REVISION: c9a0f934156d562d1e5cad4319b4b243b8c15efa  
WORKTREE_OR_BRANCH: shared checkout `/home/user/mizan`, branch `wip/halal-transparency` (no worktree; disjoint paths below)

## Objective

GOAL_LINE: G3 (a non-technical person installs and runs it; no terminal), serving the No-Terminal Law (G-tripwire 9).

Rewrite `frontend/src/components/AgentCliBridge.tsx` (the card that installs and signs in the AI apps on this computer)
to match the new story (the Copilot's default AI is the signed-in AI app on the computer): titled "Set up AI apps on this
computer", one plain line, one state and one next-step button per app, no terminal controls, product names without "CLI",
and a refresh of the Copilot's AI check when an install or sign-in ends so the two cards agree within a second.

## Owned paths

- `frontend/src/components/AgentCliBridge.tsx`
- `frontend/src/components/aiapps/**` (new; pieces split out of the card)
- `frontend/src/components/AgentCliBridge*.test.tsx` and `frontend/src/components/aiapps/*.test.*` (new tests)
- `frontend/src/lib/noTerminalRule.test.ts` (remove the paid debt entry)

Minimal in-place edits to files outside that list, each one forced by the change (each is stated in the final report):

- `frontend/src/lib/queries.ts`: narrow `useLaunchCli` (no `run`/`custom` action, no `custom_command`). Region: `useLaunchCli` only.
  Another worker appends to this file; an Edit on one region only.
- `frontend/src/lib/types.ts`: drop `AgentCli.run_cmd` and `AgentCli.install_steps`. Region: `AgentCli` only.
- `frontend/src/lib/aiSource.ts` + `frontend/src/lib/aiSource.test.ts` + `frontend/src/components/settings/AiSource.test.tsx`
  (one fixture line): the "Set up" jump finds a card by its title text equal to the backend name ("Codex CLI"). The card
  titles lose "CLI", so the jump would silently stop landing on the right card. The card now carries `data-app-name`.
- `frontend/src/components/settings/AiSourceTest.tsx`: an optional `quiet` prop (and an optional `subject`) so the existing
  "Test this AI" flow can sit in an app card as a quiet link instead of being duplicated.

## Non-goals

- No backend change (the `/api/v2/cli/launch` endpoint keeps its `run` and `custom` actions; the screen just stops calling them).
- No edit to `pages/Settings.tsx`, `pages/Tools.tsx`, `components/topbar/**` (the "Coding agents" tab and screen name there are
  reported, not changed).
- No faster polling. No commit, no stage, no formatter.

## Plan

1. Record (this file). DONE
2. Words and state helpers: `components/aiapps/appWords.ts`. DONE
3. Pieces: `AppCard.tsx`, `JobProgress.tsx`, `useAppSetup.ts` (+ job-end refresh), then `AgentCliBridge.tsx` thin. DONE
4. Narrow `useLaunchCli` / `AgentCli`; `aiSource.ts` jump; `AiSourceTest` quiet prop; guard debt entry removal. DONE
5. Tests: wording, states, no terminal control, refresh after job, existing behaviours. DONE (36 new tests)
6. Gates: tsc, vitest (files, then whole), craft checks, detect-secrets. DONE
7. Real-browser look at 390 and 1280, light and dark, axe. DONE (own server copy, faked jobs, port 8882, stopped)

## Current step

Finished. Handed to the coordinator to commit.

## Decision rationale

- Backend `signin_mode` for Gemini is `terminal`: its sign-in opens a window. That cannot be fixed from the frontend; the card
  keeps the existing sign-in behaviour and the follow-up note, and the limitation is reported.
- The old "What Install will run" disclosure printed shell commands (`irm ... | iex`, `npm install -g ...`). That is a code term
  shown to a non-programmer, so it becomes one plain sentence.
- `auth_detail` can read "Using the ANTHROPIC_API_KEY key saved in QuantOS" (a setting name), so the card shows its own
  plain state words and does not print `auth_detail`.
- A fourth state exists in the data (installed, sign-in cannot be read, `UNKNOWN`); it is shown as "Installed, not checked yet"
  with Sign in and the quiet test, consistent with the card above ("Not checked yet. Press Test this AI.").

## Commands and outcomes

| Command | Result | Evidence/notes |
|---|---|---|
| `cd frontend && npx tsc --noEmit -p .` | PASS (exit 0) | after the last edit |
| `npx vitest run AgentCliBridge.test.tsx AgentCliBridge.jobs.test.tsx` | PASS 36/36 | new; the card had no tests before |
| `npx vitest run <those> src/lib/noTerminalRule.test.ts src/lib/aiSource.test.ts src/components/settings src/pages` | PASS 14 files, 192 tests | guard passes with the debt entry gone |
| `npx vitest run` (whole) | PASS 89 files, 1284 tests | an earlier whole run had 2 failures in another worker's unfinished `topbar/statusItems.test.ts`; gone in the last run |
| mutation check: disable the job-end refresh | 3 refresh tests FAIL, 14 pass; restored | proves the tests bite |
| `node scripts/check-code.mjs` / `check-tests.mjs` on my files | clean | `noTerminalRule.test.ts` and `aiSource.test.ts` keep findings that were there before (loops in the guard, one long line) |
| `uv run --frozen detect-secrets scan <my files>` | no candidates | |
| `npx vite build --outDir <scratchpad>/appscard/ui --emptyOutDir` | PASS | `src/quant_system/server/static` untouched |
| real browser, `scratchpad/appscard/qa.mjs`, real engine with faked apps and jobs | all PASS | 4 themes/widths x 2 worlds, axe 0 violations, install/sign-in/failure/window/test/jump flows; Codex card and the AI choice card showed Codex ready 20 to 40 ms apart |

## Files changed

- `frontend/src/components/AgentCliBridge.tsx`: thin card, new title and words, no terminal controls
- `frontend/src/components/aiapps/appWords.ts`, `AppCard.tsx`, `JobProgress.tsx`, `useAppSetup.ts` (new): words, one app's card, job progress, job-end refresh
- `frontend/src/components/aiapps/appFixtures.tsx` (new): shared fake engine for the tests
- `frontend/src/components/AgentCliBridge.test.tsx`, `AgentCliBridge.jobs.test.tsx` (new)
- `frontend/src/lib/noTerminalRule.test.ts`: debt entry removed
- `frontend/src/lib/queries.ts` (4 hunks: `keys.agentClis`, narrowed `useLaunchCli`), `frontend/src/lib/types.ts` (`AgentCli`: `install_steps`, `run_cmd` removed)
- `frontend/src/lib/aiSource.ts`, `aiSource.test.ts`, `components/settings/AiSource.test.tsx`: the Set up jump finds a card by `data-app-name`
- `frontend/src/components/settings/AiSourceTest.tsx`: optional `quiet` and `subject`

## Blockers and conflicts

None. Concurrent workers edit `components/copilot/**`, `components/topbar/**`, `components/portfolio/**`, `pages/Portfolio.tsx`,
`lib/queries.ts` and `lib/types.ts` (append only); my edits to the last two touch different regions.

## Stop point

Complete. Nothing staged or committed by me. Not true yet: Gemini sign-in still opens a window, because the engine marks its
sign-in as needing one (`cli_bridge.py` `signin_mode="terminal"`); only an engine change makes it a hands-off browser job.
The Tools screen tab and the top bar screen name still say "Coding agents" (not mine).

## Next safe action

Coordinator commits the paths listed under Files changed. `queries.ts` and `types.ts` also hold another worker's uncommitted
hunks (`account_id` in `HoldingInput`; portfolio account types), so stage only mine: `git apply --cached` of
`scratchpad/appscard/mine-shared-hunks.patch`, or `git add -p`.
