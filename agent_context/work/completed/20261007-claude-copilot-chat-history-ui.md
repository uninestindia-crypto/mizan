# Completed work: Copilot chat history UI

STATUS: COMPLETED  
OWNER: Claude Code (worker for the coordinator session)  
TOOL: Claude Code  
STARTED_UTC: 2026-10-07T15:00:00Z  
STARTING_REVISION: e9fea0bca (HEAD when this record was first written; the work began on top of 07b6c6c8c)  
WORKTREE_OR_BRANCH: shared checkout `/home/user/mizan`, branch `wip/halal-transparency`. No worktree. The coordinator commits; this work never staged or committed anything.

GOAL_LINE: G6 (real benefit to retail users: a person can move from one Copilot chat to another). Founder's words:
"why in copilot there is no chat history how will one move from this chat to that".

## Objective

Frontend only. Give the Copilot drawer a saved-chat history: a History button and a New chat button in the header, a
panel listing saved chats (search, rename, delete with confirmation, clear all), reopening a chat so the next message
continues it, remembering the open chat across a restart, an "Answered by <AI>" line under each AI answer, a quiet
note when an answer could not be saved, and the renamed "Choose an AI" button routing to `/settings/ai`. The backend
(`src/quant_system/server/v2/copilot_routes.py`, `src/quant_system/copilot/conversations.py`) was finished and is not edited.

## Owned paths

- `frontend/src/components/copilot/{CopilotDrawer,DrawerHeader,ChatThread,ChatMessageView,Composer,chatState,useChatSession,CopilotProvider,useDrawer,fixtures,chatTestKit,testHarness}.*`
- `frontend/src/components/copilot/Copilot.test.tsx`, `chatState.test.ts`, `resultModel.*`
- NEW: `frontend/src/components/copilot/history/**`
- NEW: `frontend/src/lib/copilotHistory.ts`, `frontend/src/lib/copilotHistory.test.ts`
- This record.

Not touched, by design: `frontend/src/lib/copilot.ts` (the extra request and reply fields are read and sent through
`lib/copilotHistory.ts` instead), `Layout.tsx`, `pages/**`, `components/mode/**`, `components/proof/**`, Settings and
second-opinion files.

## Non-goals

- No backend change. No git add, commit or format run. No new trial, model or data work.

## Plan

1. Read the code and the backend contract. DONE.
2. `lib/copilotHistory.ts`: shapes, calls, "answered by" map, dates, remembered chat. DONE.
3. `chatState.ts` (chat id, opened chat, saved note, Choose an AI), `history/chatStore.ts`, `useChatSession.ts`,
   `history/useOpenChat.ts`, `history/useRememberedChat.ts`, `history/useHistoryView.ts`, provider. DONE.
4. UI: header buttons, `HistoryPanel`, `HistoryList`, `ChatRow`, `RenameForm`, `Confirm`, `ClearAll`, drawer swap,
   `ChatThread` loading line, `ChatMessageView` lines. DONE.
5. Update existing tests for the new label, path, request body and "Answered by". DONE.
6. New tests under `history/` and `lib/`. DONE.
7. Craft checks on my files. DONE.
8. Real-browser check with screenshots and axe. DONE.
9. Report to the coordinator. DONE.

## Decision rationale

- `lib/copilot.ts` is not in my owned list and another worker may edit it, so the new request field
  (`conversation_id`), the reply fields (`conversation_id`, `saved`, `saved_note`) and the provider names live in
  `lib/copilotHistory.ts`; `askInChat` wraps the existing `buildChatRequest` and `normaliseReply`.
- The reducer already ignores a reply whose request is no longer awaited, so a late answer cannot land in another
  chat. `opened` and `cleared` reset the awaited request. A separate "opening" counter (in `history/chatStore.ts`)
  drops a saved chat that is still loading when the person types, starts a new chat, or opens another one.
- Rename and Delete are icon buttons beside each chat (always visible, keyboard reachable), not a hidden menu.
- The panel replaces the thread and the message box (the draft is kept in the provider). Escape inside the panel steps
  back to the chat first; a rename or delete question takes Escape before that.
- A full chat repeats the same saved note with every answer, so the note is shown once and not repeated under the
  following answers that carry the same sentence.
- A chat that disappears while the person writes in it (404) shows the engine's own sentence, hands the question back
  to the message box, and the next question starts a new chat.
- `chatStore.ts` is in `history/` (not the copilot root) to stay inside the owned paths.
- Rejected: clearing storage inside the shared `renderApp` harness (used by many other test files); the tests clear it
  in their own `beforeEach`.
- Placeholder in the message box shortened from "Ask about a stock or a screen" to "Ask about a stock" because it was
  clipped at 320 px; no test depended on the old wording.

## Commands and outcomes

| Command | Result | Evidence/notes |
|---|---|---|
| `cd frontend && npx vitest run src/components/copilot src/lib/copilot` (before any change) | PASS | 197 tests in 11 files |
| `cd frontend && npx vitest run src/components/copilot src/lib/copilotHistory src/lib/copilot` (final) | PASS | 342 tests in 19 files |
| `cd frontend && npx vitest run` (whole frontend, final) | PASS | 967 tests in 69 files |
| `cd frontend && npx tsc --noEmit -p .` (final) | PASS | no output |
| `node scripts/check-code.mjs frontend/src/components/copilot frontend/src/lib/copilotHistory.ts frontend/src/lib/copilotHistory.test.ts` | PASS | 0 findings, 65 files |
| `node scripts/check-tests.mjs frontend/src/components/copilot frontend/src/lib/copilotHistory.test.ts` | PASS for my files | findings remain only in MarkdownView, SecondOpinion, markdown and verifyPolling tests (not mine) |
| Chromium against the real engine, scripted AI answers (`qa_history/history_qa.mjs flow`) | PASS 24/24 | two chats, search, reopen, continue, rename, refused name, delete, reload reopens last chat, stale id, clear all |
| Same, `visual` (light and dark; 1280, 390 and 320 px wide) | PASS 12/12 | no sideways scrolling, nothing wider than the panel; screenshots read by eye |
| Same, `axe` (WCAG 2 A/AA, 2.1 AA, 2.2 AA, scoped to the drawer) | PASS 20/20 | 0 violations: thread, list, rename, delete question, clear-all question; light and dark; wide and phone |
| `scripts/audit-agent-claims.ps1`, `audit-disk-layout.ps1` | NOT RUN | no PowerShell in this container |
| `detect-secrets` | NOT RUN | left to the coordinator before the commit |

## Files changed

New: `frontend/src/lib/copilotHistory.ts`, `frontend/src/lib/copilotHistory.test.ts`, and under
`frontend/src/components/copilot/history/`: `chatStore.ts`, `savedChat.ts`, `useOpenChat.ts`, `useRememberedChat.ts`,
`useHistoryView.ts`, `useDebouncedValue.ts`, `useChatActions.ts`, `HistoryPanel.tsx`, `HistoryList.tsx`, `ChatRow.tsx`,
`RenameForm.tsx`, `Confirm.tsx`, `ClearAll.tsx`, `historyKit.tsx`, and tests `History.test.tsx`, `HistoryRows.test.tsx`,
`Continue.test.tsx`, `Remember.test.tsx`, `Answers.test.tsx`, `savedChat.test.ts`.

Changed (all in `frontend/src/components/copilot/`): `chatState.ts`, `useChatSession.ts`, `CopilotProvider.tsx`,
`CopilotDrawer.tsx`, `DrawerHeader.tsx`, `ChatThread.tsx`, `ChatMessageView.tsx`, `Composer.tsx`, `testHarness.tsx`
(added `serveApi`), `Copilot.test.tsx`, `chatState.test.ts`, `resultModel.test.ts` (one loop turned into a table).

## Blockers and conflicts

None. The shared checkout has other workers' uncommitted changes (Layout, pages, mode, proof, Settings, ModelPicker,
SecondOpinion files); none of those files are touched here.

## Stop point

Done. All gates above passed on the final code. The private build and test server in the session scratchpad were used
only for the browser check; the shared `static/app` build was not touched. Nothing is staged or committed by me.

## Next safe action

Coordinator: review and commit the files listed above (explicit paths only), run `detect-secrets` and the PowerShell
audits, and rebuild the shared frontend (`npm run build`) so the installed app carries this change.
