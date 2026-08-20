---
name: nse-execution-craft
description: Design, implement, test, or review Indian NSE equity, futures, and options execution simulations, paper brokers, transaction-cost models, calendars, contract metadata, or broker reconciliation. Use when fees, taxes, lot sizes, expiry, fills, margin, or exchange rules affect trading results; verify changeable rules from official sources.
---

# NSE Execution Craft

Model the executable trade, not the chart. Exchange rules, taxes, contract metadata, and broker behavior are effective-dated inputs rather than timeless constants.

## Source and configuration law

- Verify changeable rates, calendars, contract specifications, margin rules, expiry conventions, and lot sizes against current official NSE, SEBI, clearing-corporation, tax-authority, or broker primary documentation.
- Record source URL/document, publication date, effective-from/effective-to dates, market segment, and rounding rule with each configuration version.
- Never silently apply today’s fee, tax, lot-size, or expiry rules to historical trades. Select rules by trade date.
- Keep broker-specific charges separate from statutory/exchange charges and expose every component in the result.

## Execution contract

Define per venue/instrument:

- decision, submission, acknowledgement, and fill timestamps;
- tradable session and holiday calendar;
- order type and time-in-force support;
- bid/ask or bar-based fill rule and delay;
- tick-size and quantity/lot validation;
- partial fill, rejection, cancellation, duplicate submission, and retry semantics;
- spread, slippage, impact, and liquidity/capacity assumptions;
- cash/margin reservation, settlement timing, assignment/exercise behavior, and reconciliation.

Bar backtests must never fill at a price unavailable after the decision timestamp. If only OHLCV exists, document the conservative ambiguity rule and test gap, limit, stop, and illiquid-bar cases.

## Financial correctness

- Use exact decimal/fixed-point arithmetic for cash, fees, taxes, premium, settlement, and ledger postings.
- Centralize explicit rounding per component; test values immediately below, at, and above each rounding boundary.
- Reconcile order → fills → fees/taxes → cash → positions → realized/unrealized P&L. Duplicated/replayed fills must not double-post.
- Reject invalid signs, zero/negative quantities, mixed units/currencies, unknown instruments, stale quotes, forbidden naked shorts, and insufficient cash/margin with typed reasons.
- Options require contract identity, underlying, call/put, strike scale, expiry, multiplier/lot size, exercise style, settlement convention, and current contract status.

## Minimum adversarial evidence

Test market gaps, locked/crossed/wide/stale quotes, zero liquidity, partial fills, rejected and duplicated orders, out-of-order events, network loss after broker acceptance, trading halts, expiry/rollover, contract changes, corporate actions, fee/tax effective-date boundaries, and reconciliation after restart/replay.

## Promotion boundary

Passing a simulated or paper execution review does not authorize live orders. Live routing requires separate broker sandbox evidence, credential and authorization design, immutable audit logs, idempotency/reconciliation, tested kill switches, operational monitoring, and explicit high-risk approval.
