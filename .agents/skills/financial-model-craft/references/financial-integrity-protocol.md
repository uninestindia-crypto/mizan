# Financial Integrity Protocol

Use this protocol when a task changes a financial calculation, ledger transition, research report,
stress test, or promotion decision. Apply only the sections relevant to the task, but do not omit a
section that can change the economic result.

## 1. Freeze the contract

Record these fields before coding:

| Field | Required meaning |
|---|---|
| Purpose and verdict ceiling | Research, backtest, shadow, bounded paper pilot, or paper; never inferred live authority |
| Instrument identity | Venue, segment, symbol/security ID, currency, multiplier, lot/tick rules, contract status |
| Time contract | Decision, information cutoff, order, eligible fill, mark, settlement, and realization timestamps |
| Quantity and price units | Shares/contracts/lots, quote scale, multiplier, currency, and canonical decimal representation |
| Capital convention | Initial cash, external flows, leverage/margin, cash buffer, sizing basis, and short-sale policy |
| Cost authority | Component, source, publication and effective dates, side/segment basis, rate/cap/minimum, rounding |
| Accounting policy | Inventory method, fee allocation, realized/unrealized treatment, corporate actions, settlement |
| Metric policy | Formula, sampling frequency, benchmark/risk-free source, annualization, missing/flat behavior |
| Stress policy | Default and adverse costs, delay, gap, spread, liquidity, stale/missing data, event ordering |
| Evidence identity | Input, rules, code, environment, configuration, event stream, result, and reconciliation hashes |

Unknown fields become typed failures or explicit research-only limitations. They are not defaulted
to the most favorable common convention.

## 2. Exact numeric boundary

- Parse external decimal text directly to `Decimal`; reject exponent notation, `NaN`, infinity,
  booleans masquerading as integers, and noncanonical strings when the persisted contract requires
  canonical form.
- Never use `Decimal(float_value)` or an intermediate expression such as
  `Decimal(str(float_bps / 10000))`. Parse a decimal rate once, then divide by a Decimal basis.
- Represent persisted money as integer paise plus currency when indivisible paisa is required, or
  as canonical decimal text when a rule needs sub-paisa intermediate precision.
- State rounding mode and stage. Legal component rounding happens at the component's specified
  boundary; display rounding happens only after the reconciled economic value exists.
- Check intermediate precision and maximum magnitude. Fail typed on overflow or unsupported scale
  instead of clipping.
- Money, accounting identities, legal rounding, rule selection, and exact gates remain Decimal or
  integer arithmetic. A vetted statistical library may use floating point only when the contract
  records architecture, algorithm/library version, tolerances, and replay evidence; its outputs do
  not become exact money by converting them back to Decimal.

Minimum numeric tests:

- zero, one paisa, negative values where invalid, maximum supported amount, and maximum quantity;
- values immediately below, exactly at, and immediately above each rate, cap, minimum, tick, lot,
  tax, and promotion threshold;
- algebraically equivalent input representations and canonical persistence;
- a value such as `0.1` that exposes binary-float contamination.

## 3. Effective-dated cost model

Store each component as a versioned rule with at least:

```text
rule_id, component, source_ref, publication_date,
effective_from, effective_to, venue, segment, product,
side_basis, rate, rate_unit, base_formula, cap, minimum,
rounding_unit, rounding_mode, rule_hash
```

Select by the event/trade date and instrument segment. Reject missing, overlapping, or ambiguous
versions. Record separately, where applicable: brokerage, STT, exchange charges, SEBI charges,
stamp duty, GST, spread, slippage, impact, borrow, funding, exercise/assignment, and other configured
friction. Preserve both component values and rule IDs in fills, labels, ledgers, reports, and
evidence bundles.

Boundary evidence needs a primary-source-derived expected result before, at, and after each
effective-date or rounding transition. Current web values may inform a new rule version but cannot
rewrite historical evidence.

Classify the implementation boundary explicitly:

- a **trusted cost-quote consumer** verifies the quote identity, instrument, event time, component
  map, rule IDs, total, and content hash, but makes no claim that its rates are currently lawful;
- an **authority-producing cost calculator** selects complete effective-dated primary-source rules,
  applies their legal bases and rounding, and proves before/at/after transition fixtures.

Do not promote a consumer to an authority-producing claim merely because its arithmetic is exact.

## 4. Event and ledger identities

Derive all financial state from one ordered event stream. At minimum retain:

- proposal/order identity and risk decision;
- fill identity, linked order, quote/bar provenance, quantity, price, side, and fill sequence;
- each component cost and applied rule ID;
- cash and position postings, inventory-lot changes, realized P&L, and reconciliation hash;
- mark source/time for unrealized P&L and equity;
- cancellation, rejection, correction, corporate action, and settlement events.

Useful reconciliation identities include:

```text
final cash = initial cash + external cash flows
             + sale proceeds - purchase consideration - cash charges

position quantity = opening quantity + accepted buys - accepted sells

equity = cash + sum(marked position values) + separately recognized receivables/payables
```

Realized P&L must follow the frozen inventory and fee-allocation policy; do not assume one universal
formula for partial closes, flips, shorts, options, corporate actions, or settlement. Prove every
supported transition with hand-derived journal fixtures.

Idempotency is a financial invariant. Reprocessing the same event returns the prior result without
new postings. A duplicate identity with different content is a conflict. Out-of-order events either
follow a deterministic, evidenced reorder policy or fail closed before mutation.

Validate before mutate: rejection or processing failure must be an atomic no-op across balances,
positions, lots, P&L, fees, evidence, and replay keys. Reconciliation must independently rebuild
cash, positions, inventory lots, component fees, realized/unrealized P&L, and equity from the
authoritative event stream. Re-summing the ledger's own cash-delta column is a consistency check,
not independent reconciliation.

## 5. Return and risk metrics

Keep these concepts separate:

- gross return before friction;
- each modeled friction component;
- net return after friction;
- cash P&L in currency;
- return on the frozen capital or exposure denominator;
- realized and unrealized P&L;
- time-weighted versus money-weighted performance.

For annualized return, volatility, Sharpe, or Sortino, persist the sampling frequency, session
calendar, sample count, annualization factor, benchmark or risk-free source, and treatment of flat
or missing periods. Report drawdown magnitude and duration, turnover, exposure, concentration,
attributable count, hit rate, profit factor, and capacity assumptions alongside performance.

Do not use a magic sentinel such as an extreme profit factor for a zero-loss sample without an
explicit schema meaning. Prefer a typed undefined/infinite representation that cannot be confused
with a measured finite value.

Candidate and baseline comparisons must use identical rows, timing, capital, cost, risk, and
attribution rules. Apply multiple-testing correction when model or strategy selection is involved.

## 6. Risk governor integrity

For every declared limit, prove one accept case and below/at/above rejection boundaries. Persist and
bind the immutable limit-set ID to each decision. At minimum inspect leverage, concentration,
position size, cash buffer, fee/slippage reserve, spread/liquidity, naked short, daily drawdown,
session peak, and kill-switch behavior when those limits are declared.

Approval at decision time is not fill authority: re-check price-sensitive and exposure-sensitive
limits against the executable fill. Define session reset semantics, persist peak/kill state across
restart, reject stale quotes and symbol mismatches, and prove a rejected order/fill changes no
financial state.

## 7. Mandatory adverse cases

Choose task-relevant cases from every applicable family:

- timing: same-bar temptation, one-bar delay, overnight gap, session boundary, holiday;
- prices: zero/negative/non-finite, tick boundary, locked/crossed/wide/stale quote;
- quantities: zero/negative, lot mismatch, partial fill, overfill, position flip;
- costs: default and twice-default, cap/minimum/rounding boundary, rule change date;
- events: duplicate, conflicting duplicate, out of order, replay after restart, crash between
  publication phases;
- capital/risk: insufficient cash, leverage, cash buffer, concentration, drawdown, kill switch,
  liquidity, naked short;
- data/evidence: missing authority, corrupt hash, partial history, stale mark, unknown instrument;
- markets: suspension, corporate action, expiry, settlement, illiquidity, adverse 20% gap.

For promotion evidence, QuantOS additionally requires attributable matured outcomes, exact paisa
reconciliation, default/twice-default costs, delay sensitivity, frozen numeric gates, immutable
holdout use, and evidence-derived verdicts.

## 8. Test and review evidence

Use layered proof:

1. hand-derived unit fixtures for formulas and journals;
2. property tests for conservation, monotonic costs, idempotency, and canonicalization;
3. component integration from decision through report/export;
4. deterministic replay in two independent roots;
5. concurrency, corruption, restart, and failure injection;
6. a complete user journey with visible provenance, mode, components, reconciliation, and limits;
7. clean-state verification.

Inspect every user-visible claim surface, including diagnostics, logs, tearsheets, reports, exports,
API schemas, and UI copy. A truthful core calculation is insufficient if a surrounding surface
claims reconciliation, probability, institutional quality, promotion, or capital readiness that
the evidence does not prove.

Mutation-test a rule capable of flattering results: remove a fee, change a side basis, use a
same-bar fill, weaken a risk comparison, skip a duplicate guard, replace Decimal with float, or
turn reconciliation into a tolerance. Capture the real red failure, restore the implementation,
and rerun green.

## 9. Review outcome

Classify findings by potential financial impact:

- **Blocker:** can authorize money movement or promotion without valid authority, or loses the
  ability to reconcile material financial state.
- **Major:** can materially overstate performance, understate costs/risk, double-post, use future
  information, or produce unreproducible financial evidence.
- **Minor:** does not change the governed result but weakens clarity, operability, or auditability.

Severity describes the defect's economic blast radius even when today's product verdict is already
`RESEARCH_ONLY`. The current verdict ceiling limits what may be claimed; it does not downgrade a
defect that would corrupt accounting, risk, or a later promotion path.

Passing unit tests is insufficient when their expected values merely repeat the implementation.
Require an independent derivation, primary-source rule evidence where applicable, and end-to-end
reconciliation before approving a financial claim.
