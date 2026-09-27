---
name: financial-model-craft
description: Design, implement, test, or review QuantOS financial calculations and research economics where transaction costs, P&L, portfolio accounting, risk metrics, stress tests, reconciliation, or promotion evidence can change the result. Use for backtests, paper trading, ledgers, performance reports, and financial-model claims; do not use for market-data ingestion or predictive-model training alone.
---

# Financial Model Craft

A financial result is acceptable only when its timing, units, costs, accounting identities, and
evidence make the same economic claim. A plausible number is not a reconciled model.

## Route the task

- Load `point-in-time-market-data` when source availability, adjustments, corporate actions,
  historical universes, or stale observations affect the result.
- Load `quant-model-governance` when features, labels, trial selection, calibration, holdouts, or
  promotion are involved.
- Load `nse-execution-craft` when NSE calendars, fills, fees, taxes, contract metadata, margin, or
  broker reconciliation are involved. Verify changeable rules from current official sources.
- Read [references/financial-integrity-protocol.md](references/financial-integrity-protocol.md)
  before implementing or approving financial logic, ledger behavior, a backtest report, or a
  promotion gate.

## Non-negotiable invariants

- Define economic timing before formulas: decision, order, fill, valuation, settlement, and
  realization times. Never use a price or rule unavailable at its applicable time.
- Use `Decimal`, integer paise, or validated canonical decimal strings for money, prices, rates,
  quantities with fractional units, and exact gate comparisons. Vetted statistical routines may
  use floating point only under an explicit architecture, tolerance, and replay contract; never
  round-trip a binary float into exact accounting state.
- Bind every changeable fee, tax, calendar, lot, tick, expiry, settlement, benchmark, and risk rule
  to an effective-dated authority. Timeless constants are not governed evidence.
- Calculate and retain each friction component separately. Apply its own legal basis, side,
  segment, rate, cap, minimum, and rounding order before summing the total.
- Preserve one accounting path from order/proposal through fills, component costs, cash, position,
  realized/unrealized P&L, equity, metrics, and export. A display or report may not recalculate a
  second answer.
- Every accepted economic event has a stable idempotency key. Duplicate or replayed events cannot
  post twice; conflicting duplicates and out-of-order events fail closed.
- Validate an event completely before mutation. Every rejected or failed event is an atomic no-op
  across cash, positions, lots, fees, P&L, evidence, and idempotency state.
- Completed ledgers reconcile exactly to the paisa. A tolerance, residual plug, float comparison,
  or silent write-off cannot turn a mismatch into success. Reconciliation independently rebuilds
  cash, positions, lots, fees, P&L, and equity from authoritative events; it does not merely sum
  the postings written by the same code path.
- Separate gross return, modeled friction, net return, cash P&L, and percentage return. State
  numerator, denominator, currency, annualization, and sign convention for every metric.
- Evaluate candidate and baselines under identical timing, universe, fill, cost, capital, and risk
  assumptions. Stress costs, delay, gaps, missing/stale data, spread, liquidity, and event order.
- A financial model never authorizes live capital. QuantOS promotion stops at evidence-derived
  `SHADOW`, `PAPER_PILOT`, or `PAPER`; live-money routing needs separate explicit authorization.

## Working method

1. Freeze the financial contract: purpose, instruments, currency, units, chronology, sources,
   rounding, accounting method, assumptions, metrics, and failure states.
2. Write independent hand-calculated boundary fixtures before implementation. Include immediately
   below, at, and above every rounding or gate boundary.
3. Implement pure calculation kernels behind typed domain inputs. Keep provider, UI, persistence,
   and orchestration concerns outside those kernels.
4. Reconcile every state transition and emit immutable evidence linking inputs, rule versions,
   events, outputs, and reconciliation hashes.
5. Test properties and adversarial paths, then deliberately mutate at least one dangerous rule and
   prove a focused test fails before restoration.
6. Report unsupported assumptions and evidence gaps as blocking or research-only limitations. Do
   not fill them with favorable defaults.
