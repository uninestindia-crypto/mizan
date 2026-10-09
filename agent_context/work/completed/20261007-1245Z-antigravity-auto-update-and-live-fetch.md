# Work Record: Auto-Update Market Data and Resilient Live Data Fetching

STATUS: COMPLETED
CREATED_UTC: 2026-10-07T12:45:00Z
COMPLETED_UTC: 2026-10-07T12:58:00Z
OWNER: Antigravity
BRANCH: main
STARTING_REVISION: 9f5d61bef13c8ffac70c79dbd63259b3924f794b
GOAL_LINE: G6, G1

## Objective
1. Make Upstox credential resolution fully resilient across `UpstoxClient` and `with_saved_credentials`: fall back to Windows Credential Store (`CredentialStore().get(...)`) when process environment variables are not populated.
2. Fix Settings Accounts & Keys credential test dispatch for Upstox Analytics Token so that testing the analytics token updates status cleanly under its own field without conflating with the access token field.
3. Diagnose and clarify the separation between real-time intraday quotes (live Upstox feed) and historical daily closing bars (local SQLite/Parquet index).

## Scope
- `src/quant_system/data/upstox.py`: Added `CredentialStore` fallback for `UPSTOX_ANALYTICS_TOKEN` and `UPSTOX_ACCESS_TOKEN` when `os.getenv` returns empty.
- `src/quant_system/server/v2/credentials.py`: Enhanced `with_saved_credentials` to query `CredentialStore` directly when secrets are not present in `os.environ`.
- `frontend/src/pages/Settings.tsx`: Fixed `handleTest` to accept a custom `resultKey` (`upstox_analytics`) so the "Test Connection" button on the Upstox Analytics Token card updates its own loading state and result message independently.

## Non-Goals
- Live order placement or broker execution routing.
- Breaking existing pinned test contracts or changing risk invariants.

## Owned Paths
- `src/quant_system/data/upstox.py`
- `src/quant_system/server/v2/credentials.py`
- `frontend/src/pages/Settings.tsx`
- `agent_context/work/completed/20261007-1245Z-antigravity-auto-update-and-live-fetch.md`

## Outcomes & Verification
1. `src/quant_system/server/v2/credentials.py` tested via `with_saved_credentials`:
   `{'valid': True, 'provider': 'Upstox Analytics', 'message': 'Connected! Analytics quote feed is active.'}`
2. `src/quant_system/data/upstox.py` verified to load stored credentials directly from Windows Credential Store when environment is unpopulated.
3. Python tests pass cleanly: `tests/test_credentials_v2.py`, `tests/test_live_quotes.py`, `tests/test_live_routes.py`, `tests/test_auto_update.py` (179/179 passed).
4. Frontend tests pass cleanly: 438/438 passed across 33 test files.
5. Frontend production build compiled cleanly: `npm run build` succeeded in 744ms.
6. Static checks clean: `ruff check` (passed), `mypy` (success, 0 issues across all touched files).
