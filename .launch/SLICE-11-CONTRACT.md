# Slice 11 Contract — Professional Desktop & Capability Journey

STATUS: FROZEN FOR IMPLEMENTATION  
DATE: 2026-08-22  
PRIMARY ACS: AC-1–8, 56–60, 72, 77–78  

---

## 1. Scope & Objective

Slice 11 establishes the institutional desktop web UI and interactive capability journeys for QuantOS. It provides a clean, responsive, accessible frontend serving the 7 core quantitative research and execution lifecycles:

1. **Data Ingestion & Manifest Inspection**: Point-in-time NSE equity data acquisition, SHA-256 manifest inspection, quality checks (zero lookahead, monotonicity, OHLC sanity), and provenance verification.
2. **Feature Matrix & Label Explorer**: Governed 6-feature schema generation, decision-time alignment (15:30 close), next-open net return labels, friction cost deduction, and overlap purge / embargo enforcement.
3. **Governed Ridge Training & Baseline Comparison**: Expanding walk-forward fold fitting, train-side standardization, multiplicity tracking with Deflated Sharpe Ratio (DSR), and comparison against 4 baselines (`BUY_AND_HOLD`, `EQUITY_DUAL_MOMENTUM`, `PREVIOUS_SIGN`, `NO_TRADE`).
4. **Single-use Holdout & Stress Testing Tearsheet**: Single-use holdout gate evaluation with explicit unlock confirmation, tail-risk CVaR analysis, macroeconomic stress scenarios (volatility spike, spread squeeze, gap down), and downloadable model card tearsheet.
5. **Ledger & Backtest P&L Tearsheet**: Decimal double-entry accounting reconciliation (Assets = Liabilities + Equity with 0 float variance), zero lookahead event-driven backtesting, transaction friction breakdown, and tearsheet export.
6. **Real-Time / Replay Shadow Monitor**: Read-only live quote stream and recorded quote replay with hard zero broker write guarantee (`broker_orders_submitted == 0`), latency tracking, and decision attribution.
7. **Paper Pilot Campaign Dashboard**: Quote-driven paper trading simulation with bid/ask depth matching, adverse slippage, partial fills, campaign ledger idempotency tokens, and drawdown circuit breaker.

---

## 2. Interface & Routing Architecture

### UI Views
- `GET /`: Serves the complete single-page interactive dashboard with all 7 journey tabs.
- `GET /ui`: Alias for root dashboard.
- `GET /ui/journeys`: Returns JSON metadata for all 7 registered user journeys.
- `GET /ui/journey/{journey_id}`: Serves a standalone HTML view for a specific journey or an accessible 404 error page if invalid.

### Backing REST APIs
- `GET /api/journeys`: Enumerates all 7 journey descriptors.
- `GET /api/data/manifests`: Returns immutable dataset manifests with SHA-256 digests.
- `POST /api/data/ingest`: Ingests and verifies historical bar data ranges.
- `POST /api/features/explore`: Computes 6-feature schema and decision-time aligned net labels.
- `POST /api/training/governed-ridge`: Fits walk-forward ridge fold and computes baseline comparison & DSR.
- `POST /api/holdout/evaluate`: Evaluates single-use holdout gates and macroeconomic stress tests.
- `GET /api/shadow/status`: Streams shadow quote feed and decision attribution log with 0 broker orders.
- `POST /api/shadow/control`: Controls shadow monitor playback state.
- `GET /api/paper-pilot/campaign`: Returns active campaign equity, positions, and order ladder.
- `POST /api/paper-pilot/order`: Submits quote-driven paper order with unique idempotency token.

---

## 3. Accessibility & Usability Invariants (WCAG AA & WAI-ARIA)

1. **Landmark Structure**: Every page and view contains semantic HTML5 landmarks:
   - `<header class="navbar" role="banner">`
   - `<nav class="nav-tabs" role="tablist" aria-label="...">`
   - `<main class="container" id="main-content" role="main">`
   - `<footer class="footer" role="contentinfo">`
2. **Keyboard Navigation**:
   - Skip to main content link (`<a href="#main-content" class="skip-link">`).
   - WAI-ARIA Tabs pattern: tab buttons support `ArrowLeft`, `ArrowRight`, `Home`, and `End` navigation with dynamic `aria-selected` and `tabindex` management.
   - Visible focus indicator on all interactive controls (`*:focus-visible { outline: 2px solid var(--color-accent); }`).
3. **Form Accessibility**: Every form control `<input>` or `<select>` has an associated `<label for="...">` with matching ID.
4. **Live Regions & Alerts**: Dynamic notifications and error banners use `role="alert"`, `role="status"`, or `aria-live="polite"`.
5. **Truthful Source Disclosures**: Every journey view explicitly displays data provenance badges (`SYNTHETIC`, `GOVERNED_PIT`, `RESEARCH_ONLY`, `READ_ONLY`, `PAPER_SIM`).

---

## 4. Financial & Safety Invariants

- **Zero Live Broker Orders**: Across all UI endpoints and journeys, broker order creation, modification, and cancellation counts are strictly 0 (zero).
- **Decimal Double-Entry Ledger**: Backtest and ledger views enforce exact Decimal accounting with zero floating-point rounding variance.
- **Single-Use Holdout Lock**: Holdout dataset can only be evaluated once per frozen candidate; unconfirmed requests fail closed.
- **Multiplicity Accounting**: Every model fitting attempt increments the global multiplicity counter, preventing selection bias in Deflated Sharpe calculation.
