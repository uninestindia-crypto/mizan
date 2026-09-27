---
name: point-in-time-market-data
description: Ingest, transform, validate, or review market/fundamental/options data for backtests and quantitative models where timestamp availability, revisions, corporate actions, survivorship, stale data, or source provenance can invalidate results.
---

# Point-in-Time Market Data Summary
- Data must represent what strategy could actually know at decision time.
- Zero look-ahead leakage.
- Handle circuit-locked sessions (volume == 0 or high == low).
- Respect calendar and point-in-time pricing.
