# ADR-0001: Retail frontend, API v2, market index, lab simulator

STATUS: ACCEPTED for branch `claude/retail-redesign` (2026-09-28)

## Context

The shipped UI is about 7,000 lines of hand-written HTML/CSS/vanilla JS, much of it HTML inside
Python strings. Its `/live` page cannot run under the app's own CSP, `/ui/journeys` renders raw
JSON, and `/api/v1/backtest/run` simulates on `SyntheticDataGenerator` prices. The evidence store
holds the real data (3,322 all-market datasets to 2026-08-21 and a daily 3-year NIFTY 500 refresh
to 2026-09-23) as gzipped JSONL behind manifests, which is too slow to scan per request.

## Decisions

1. **Frontend**: React 19 + TypeScript + Vite, Tailwind CSS 4, React Router, TanStack Query,
   TradingView Lightweight Charts (Apache-2.0, attribution shown), lucide icons, self-hosted
   fonts. Built into `src/quant_system/server/static/app/` (gitignored), so PyInstaller bundles it
   with no spec change. Node is a build-time tool only.
2. **Serving**: FastAPI serves the SPA at `/` with an `index.html` fallback for client routes. The
   old console moves to `/classic`; `/live` and all `/api/v1` routes are unchanged.
3. **API v2** under `/api/v2`, typed Pydantic models. Mutations send `X-CSRF-Token` obtained from
   the existing `/api/v1/csrf-token`.
4. **Market index**: a derived SQLite file built from the evidence store, read-only against it.
   It records every source manifest hash it used. Per symbol it takes the all-market 10-year
   dataset and the newest NIFTY 500 refresh vintage, stitching them only when every overlapping
   session agrees to within 0.1% (both are the same provider, but a later vintage can be
   re-adjusted after a split). If they disagree, the newer vintage alone is used, and the reason
   is stored. Prices are stored as REAL and read back through `Decimal(repr(x))` for accounting.
5. **App state** (settings, watchlist, holdings, lab runs) lives in `app.sqlite` beside the index.
6. **Lab simulator** (`quant_system.lab`): a separate event loop that reuses `DecimalLedger`, the
   domain types and the same semantics as `BacktestEngine` (signals at close, fills at the next
   open, slippage in the fill price). It adds per-date costs from `NSERuleEngine`, configurable
   brokerage, and precomputed indicators so universe rotations stay fast. `backtest/engine.py` is
   claimed by money-path records and is not edited. Instead, a parity test shows that the lab
   simulator reproduces `BacktestEngine` exactly when given the same cost function.
7. **Credentials** go to Windows Credential Manager through `ctypes` (`CredWriteW`/`CredReadW`/
   `CredDeleteW`); no new dependency, and never a file.

## Rejected alternatives

| Alternative | Why not |
|---|---|
| Restyle the existing templates | Cannot reach the quality bar; HTML inside Python strings; CSP-hostile inline scripts |
| Electron / Tauri shell | Adds a second runtime; the existing Edge app-window shell is enough |
| Next.js | Server rendering is unnecessary for a local app; heavier build |
| Parquet / DuckDB for bars | New 50-100 MB dependencies; SQLite is stdlib and fast enough at 4.6M rows |
| Edit `BacktestEngine` to inject costs | Claimed money-path file; the parity test gives the same guarantee without touching it |
| Backtests on `SyntheticDataGenerator` | A retail backtest on synthetic prices is a fabricated financial claim |

## Consequences

- A developer building the installer needs Node 20+; users need nothing.
- The index must be rebuilt when the evidence store changes; the app detects this from the
  manifests' count and newest acquisition time.
- Two backtest loops exist; the parity test is the guard that keeps their semantics identical.
