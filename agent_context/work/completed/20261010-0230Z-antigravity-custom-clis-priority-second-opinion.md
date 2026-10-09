# Completed work: Custom company CLIs, automatic updates, CLI priority order, and infinite-model sequential second opinion pipeline

STATUS: COMPLETED  
OWNER: Antigravity  
TOOL: Antigravity  
STARTED_UTC: 2026-10-10T01:55:00Z  
COMPLETED_UTC: 2026-10-10T02:30:00Z  
STARTING_REVISION: 7dd0bba399c535a235d3ec9f830f55d38b0e957d  
ENDING_REVISION: 27201891f3b2075253e921d26f2178eef87f2ff0  
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
- `frontend/src/components/aiapps/AddCustomCliModal.tsx`
- `frontend/src/components/aiapps/appWords.ts`
- `frontend/src/components/settings/AiSourcePrefer.tsx`
- `frontend/src/components/copilot/SecondOpinionSetup.tsx`
- `frontend/src/components/copilot/ModelReadingCard.tsx`
- `frontend/src/components/copilot/resultModel.ts`
- `frontend/src/components/copilot/useStartRun.ts`
- `tests/test_cli_bridge.py`
- `tests/test_copilot_ai_choice.py`
- `tests/test_copilot_routes.py`
- `tests/test_copilot_verify.py`
- `tests/test_copilot_cli_chat.py`

## Plan & Delivery Summary

1. **Custom Company CLIs Persistence & Management**:
   - Extended `src/quant_system/server/v2/state.py` with `custom_clis` table and CRUD methods (`add_custom_cli`, `delete_custom_cli`, `list_custom_clis`, `set_custom_cli_auto_update`).
   - Integrated with `cli_bridge.py` to seamlessly register, discover, inspect, and execute custom company CLIs alongside standard assistants with drive isolation and background execution.
   - Built `AddCustomCliModal.tsx` and custom app controls in `AppCard.tsx` / `AgentCliBridge.tsx` adhering to No-Terminal Law (clean consumer UI with plain labels, zero terminal jargon).
2. **Automatic Updates**:
   - Added `auto_update` toggle to custom CLIs schema, state, and API endpoints (`POST /api/v2/cli/auto-update`).
   - Added automatic update execution logic via `auto_update_all_clis()` in `cli_bridge.py`.
   - Wired per-app auto-update switches directly into `AppCard.tsx`.
3. **CLI Answering Priority Ordering**:
   - Added `cli_priority: list[str]` to `Settings` in `state.py` and persisted in SQLite.
   - Updated `ai_choice.py` and `copilot_ai.py` to prioritize models according to user preference, falling back down the chain when a CLI is unavailable or fails.
   - Built interactive priority ordering UI (`CliPriorityOrder`) in `AiSourcePrefer.tsx` with up/down controls and plain fallback explanations.
4. **Infinite-Model Sequential Second Opinion Pipeline**:
   - Removed the 6-model hard ceiling in `verify.py` and `copilot_routes.py` (`VerifyRequest`).
   - Implemented `_run_chained_pipeline` in `verify.py` and `build_chained_question` in `verify_opinion.py`: Model 1 evaluates stock facts; Model 2 reviews Model 1's verdict, reasoning, and risks; Model 3 reviews all prior opinions, continuing through an unbounded chain.
   - Added sequential review toggle and model reordering controls in `SecondOpinionSetup.tsx`.
   - Added stage badges (`Stage 1 · Initial Reading`, `Stage 2 · Recheck`, etc.) in `ModelReadingCard.tsx`.

## Commands and Evidence

- Backend Python test suite:
  `pytest tests/test_cli_bridge.py tests/test_copilot_routes.py tests/test_copilot_cli_chat.py tests/test_copilot_verify.py tests/test_copilot_ai_choice.py`
  Result: 140 passed, 0 failed, 1 warning (12.28s).
- Frontend production bundle build:
  `npm run build` (`tsc --noEmit -p . && vite build`)
  Result: Exit code 0, 2244 modules transformed, bundle generated cleanly in 847ms.
- Frontend test suite:
  `npm test -- --run`
  Result: 100 passed test files (100%), 1497 passed tests (100%), 0 failed (56.72s).
- No-Terminal Law compliance test:
  `npx vitest run src/lib/noTerminalRule.test.ts`
  Result: 1 passed test file, 3 passed tests (100%).
- Disk layout audit:
  `powershell -ExecutionPolicy Bypass -File scripts/audit-disk-layout.ps1`
  Result: PASS - no stray QuantOS directories.

## Next safe action

Work complete. The feature branch `feature/antigravity-cli-modernization` is clean and fully verified.
