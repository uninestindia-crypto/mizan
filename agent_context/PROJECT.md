# QuantOS project context

## Product intent

QuantOS is a local-first Python quantitative research, backtesting, risk, analytics, evidence, and
paper/shadow trading platform focused on trustworthy NSE-oriented research. The professionalization
program is turning an existing functional system into a reproducible, point-in-time, cost-aware,
governed research product.

The release target includes research, governed model training, deterministic backtesting,
read-only market data, and shadow/paper workflows. It does not include live-money broker order
routing.

## Non-negotiable invariants

- Decisions use only information available at their declared decision timestamp.
- Signals formed at a close execute no earlier than the next valid bar/open contract.
- Results include fees, spread, slippage, liquidity, and NSE-specific cost assumptions.
- Cash, fees, fills, and ledger values use exact Decimal accounting and reconcile.
- Every proposed order passes the risk governor.
- Datasets, derived rows, trials, models, and evaluations are reproducible and evidence-linked.
- Discovery, tuning, validation, final holdout, shadow, and paper roles remain separate.
- Live capital is never authorized by a backtest or generic paper-broker test.
- Dependency/provider failures are typed and fail closed; no hidden synthetic success fallback.

## Major components

- `src/quant_system/data`: Upstox and synthetic data, point-in-time acquisition, market-data evidence.
- `src/quant_system/evidence`: canonical content-addressed storage and crash recovery.
- `src/quant_system/modeling`: Slice 3 modeling work in progress at the current snapshot.
- `src/quant_system/strategies`: momentum, ridge ML, AI-enhanced, and options strategies.
- `src/quant_system/backtest`: event-driven next-bar execution and cost modeling.
- `src/quant_system/risk`: pre-trade risk governor and checks.
- `src/quant_system/core`: immutable domain records and Decimal ledger.
- `src/quant_system/analytics`: metrics, multiplicity, Monte Carlo, and parameter optimization.
- `src/quant_system/execution`: paper broker and order-state behavior.
- `src/quant_system/server`: local FastAPI service and browser dashboard.

## Canonical project documents

- `.launch/CHARTER.md`: mission, scope, and release boundary.
- `.launch/PRD.md`: acceptance criteria and failure states.
- `.launch/ARCHITECTURE.md`: accepted professional architecture.
- `.launch/ADR-*.md`: durable architectural decisions.
- `.launch/SLICES.md`: risk-ordered implementation plan.
- `.launch/STATE.md`: latest formal program state.
- `.launch/SLICE-*-EVIDENCE.md`: verified slice outcomes.
- `docs/code-profile.md`: code and testing conventions.

General README and older architecture prose may contain stale capability claims. Verify them against
code, tests, and `.launch/` before relying on them.

