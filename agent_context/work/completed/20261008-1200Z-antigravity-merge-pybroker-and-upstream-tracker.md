# Active work: Merge PyBroker into Mizan & Implement Upstream Update Notification with AI Hand-off

STATUS: ACTIVE  
OWNER: Antigravity, on founder instruction 2026-10-08: "learn it and merge this codebase to mizan and make sure whenever new update comes mizan gets notified and its owner hadns it to ai agent to learn an add update"  
TOOL: Antigravity  
STARTED_UTC: 2026-10-08T11:57:00Z  
STARTING_REVISION: `52df4f4514dae6365cbb64f7b60ea44207908b87` (install-root checkout, `main`)  
WORKTREE_OR_BRANCH: `main` (install-root checkout `D:\Quant OS Project\Mizan`)  

GOAL_LINE: G1 (Trustworthy engine) & G4 (Buildable and verifiable in the cloud)

## Objective

1. Learn and enshrine PyBroker's Numba JIT-accelerated core, zero-lookahead guardrails, and AI agent skills into Mizan.
2. Merge the PyBroker core engine (`src/pybroker/`) into Mizan, exposing it as a first-class quantitative research and accelerated backtesting kernel.
3. Build a native Mizan adapter (`src/quant_system/backtest/pybroker_adapter.py`) bridging Mizan's `PriceBar` data, Indian regulatory cost model (`IndianMarketCostModel` STT/GST/SEBI/stamp duty/paisa), and Shariah universe screening to PyBroker's Numba engine.
4. Build the PyBroker Upstream Update Tracker (`src/quant_system/research/pybroker_upstream_tracker.py`) and wire it into Mizan's server endpoints (`/api/v2/updates/pybroker` and system update notifications).
5. Establish the AI Agent Hand-off Protocol: whenever an upstream update is detected, Mizan alerts the owner and generates an automated briefing (`agent_context/handoffs/PYBROKER-UPDATE-BRIEFING.md`) with a pre-formatted prompt for the owner to give to an AI agent (Antigravity/Claude Code/Cursor) to learn and integrate the update.
6. Install PyBroker AI Agent Skills and write comprehensive tests.

## Owned paths

- `agent_context/work/active/20261008-1200Z-antigravity-merge-pybroker-and-upstream-tracker.md` (this record)
- `src/pybroker/**`
- `src/quant_system/backtest/pybroker_adapter.py`
- `src/quant_system/research/pybroker_upstream_tracker.py`
- `src/quant_system/server/v2/updates.py`
- `src/quant_system/server/v2/router.py`
- `scripts/sync_pybroker_update.py`
- `skills/pybroker-*`
- `.agents/skills/pybroker-*`
- `agent_context/skills/pybroker_engine_guide.md`
- `agent_context/handoffs/PYBROKER-UPDATE-BRIEFING.md`
- `tests/test_pybroker_adapter.py`
- `tests/test_pybroker_upstream_tracker.py`
- `pyproject.toml`

## Non-goals

- No change to live paper-books, trading schedules, or existing broker configurations.
- No alteration to existing Shariah compliance definitions (AAOIFI/TASIS standards remain immutable).
- No removal or replacement of existing `DecimalLedger` or `BacktestEngine`; PyBroker acts as an accelerated research engine alongside the existing engine.

## Plan

1. Record claim in active work (this record).
2. Copy PyBroker source code (`src/pybroker`) into Mizan and update `pyproject.toml`.
3. Copy and link PyBroker AI agent skills into Mizan (`skills/` and `.agents/skills/`) and write `agent_context/skills/pybroker_engine_guide.md`.
4. Implement `PyBrokerAdapter` in `src/quant_system/backtest/pybroker_adapter.py`.
5. Implement `PyBrokerUpstreamTracker` in `src/quant_system/research/pybroker_upstream_tracker.py` and sync utility `scripts/sync_pybroker_update.py`.
6. Wire update checking and owner notification into `src/quant_system/server/v2/updates.py` and `router.py`.
7. Write and run unit tests for both adapter and upstream tracker.
8. Verify all tests pass, file completed work record.
