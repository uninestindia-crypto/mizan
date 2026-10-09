# Work Record: Factory-New Laptop Seed Instrument Fallback for Immediate Live Quotes

STATUS: COMPLETED
CREATED_UTC: 2026-10-07T13:15:00Z
COMPLETED_UTC: 2026-10-07T13:20:00Z
OWNER: Antigravity
BRANCH: main
STARTING_REVISION: 4ba857633e9d80d24e107bb4ce5fa7310e53a25b
GOAL_LINE: G6, G1

## Objective
Ensure that on a factory-new laptop installation, before full historical market data or the market index database is downloaded/built, adding an Upstox key (or analytics token) immediately enables live quote fetching for all major NSE equities (NIFTY 500) without terminal intervention.

## Scope
- `configs/nse_seed_instruments.json`: Curated offline seed mapping (502 NSE equities and ETFs) mapping ticker symbols to Upstox instrument keys (`NSE_EQ|ISIN`).
- `src/quant_system/server/v2/live_routes.py`: Separated `index_resolver`, `seed_resolver`, and `combined_resolver` so that:
  - `index_resolver` preserves its strict contract with the market index.
  - `seed_resolver` resolves ticker symbols using bundled seed instruments.
  - `combined_resolver` falls back to seed instruments when the local index does not have a symbol or is unbuilt.
  - `_build` uses `combined_resolver`.
- `tests/test_live_routes.py`: Added regression tests verifying `seed_resolver` and `combined_resolver`.

## Non-Goals
- Altering existing index contracts or breaking index unit test mocks.
- Live-money order execution.

## Owned Paths
- `configs/nse_seed_instruments.json`
- `src/quant_system/server/v2/live_routes.py`
- `tests/test_live_routes.py`
- `agent_context/work/completed/20261007-1315Z-antigravity-factory-new-seed-instruments.md`

## Outcomes & Verification
1. `src/quant_system/server/v2/live_routes.py`:
   - `index_resolver`: preserves isolated index contract (returns `None` when index doesn't have symbol, is blank, or not ready).
   - `seed_resolver`: resolves 502 NIFTY 500 symbols & ETFs using bundled `configs/nse_seed_instruments.json`.
   - `combined_resolver`: checks index first, then falls back seamlessly to seed instruments.
   - `_build`: builds `QuoteService` with `combined_resolver`.
2. Pytest suites verified:
   - `tests/test_live_routes.py`: 58/58 passed.
   - `tests/test_credentials_v2.py`: 7/7 passed.
   - `tests/test_live_quotes.py`: 40/40 passed.
   - `tests/test_auto_update.py`: 37/37 passed.
   - Total backend tests run: 182 passed, 0 failed.
3. Frontend vitest suites verified:
   - `LivePrice.test.tsx`, `Stock.live.test.tsx`, `Home.live.test.tsx`: 22/22 passed.
4. Secret detection scan:
   - `.venv/Scripts/detect-secrets scan` passed with 0 candidate credentials detected.
