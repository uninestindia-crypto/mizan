# Slice 07 Evidence — Governed Financial Research & Ledgers

STATUS: PASS  
DATE: 2026-08-22  
CANDIDATE REVISION: HEAD  

## 1. Outcome & Summary

Slice 7 delivers the governed financial research, ledger accounting kernel, options engine, and pre-trade risk governor for QuantOS:
1. **`src/quant_system/analytics/nse_rules.py`**: Effective-dated Indian exchange rule engine with point-in-time statutory rule lookup across Cash Delivery, Cash Intraday, Equity Futures, and Options. Zero timeless constants.
2. **`src/quant_system/core/ledger.py`**: Exact Decimal double-entry accounting kernel with strict binary float rejection, FIFO lot management, position flips, single-path idempotency, and deterministic SHA-256 state reconciliation.
3. **`src/quant_system/analytics/greeks.py`**: Analytical Black-Scholes and lattice Binomial CRR Greeks engine (Delta, Gamma, Theta, Vega, Rho), robust IV solver, and effective-dated NSE contract conventions (lot sizes, strike steps, Act/365 expiry fractions).
4. **`src/quant_system/risk/governor.py`**: Pre-trade risk governor enforcing session peak equity tracking, daily and trailing drawdown circuit breakers, concentration caps, cash buffers, spread limits, naked short checks, fail-closed kill switches, and state restoration.

---

## 2. Contracts Proved

- **Effective-Dated Rule Invariants**:
  - Tested Finance (No. 2) Act 2024 STT hike from 0.0125% to 0.02% on futures and 0.0625% to 0.10% on options on 2024-10-01.
  - Tested SEBI turnover fee reduction from ₹15/crore to ₹10/crore on 2021-06-01.
  - Tested Uniform Stamp Duty Act 2020 (0.015% delivery buy, 0.003% intraday buy, 0.002% futures buy, 0.003% options buy).
  - Tested NSE revised exchange turnover charge structure on 2024-10-01 (0.00297% delivery, 0.00173% futures, 0.03503% options).
  - Tested catalog ambiguity detection: overlapping or invalid date ranges fail closed with `ValueError`.
- **Accounting & Ledger Invariants**:
  - Exact Decimal double-entry accounting down to `Decimal("0.01")` (1 paisa).
  - Binary floats passed into ledger initialization, fills, prices, or fees are rejected with `TypeError`.
  - Single-path idempotency: identical duplicate events return cached transactions without state mutation; conflicting payloads raise `IdempotencyConflictError`.
  - FIFO lot allocation correctly tracks cost basis, computes realized P&L per lot, and handles position flips in a single atomic transaction.
  - Atomic validation-before-mutation: any invalid fill or cash flow is an atomic no-op leaving balances, lots, and journal untouched.
  - SHA-256 state reconciliation hash verifies complete ledger state deterministically.
- **Options & Greeks Invariants**:
  - European Call-Put parity holds to within $10^{-4}$.
  - Binomial CRR lattice converges to analytical Black-Scholes within 0.1%.
  - American Put early exercise rights verified ($P_{\text{American}} \ge P_{\text{European}}$).
  - Hybrid Newton-Raphson + Bisection IV solver recovers true volatility parameters within $10^{-4}$.
  - NSE contract specifications enforce effective-dated lot sizes and strike step multiples.
- **Risk Governor Invariants**:
  - Monotonic peak equity tracking across daily session and all-time periods.
  - Automatic fail-closed kill switch triggered upon daily or trailing drawdown breaches.
  - Spread gate, max position weight, cash buffer, and naked short sale rules verified.
  - Full state serialization and recovery across application restarts.

---

## 3. Test Suite Evidence

Execution command:
```powershell
uv run pytest tests/test_nse_rules.py tests/test_ledger_accounting.py tests/test_greeks_and_options.py tests/test_risk_governor.py
```

Results:
```text
============================= test session starts =============================
platform win32 -- Python 3.13.15, pytest-9.1.1, pluggy-1.6.0
collected 30 items

tests/test_nse_rules.py::test_nse_rule_engine_catalog_validity PASSED    [  3%]
tests/test_nse_rules.py::test_stt_futures_effective_date_transition_2024 PASSED [  6%]
tests/test_nse_rules.py::test_stt_options_effective_date_transition_2024 PASSED [ 10%]
tests/test_nse_rules.py::test_stamp_duty_uniform_rates_and_side_applicability PASSED [ 13%]
tests/test_nse_rules.py::test_sebi_turnover_charges_transition_2021 PASSED [ 16%]
tests/test_nse_rules.py::test_exchange_turnover_uniform_structure_2024 PASSED [ 20%]
tests/test_nse_rules.py::test_gst_component_identity PASSED              [ 23%]
tests/test_nse_rules.py::test_cost_breakdown_deterministic_hash PASSED   [ 26%]
tests/test_nse_rules.py::test_overlapping_catalog_rejection PASSED       [ 30%]
tests/test_ledger_accounting.py::test_ledger_initial_state PASSED        [ 33%]
tests/test_ledger_accounting.py::test_ledger_rejects_binary_float PASSED [ 36%]
tests/test_ledger_accounting.py::test_ledger_buy_sell_fifo_realized_pnl PASSED [ 40%]
tests/test_ledger_accounting.py::test_ledger_position_flip_long_to_short PASSED [ 43%]
tests/test_ledger_accounting.py::test_ledger_idempotency_and_conflict_detection PASSED [ 46%]
tests/test_ledger_accounting.py::test_ledger_atomic_validation_before_mutation PASSED [ 50%]
tests/test_ledger_accounting.py::test_ledger_external_cash_flows PASSED  [ 53%]
tests/test_greeks_and_options.py::test_black_scholes_call_put_parity PASSED [ 56%]
tests/test_greeks_and_options.py::test_black_scholes_at_expiration PASSED [ 60%]
tests/test_greeks_and_options.py::test_binomial_crr_convergence_to_black_scholes PASSED [ 63%]
tests/test_greeks_and_options.py::test_binomial_american_early_exercise_premium PASSED [ 66%]
tests/test_greeks_and_options.py::test_implied_volatility_solver PASSED  [ 70%]
tests/test_greeks_and_options.py::test_nse_contract_conventions_and_lot_sizes PASSED [ 73%]
tests/test_greeks_and_options.py::test_nse_time_to_expiry_act365 PASSED  [ 76%]
tests/test_risk_governor.py::test_risk_governor_approval_flow PASSED     [ 80%]
tests/test_risk_governor.py::test_risk_governor_rejects_oversized_position PASSED [ 83%]
tests/test_risk_governor.py::test_risk_governor_cash_buffer_enforcement PASSED [ 86%]
tests/test_risk_governor.py::test_risk_governor_daily_drawdown_kill_switch PASSED [ 90%]
tests/test_risk_governor.py::test_risk_governor_trailing_max_drawdown_kill_switch PASSED [ 93%]
tests/test_risk_governor.py::test_risk_governor_spread_and_missing_price_checks PASSED [ 96%]
tests/test_risk_governor.py::test_risk_governor_state_persistence_and_recovery PASSED [100%]

============================= 30 passed in 0.33s ==============================
```

---

## 4. Static Analysis & Type Checking

- `uv run ruff check src/quant_system/analytics/nse_rules.py src/quant_system/core/ledger.py src/quant_system/analytics/greeks.py src/quant_system/risk/governor.py src/quant_system/core/domain.py tests/test_nse_rules.py tests/test_ledger_accounting.py tests/test_greeks_and_options.py tests/test_risk_governor.py`: **0 errors (100% clean)**.
- `uv run mypy src/quant_system/analytics/nse_rules.py src/quant_system/core/ledger.py src/quant_system/analytics/greeks.py src/quant_system/risk/governor.py src/quant_system/core/domain.py tests/test_nse_rules.py tests/test_ledger_accounting.py tests/test_greeks_and_options.py tests/test_risk_governor.py`: **Success: no issues found in 9 source files**.
