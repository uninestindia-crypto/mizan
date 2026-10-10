# Completed work: Replace retired Gemini CLI with Antigravity CLI, add CLI live updating & model capabilities

STATUS: COMPLETED  
OWNER: Antigravity  
TOOL: Antigravity  
STARTED_UTC: 2026-10-10T01:30:00Z  
COMPLETED_UTC: 2026-10-10T02:11:00Z  
STARTING_REVISION: c751b268c9c0b2f5da642c2be950d890bf67f374  
ENDING_REVISION: 31def196cf3dc43ff45bc8bb1cb7655aa9179efd  
WORKTREE_OR_BRANCH: branch feature/antigravity-cli-modernization in worktree feature-antigravity-cli-c751b26-20261009-201709

## Objective

GOAL_LINE: G2 (One unified application, two modes), G3 (Factory-new laptop), G7 (Releases reach the founder)

1. Remove Gemini CLI (`gemini`) across backend and frontend since it has been retired and replaced by Antigravity CLI (`agy` / `antigravity`).
2. Wire Antigravity CLI into Copilot CLI chat runner (`cli_chat.py`), bridge definitions (`cli_bridge.py`), tool detector (`aitools.py`), application state (`state.py`), and frontend components.
3. Allow users to update CLIs from within the software manually and automatically.
4. Allow users to fetch and view all live models and features of the CLI directly from the desktop software.
5. Update all tests and verify test suite passes.

## Owned paths

- `src/quant_system/server/v2/cli_bridge.py`
- `src/quant_system/server/v2/router.py`
- `src/quant_system/server/v2/aitools.py`
- `src/quant_system/server/v2/state.py`
- `src/quant_system/copilot/cli_chat.py`
- `frontend/src/lib/aiSource.ts`
- `frontend/src/lib/types.ts`
- `frontend/src/lib/copilotHistory.ts`
- `frontend/src/components/aiapps/appWords.ts`
- `frontend/src/components/aiapps/AppCard.tsx`
- `frontend/src/components/aiapps/appFixtures.tsx`
- `frontend/src/components/agents/agentFixtures.ts`
- `frontend/src/components/AgentCliBridge.test.tsx`
- `frontend/src/components/AgentCliBridge.jobs.test.tsx`
- `frontend/src/components/settings/AiSource.test.tsx`
- `frontend/src/lib/aiSource.test.ts`
- `tests/test_cli_bridge.py`
- `tests/test_copilot_cli_chat.py`
- `tests/test_copilot_ai_choice.py`
- `tests/test_copilot_ai_wiring.py`
- `tests/test_first_run_usability.py`
- `tests/test_v2_api.py`

## Non-goals

- Removing direct Google Gemini REST API client (`GeminiClient`, `GEMINI_API_KEY`) used for standalone API keys.
- Changing live money routing.

## Plan & Outcomes

1. Replaced `gemini` with `antigravity` in `cli_chat.py` (with `_ANTIGRAVITY_INSTRUCTION`), `aitools.py`, `state.py`, and `cli_bridge.py`.
2. Added one-click manual updating (`action="update"`) and automated batch updating (`auto_update_all_clis`).
3. Added `fetch_cli_capabilities` and endpoint `GET /cli/{agent_id}/capabilities` to query live models, tokens, and agentic capabilities from the CLI.
4. Added GUI toggle for automatic updates in `AgentCliBridge.tsx`.
5. Updated `frontend/src/lib/aiSource.ts` and `frontend/src/components/aiapps/AppCard.tsx` with Live Models & Features inspection.
6. All 100 frontend test suites (1,497 tests) and 132 core backend tests passing 100%.

## Evidence

- `npm --prefix frontend test`: 100 test files passed, 1,497 passed (100%).
- `pytest tests/`: 132 tests passed (100%).
- `ruff check src tests`: passed (zero errors).
- `mypy src/quant_system/copilot src/quant_system/server/v2`: passed (zero errors).
