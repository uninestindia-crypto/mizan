# Active work: Replace retired Gemini CLI with Antigravity CLI, add CLI live updating & model capabilities

STATUS: ACTIVE  
OWNER: Antigravity  
TOOL: Antigravity  
STARTED_UTC: 2026-10-10T01:30:00Z  
STARTING_REVISION: c751b268c9c0b2f5da642c2be950d890bf67f374  
WORKTREE_OR_BRANCH: branch feature/antigravity-cli-modernization in worktree feature-antigravity-cli-c751b26-20261009-201709

## Objective

GOAL_LINE: G2 (One unified application, two modes), G3 (Factory-new laptop), G7 (Releases reach the founder)

1. Remove Gemini CLI (`gemini`) across backend and frontend since it has been retired and replaced by Antigravity CLI (`agy` / `antigravity`).
2. Wire Antigravity CLI into Copilot CLI chat runner (`cli_chat.py`), bridge definitions (`cli_bridge.py`), tool detector (`aitools.py`), application state (`state.py`), and frontend components.
3. Allow users to update CLIs from within the software manually and automatically.
4. Allow users to fetch and view all live models and features of the CLI directly from the desktop software.
5. Update all tests and verify test suite passes.

## Owned paths

- `agent_context/work/active/20261010-0130Z-antigravity-cli-modernization.md`
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
- `tests/test_cli_chat.py`
- `tests/test_copilot_cli_chat.py`
- `tests/test_copilot_ai_choice.py`
- `tests/test_copilot_ai_wiring.py`
- `tests/test_first_run_usability.py`
- `tests/test_v2_api.py`

## Non-goals

- Removing direct Google Gemini REST API client (`GeminiClient`, `GEMINI_API_KEY`) used for standalone API keys.
- Changing live money routing.

## Plan

1. Create active work record with exact path claims.
2. Update `src/quant_system/copilot/cli_chat.py`: replace gemini CLI with antigravity CLI, wire `_ANTIGRAVITY_INSTRUCTION` and prompt dispatch.
3. Update `src/quant_system/server/v2/cli_bridge.py`:
   - Remove `gemini` from `SUPPORTED_AGENTS`.
   - Add CLI update support (`update` steps, `action="update"` in `start_agent_job`).
   - Add CLI auto-update logic and update availability checks.
   - Add `fetch_cli_capabilities(agent_id, force_refresh)` to query live models and features of the CLI.
4. Update `src/quant_system/server/v2/router.py`:
   - Support `action="update"` in `/cli/launch`.
   - Add endpoint `GET /cli/{agent_id}/capabilities` to fetch live models & features.
   - Add endpoint `POST /cli/auto-update` to configure auto-update.
5. Update `src/quant_system/server/v2/aitools.py` and `state.py`: replace `gemini` with `antigravity`.
6. Update frontend (`aiSource.ts`, `types.ts`, `copilotHistory.ts`, `appWords.ts`, `AppCard.tsx`, `Settings.tsx`):
   - Replace `gemini` CLI with `antigravity`.
   - Add "Update" button, "Auto-update" toggle, and "Live Models & Features" inspection view.
7. Update backend and frontend tests.
8. Run full test suite and verify everything passes cleanly.

## Current step

Step 1 completed. Proceeding to Step 2: updating `cli_chat.py`.

## Decision rationale

Gemini CLI has been officially retired and replaced by Antigravity CLI (`agy`). The desktop software must provide seamless one-click CLI lifecycle management: installation, authentication, automated/manual updates, and real-time inspection of active DeepMind models and agentic features without requiring terminal navigation.
