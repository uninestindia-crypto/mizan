# Active work: the "Which AI should answer your questions?" setting (frontend)

STATUS: COMPLETED  
OWNER: Claude Code (cloud session, frontend sub-agent for the coordinator)  
TOOL: Claude Code  
STARTED_UTC: 2026-10-07T00:00:00Z  
STARTING_REVISION: 07b6c6c8c88e74c95f7c5b79ff70abb08742d56b  
WORKTREE_OR_BRANCH: `/home/user/mizan`, branch `wip/halal-transparency` (shared checkout, disjoint paths, no worktree)

GOAL_LINE: G3 and the No-Terminal Law (an AI is chosen and tested by clicking, in plain words), G6.

## Objective

Founder: "set api key ai primary default for every ai feature, allow user to select from setting, default will be cli
based ai". The backend is committed (`07b6c6c8c`). This record covers the screens only: a card at Settings, then AI
assistants that picks the AI app on this computer or a saved key, a favourite, the backup switch and "Test this AI";
the second-opinion picker listing apps and keys; the Agents card sending people to Settings, then AI assistants.

## Owned paths

- `frontend/src/lib/aiSource.ts`, `frontend/src/lib/aiSource.test.ts` (new)
- `frontend/src/components/settings/AiSource*.tsx` and their tests (new)
- `frontend/src/pages/Settings.tsx`: only the `AiAssistants()` function and the import line
- `frontend/src/components/copilot/{ModelPicker,SecondOpinionSetup,SecondOpinionDialog,SecondOpinionReady,SecondOpinionHost,SecondOpinionButton,PickSecondOpinion}.tsx`
  and `SecondOpinion*.test.tsx`, `PickSecondOpinion.test.tsx`, `verifyState*`, `verifyPolling*`
- `frontend/src/components/agents/{AgentCard,AgentSections,agentFixtures}.*`
- `frontend/src/pages/Agents.test.tsx`: three lines that assert the sentence and link of the AgentCard note I change

## Non-goals

No backend change. No edit of `AgentCliBridge.tsx`, `lib/copilot.ts`, `lib/types.ts` or any file another worker owns. No
git add, commit or repository-wide formatter.

## Plan

1. `lib/aiSource.ts`: types, plan order, summary sentence, chips, test target (pure, unit tested). DONE
2. `components/settings/AiSource*.tsx` and the Settings mount (`AiAssistants()` + import only). DONE
3. Second-opinion picker groups (`ModelPicker`, `SecondOpinionSetup`), Agents card link (`AgentCard`, fixtures). DONE
4. Unit and screen tests, typecheck, craft checks. DONE (see Commands)
5. Real-browser check with screenshots (light/dark, wide/phone) and axe. DONE: 35 of 35 scripted checks passed against the
   real engine with a faked set of AI apps and keys (scratchpad `aisrc/qa.mjs`); screenshots looked at and polished
   ("Saved" moved beside the summary, chips stacked under names on a phone, link-style "Install or sign in below").
6. Final report to the coordinator. DONE

## Current step

Finished.

## Decision rationale

Types live in `lib/aiSource.ts`, not `lib/types.ts`, because `types.ts` is claimed by another record. The choice is read
from `GET /copilot/status` (`ai` block mirrors Settings) so there is one source of truth after a save.

## Commands and outcomes

| Command | Result | Evidence/notes |
|---|---|---|
| `npx vitest run` (whole frontend) | PASS | 69 files, 967 tests; my 4 new files hold 97 of them |
| `npm run typecheck` | PASS | clean |
| `node scripts/check-code.mjs` on my 15 source and test files | PASS | clean |
| `node scripts/check-tests.mjs` on my 4 new test files | PASS | clean (3 `loop-in-test` in the old `SecondOpinion.test.tsx` predate me and are untouched) |
| `pytest tests/test_no_terminal_copy.py` | PASS | 34 passed; the tab label "AI assistants" is unchanged |
| scratch build + real engine + Chromium, `aisrc/qa.mjs` | PASS | 35/35: summary sentences, saves, favourite, backup switch, test ok and not ok, spinner line, chip flip by polling, Set up focus, arrow keys, axe 0 violations at 1280 in light and dark, no sideways scroll at 390 |
| `scripts/audit-agent-claims.ps1`, `scripts/audit-disk-layout.ps1` | NOT RUN | no PowerShell in this container |

## Files changed

- NEW `frontend/src/lib/aiSource.ts`, `frontend/src/lib/aiSource.test.ts`
- NEW `frontend/src/components/settings/AiSource.tsx`, `AiSourceChoice.tsx`, `AiSourcePrefer.tsx`, `AiSourceTest.tsx`,
  `AiSourceQueries.ts`, `AiSource.test.tsx`
- NEW `frontend/src/components/copilot/SecondOpinionGroups.test.tsx`, `frontend/src/components/agents/AgentCard.test.tsx`
- EDIT `frontend/src/pages/Settings.tsx` (import lines and `AiAssistants()` only)
- EDIT `frontend/src/components/copilot/ModelPicker.tsx`, `SecondOpinionSetup.tsx`, `SecondOpinion.test.tsx` (one test)
- EDIT `frontend/src/components/agents/AgentCard.tsx`, `AgentSections.tsx` (comment), `agentFixtures.ts`
- EDIT `frontend/src/pages/Agents.test.tsx` (sentence, link and titles of the tests for the AgentCard note only)
- `frontend/src/lib/types.ts` NOT touched: the types live in `lib/aiSource.ts`.

## Blockers and conflicts

`AgentCliBridge.tsx` still says "Coding agents ... Optional, and nothing in QuantOS needs it" and has an "Open in
terminal" button (recorded as known debt in `lib/noTerminalRule.test.ts`); not mine to change. Left for the coordinator.

## Stop point

Done. Nothing staged or committed. Every file is in a passing state.

## Next safe action

Coordinator: commit the files listed above (stage them by path; `Settings.tsx` also carries another worker's profile-text
lines, which are not mine). Decide the wording of the "Coding agents" card in `AgentCliBridge.tsx` and its "Open in
terminal" buttons, which now sit below a card that says the AI app is the default.
