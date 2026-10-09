# Active work: Custom company CLIs, automatic updates, CLI priority order, and infinite-model sequential second opinion pipeline

STATUS: ACTIVE  
OWNER: Antigravity  
TOOL: Antigravity  
STARTED_UTC: 2026-10-10T01:55:00Z  
STARTING_REVISION: 7dd0bba399c535a235d3ec9f830f55d38b0e957d  
WORKTREE_OR_BRANCH: branch `feature/antigravity-cli-modernization` in `D:/Quant OS Project/Mizan_workspaces/worktrees/feature-antigravity-cli-c751b26-20261009-201709`

## Objective

GOAL_LINE: G2 (One unified application, two modes), G3 (Factory-new laptop. Non-technical users run everything from the app), G6 (Real benefit to retail users)

1. Allow users to manually add, configure, inspect, and remove new custom/company CLIs directly from the desktop application with zero terminal use.
2. Provide automatic update capabilities for all CLIs (both built-in and custom company CLIs), including scheduled/automatic updating and manual update triggers.
3. Allow users to define a priority order of which CLI will answer when for Copilot and AI Assistant chats, automatically falling back down the priority chain if the higher priority CLI is unavailable, offline, or returns an error.
4. In Second Opinion, allow an unbounded priority order of infinite models (removing the hardcoded 6-model ceiling) in a sequential recheck pipeline: Model 1 provides initial evaluation, Model 2 rechecks and critiques Model 1's opinion and result against the facts, Model 3 rechecks both, and so on through the entire user-defined chain, displaying progressive consensus and critiques.

## Owned paths

- `agent_context/work/active/20261010-0155Z-antigravity-custom-clis-priority-second-opinion.md`
- `src/quant_system/server/v2/state.py`
- `src/quant_system/server/v2/cli_bridge.py`
- `src/quant_system/server/v2/router.py`
- `src/quant_system/server/v2/copilot_routes.py`
- `src/quant_system/server/v2/copilot_ai.py`
- `src/quant_system/copilot/ai_choice.py`
- `src/quant_system/copilot/cli_chat.py`
- `src/quant_system/copilot/verify.py`
- `src/quant_system/copilot/verify_opinion.py`
- `src/quant_system/copilot/verify_summary.py`
- `frontend/src/lib/types.ts`
- `frontend/src/lib/queries.ts`
- `frontend/src/lib/copilot.ts`
- `frontend/src/lib/aiSource.ts`
- `frontend/src/components/AgentCliBridge.tsx`
- `frontend/src/components/aiapps/AppCard.tsx`
- `frontend/src/components/settings/AiSourcePrefer.tsx`
- `frontend/src/components/copilot/SecondOpinionSetup.tsx`
- `frontend/src/components/copilot/ModelPicker.tsx`
- `frontend/src/components/copilot/RunPanels.tsx`
- `frontend/src/components/copilot/ResultView.tsx`
- `frontend/src/components/copilot/ModelReadingCard.tsx`
- `frontend/src/components/copilot/resultModel.ts`
- `tests/test_cli_bridge.py`
- `tests/test_copilot_ai_choice.py`
- `tests/test_copilot_routes.py`
- `tests/test_verify_pipeline.py`

## Non-goals

- Live money order execution.
- External cloud multi-tenancy.

## Plan

1. Backend state: Extend `state.py` to persist custom company CLIs in `custom_clis` table and `cli_priority` in `Settings`.
2. Backend CLI bridge: Extend `cli_bridge.py` with custom CLI registration, inspection, install/update steps, and auto-update management.
3. Backend Copilot AI & AI choice: Update `ai_choice.py` and `copilot_ai.py` to order models according to `cli_priority` with reliable fallback.
4. Backend Second Opinion Chained Pipeline: In `verify.py`, `verify_opinion.py`, and `copilot_routes.py`:
   - Remove 6-model limit (support unbounded/infinite models).
   - Implement chained recheck pipeline where each successive model receives the original facts plus prior models' opinions, verdicts, and critiques.
5. REST API routes: Add `/cli/custom` (GET, POST, DELETE), `/cli/auto-update`, and update `/copilot/verify`.
6. Frontend:
   - In `AgentCliBridge.tsx`: Add "Add Company CLI" button and modal dialog for adding custom CLIs, and auto-update status.
   - In `AiSourcePrefer.tsx`: Add intuitive priority ordering controls (move up/down, 1st/2nd/3rd priority indicators) for CLIs with fallback explanation.
   - In `SecondOpinionSetup.tsx` & `ModelPicker.tsx`: Support unbounded models, priority ordering (move up/down in chain), and "Sequential recheck chain" mode.
   - In `ResultView.tsx` & `ModelReadingCard.tsx`: Display stages in the critique chain (Stage 1 initial, Stage 2 critique of Stage 1, etc.).
7. Tests: Write comprehensive unit and integration tests for custom CLIs, CLI priority fallback, and the infinite-model sequential second opinion pipeline.
8. Verification: Run test suite to verify 100% pass rate.

## Current step

Step 1: Implementing custom CLIs table and `cli_priority` in `state.py`.

## Decision rationale

The user requested four key enterprise features:
1) Manually adding custom company CLIs to the platform.
2) Automatic update controls for CLIs.
3) User-defined priority ordering of which CLI will answer when, falling back to lower-priority CLIs upon errors.
4) Infinite-model priority-ordered Second Opinion pipeline where Model 1 gives an opinion, Model 2 rechecks/critiques Model 1's opinion, Model 3 rechecks both, and so on sequentially.
Implementing these with clean SQLite persistence, modular schemas, and seamless UI controls honors the No-Terminal Law and Factory-New Laptop Standard.
