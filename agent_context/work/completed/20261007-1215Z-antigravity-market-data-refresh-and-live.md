# Work Record: Market data refresh to live session and baseline resolution

STATUS: COMPLETED  
CREATED_UTC: 2026-10-07T12:15:00Z  
COMPLETED_UTC: 2026-10-07T12:26:00Z  
OWNER: Antigravity  
BRANCH: main  
STARTING_REVISION: a13d2cc9b1d3880845f4699c7e8f199f956b4877  
GOAL_LINE: G1, G6  

## Objective

1. Diagnose and resolve why market data was 8 days behind (frozen on 2026-09-29).
2. Fix baseline detection so pre-existing/seeded 10-year caches are recognized without forcing full re-downloads.
3. Fetch recent daily bars for NIFTY 500 + benchmark from Upstox up to today (October 7, 2026).
4. Rebuild the local market index in both development and installed app paths, making the session live and clearing the 8-day lag.
5. Verify live quote feed connectivity and accuracy.

## Scope & Owned Paths

- `src/quant_system/market/downloader.py`
- `tests/test_market_downloader.py`
- `agent_context/work/completed/20261007-1215Z-antigravity-market-data-refresh-and-live.md`

## Root Cause Analysis

1. **Curated Seed Marker Missing**: The bundled 10-year baseline cache (`all-market-20160822-20260821`) on disk was missing the `.quantos-download` marker file. As a result, `baseline_exists()` returned `False`.
2. **Incremental & Auto-Updates Blocked**: Because `baseline_exists()` was `False`, the system treated the data folder as having no 10-year baseline. This set `can_update = False` in the UI (prompting a full 7-minute re-download instead of a 2-minute update) and set `has_baseline = False` in `auto_update.py` (which blocked automatic daily updates).
3. **Auto-Updater Rules**: The background updater (`auto_update.py`) was also gated by `running_books > 0`. Without an active paper book, automatic daily updates did not trigger after market close.
4. **8-Day Window**: The last rolling refresh cache (`nifty500-refresh-20230828-20260827`) was acquired on September 29, 2026. Across the intervening dates (including the October 2 Gandhi Jayanti market holiday and the weekend), no fresh daily bars had been pulled into the local cache.

## Solutions Applied

1. **`downloader.py`**:
   - Updated `baseline_exists` and `_download` to recognise any pre-existing or seeded `all-market-*` directory that contains committed datasets in `store/datasets`, writing the marker if absent.
   - Added `test_seeded_baseline_without_marker_is_recognised` in `tests/test_market_downloader.py`.
2. **Data Acquisition**:
   - Marked `data/evidence/market-cache/all-market-20160822-20260821` with `.quantos-download` to preserve the 10-year baseline.
   - Executed `MarketDownload` in `update` mode, fetching 494 stocks from Upstox into `data/evidence/market-cache/nifty500-refresh-20231008-20261007`.
3. **Index Build**:
   - Rebuilt the SQLite market index in `data/quantos2/index` and `D:\QuantOS\data\quantos2\index`.
   - `latest_session` advanced from `2026-09-29` to `2026-10-06`. Total bars indexed increased to 4,478,017 across 3,268 symbols.
   - `market_data_check` returns status `"ok"`.
4. **Live Quotes**:
   - Verified `QuoteService.fetch` connects to Upstox using the credential store and resolves symbols to instrument keys via the new index.
   - Real-time closing prices as of today (`2026-10-07T15:59:xx+05:30`) verified for `RELIANCE`, `TCS`, `INFY`, `HDFCBANK`, `NIFTYBEES`.

## Verification & Test Results

- `tests/test_market_downloader.py`: 27/27 passed.
- `tests/test_auto_update.py`: 34/34 passed.
- `tests/test_credentials_v2.py`: 7/7 passed.
- `tests/test_live_routes.py`: 32/32 passed.
- `tests/test_live_quotes.py`: 41/41 passed.
- `tests/test_live_keys.py`: 27/27 passed.
- Total suite: 232/232 passed in 13.06s.
- `ruff check`: All checks passed.
- `ruff format`: Clean.
- `mypy`: Clean.
