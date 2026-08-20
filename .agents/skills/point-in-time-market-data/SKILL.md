---
name: point-in-time-market-data
description: Ingest, transform, validate, or review market/fundamental/options data for backtests and quantitative models where timestamp availability, revisions, corporate actions, survivorship, stale data, or source provenance can invalidate results. Do not use for generic static datasets without market-time semantics.
---

# Point-in-Time Market Data

The dataset must represent what the strategy could actually know at each decision time. Clean-looking data that was unavailable then is corrupt research input.

## Required dataset contract

For every source and field, define:

- provider and provider identifier;
- instrument identity and mapping history;
- event/exchange timestamp, provider timestamp, and ingestion timestamp;
- timezone and trading-calendar version;
- publication/revision availability when the value is not exchange-native;
- raw versus adjusted value and adjustment methodology;
- units, currency, price scale, and null/stale semantics;
- requested and received range, pagination/completeness, and provider response provenance;
- synthetic, cached, delayed, or live status.

## Invariants

- Never silently mix synthetic and provider data in one run. Mixed datasets require explicit per-row provenance and user-visible labeling.
- Preserve raw observations; derive corrected/adjusted datasets reproducibly with a versioned transformation manifest.
- Universe membership is point-in-time. Include delisted, renamed, suspended, and failed instruments where the historical rule requires them.
- Apply splits, dividends, symbol changes, expiries, and contract rolls consistently across prices, volumes, positions, and labels.
- Reject duplicate/conflicting keys unless an explicit deterministic resolution rule records the discarded source.
- A missing response, truncated range, partial symbol set, stale quote, or provider fallback is a first-class outcome, never success.
- Validate OHLC relationships, monotonic timestamps, session membership, duplicates, gaps, non-positive prices, volume/open-interest bounds, and cross-field units before use.
- Store a manifest hash over canonical raw data and transformation configuration so a backtest can be reproduced.

## Failure behavior

Provider timeout, 429, 5xx, malformed body, HTML body, expired credentials, empty result, partial range, and schema drift must map to typed outcomes. Retries require bounded exponential backoff with jitter and respect `Retry-After`; never retry authentication or validation failures blindly.

When data is incomplete, the caller must choose explicitly among: abort, restrict the universe with disclosure, use a previously validated cache with age shown, or run a separately labeled synthetic scenario. The connector may not choose silently.

## Evidence required before model/backtest use

- dataset manifest and source/effective-date metadata;
- completeness report per instrument/session;
- anomaly and repair report;
- corporate-action/universe policy;
- raw-to-derived reproducibility check;
- point-in-time leakage tests;
- representative failure-injection tests for the provider boundary.

For NSE-specific session, contract, lot-size, or regulatory rules, also load `nse-execution-craft` and verify current values against official primary sources.
