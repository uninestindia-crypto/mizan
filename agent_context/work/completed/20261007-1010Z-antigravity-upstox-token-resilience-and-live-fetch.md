# Work Record: Upstox Token Resilience and Live Data Auto-Fetch with Manual Click Fallback

STATUS: COMPLETED  
CREATED_UTC: 2026-10-07T10:10:00Z  
COMPLETED_UTC: 2026-10-07T10:18:00Z  
OWNER: Antigravity  
BRANCH: main  
STARTING_REVISION: bb59a3ac8fe23d2ac7e2e928152a0c6b98701b22  
GOAL_LINE: G6, G1  

## Objective
Make Upstox credential verification and live quote acquisition resilient by evaluating token validity dynamically:
1. If an expired `UPSTOX_ACCESS_TOKEN` is present alongside an active `UPSTOX_ANALYTICS_TOKEN`, automatically pass over the expired access token and verify/connect using the active analytics token instead of throwing a false `HTTP 401: Unauthorized`.
2. Ensure live quotes are fetched automatically from the working token, and provide the user with a manual click-to-fetch / refresh button on live price displays if data fetching pauses, stops, or if an on-demand update is requested.

## Scope
- `src/quant_system/server/v2/credentials.py`: Updated `verify_credential_connection` for provider `upstox` to inspect token expiry (`key_problem`) and fall back to `UPSTOX_ANALYTICS_TOKEN` if `UPSTOX_ACCESS_TOKEN` is expired or invalid.
- `tests/test_credentials_v2.py`: Added test cases for `verify_credential_connection` with expired access token + valid analytics token.
- `frontend/src/components/live/LivePrice.tsx`: Added an interactive manual refresh / click-to-fetch capability with loading state and retry button if live fetch stops or is paused.
- `frontend/src/pages/Home.tsx`: Added manual fetch button and retry wire in Watchlist header.

## Non-Goals
- Modifying order execution or routing (strictly paper/simulated per G1).
- Modifying third-party APIs or external network protocols.

## Owned Paths
- `src/quant_system/server/v2/credentials.py`
- `tests/test_credentials_v2.py`
- `frontend/src/components/live/LivePrice.tsx`
- `frontend/src/pages/Home.tsx`
- `agent_context/work/completed/20261007-1010Z-antigravity-upstox-token-resilience-and-live-fetch.md`

## Outcomes & Verification
1. `src/quant_system/server/v2/credentials.py` updated and tested against real stored tokens:
   Output: `{'valid': True, 'provider': 'Upstox Analytics', 'message': 'Connected! Analytics quote feed is active.'}`
2. Unit tests in `tests/test_credentials_v2.py` pass (7/7 passed).
3. Live quote test suite `tests/test_live_keys.py`, `tests/test_live_routes.py`, `tests/test_live_quotes.py` pass (171/171 passed).
4. Frontend unit tests pass (433/433 passed in 32 files).
5. Frontend production bundle rebuilt cleanly (`npm run build` completed in 779ms).
6. Strict static analysis passed: `ruff check` (clean), `ruff format` (clean), `mypy` (clean).
