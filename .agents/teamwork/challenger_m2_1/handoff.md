# Milestone 2 (R2) Challenger Verification Report: Staggered Tranche Portfolio Ledger

## 1. Observation
- Target module under review: `src/quant_system/research_xs_monthly/tranche_ledger.py`.
- Target requirements evaluated:
  * R2 Staggered Tranche Portfolio Ledger invariants: 4 autonomous sub-ledgers, 25% max capital allocation per tranche, 21-session holding period, 5-session weekly stagger.
  * Capital preservation invariant: aggregate portfolio leverage strictly `<= Decimal("1.0000")` across all market conditions.
  * Cash non-negativity invariant: cash balance strictly `>= Decimal("0.00")` under any combination of prices, fees, and quantities.
  * Zero lookahead leakage: execution strictly at next-session open (T+1), attempting execution on `execution_date < decision_date` fails closed.
  * Circuit-lock protections: candidate entries skipped if `volume == 0` or `high == low`; exits carried over without forced liquidation.
  * Statutory fee accounting: exact 0.224% round-trip (11.2 bps entry + 11.2 bps exit) in Decimal arithmetic.
- Created empirical adversarial test suite in `tests/test_xs_portfolio_alpha/test_tranche_ledger_adversarial.py` containing 22 focused stress tests covering:
  1. `test_adversarial_single_asset_surge_1000_pct`: single-stock +1000% price spike (100.00 -> 1100.00). `nav.total_exposure <= Decimal("1.0000")` confirmed.
  2. `test_adversarial_multi_asset_hyper_surge_10000_pct`: +10,000% hyper-surge across all 4 tranches (50.00 -> 5050.00). Invariant `total_exposure <= 1.0000` confirmed.
  3. `test_adversarial_single_asset_crash_99_9_pct`: single-stock -99.9% crash (1000.00 -> 1.00). `total_exposure <= 1.0000` and `>= 0.0000` confirmed.
  4. `test_adversarial_micro_penny_crash_99_999_pct`: extreme crash to 1 paisa (500.00 -> 0.01). `total_exposure <= 1.0000` and cash non-negative confirmed.
  5. `test_adversarial_total_wipeout_zero_price_crash`: 100% price wipeout (price = 0.00). Handled with zero division errors, `exposure == 0.0000`.
  6. `test_adversarial_asymmetric_cross_tranche_extremes`: Tranche 0 (+1000% surge), Tranche 1 (-99.9% crash), Tranche 2 (circuit locked), Tranche 3 (100% cash). Consolidated portfolio exposure strictly `<= 1.0000`.
  7. `test_adversarial_monte_carlo_price_fuzzing_500_trials`: 500 randomized Monte Carlo market shocks with price multipliers in `[0.001, 21.0]` across 20 symbols. Invariant `0.0000 <= total_exposure <= 1.0000` held on 100% of 500 trials.
  8. `test_adversarial_micro_capital_one_rupee`: ₹1.00 initial capital (₹0.25 per tranche). Cash remained non-negative (`>= Decimal("0.00")`).
  9. `test_adversarial_nano_capital_four_paise`: ₹0.04 initial capital (₹0.01 per tranche). Cash remained non-negative.
  10. `test_adversarial_expensive_stocks_exceeding_capital`: stocks with share price exceeding available capital (e.g. MRF at ₹140,000 vs ₹12,500 cash) yielded 0 shares and left cash intact.
  11. `test_adversarial_half_paisa_fee_rounding_exactness`: boundary pricing where fee rounding hits half-paisa quantize boundaries.
  12. `test_adversarial_exhaustive_fee_deduction_domain`: 10,000 discrete trade sizes from 1 paisa to ₹1,000.00 verified `proceeds - fee >= 0` unconditionally.
  13. `test_adversarial_fifty_cycle_churning_fuzz`: 50 sequential rapid rebalance cycles with random prices and random stock picks. Cash remained non-negative across all cycles.
  14. `test_adversarial_lookahead_execution_precedes_decision_fails_closed`: `execution_date < decision_date` raised `ValueError("cannot precede decision date")` and left state 100% unchanged (atomic no-op).
  15. `test_adversarial_lookahead_extreme_past_date_fails_closed`: execution date 1 year in the past raised `ValueError`.
  16. `test_adversarial_next_open_execution_pricing_fidelity`: fills strictly execute at `open_prices` on `execution_date` (T+1).
  17. `test_adversarial_all_symbols_circuit_locked_on_entry`: 100% volume == 0 resulted in 0 purchases, cash untouched.
  18. `test_adversarial_all_symbols_limit_locked_on_entry`: 100% high == low resulted in 0 purchases, cash untouched.
  19. `test_adversarial_circuit_locked_exit_persists_unliquidated`: upper circuit locked position retained without forced liquidation.
  20. `test_adversarial_rebalance_with_zero_cash_survives`: rebalancing with 0.00 cash completed cleanly without division by zero.
  21. `test_adversarial_duplicate_selected_symbols_safe`: duplicate symbols in selection did not violate cash non-negativity or exposure invariants.
  22. `test_adversarial_empty_selection_clears_positions`: empty selection liquidates all liquid positions to cash.
- Empirical test executions:
  * `uv run pytest tests/test_xs_portfolio_alpha/test_tranche_ledger_adversarial.py -v`: 22 passed in 0.18s.
  * `uv run pytest tests/test_xs_portfolio_alpha/test_tranche_ledger.py -v`: 30 passed in 0.18s.
  * `uv run pytest tests/test_xs_portfolio_alpha/test_e2e_acceptance.py -v`: 105 passed in 1.59s.
  * Combined test suite: 168 passed in 1.80s.
  * `uv run ruff check src/quant_system/research_xs_monthly/ tests/test_xs_portfolio_alpha/`: "All checks passed!".
  * `uv run mypy src/quant_system/research_xs_monthly/tranche_ledger.py tests/test_xs_portfolio_alpha/test_tranche_ledger.py tests/test_xs_portfolio_alpha/test_tranche_ledger_adversarial.py`: "Success: no issues found in 3 source files".
  * `scripts/audit-agent-claims.ps1`: "RESULT: PASS - every workspace has a visible claim and every claim resolves."
  * `scripts/audit-disk-layout.ps1`: "RESULT: PASS - no stray QuantOS directories."

## 2. Logic Chain
1. In `src/quant_system/research_xs_monthly/tranche_ledger.py`, capital exposure is calculated in `mark_to_market` as `total_pos_val / (total_cash + total_pos_val)`.
2. Because share quantities are integers `>= 0`, valid stock prices are `>= 0`, and `cash` is maintained strictly `>= 0`, the denominator `nav = total_cash + total_pos_val` is always `>= total_pos_val`.
3. Consequently, for any price surge (+1000%, +10,000%) or crash (-99.9%, -100%), `total_exposure <= Decimal("1.0000")` is mathematically and empirically guaranteed.
4. In `rebalance_tranche`, cash deduction on buy is guarded by `if cash >= (cost + fee): cash -= (cost + fee)`. Because cash is only decremented when sufficient funds exist, cash can never become negative during acquisition.
5. On liquidation, proceeds are `pos.quantity * p_exit` and statutory exit fee is `(proceeds * 0.00112).quantize(Decimal("0.01"))`. Since `0.00112 < 1.0`, fee is always strictly less than proceeds for all `proceeds >= 0.01` (and fee is 0.00 for `proceeds == 0.00`). Thus net liquidation proceeds `proceeds - fee >= 0`, ensuring cash never decreases on liquidation.
6. The lookahead check `if execution_date < decision_date: raise ValueError(...)` executes prior to any state mutation, ensuring atomic fail-closed behavior with zero side effects.
7. Across 500 Monte Carlo randomized trials and 50 rapid churning cycles, zero invariant violations, zero negative cash states, and zero division-by-zero crashes occurred.

## 3. Caveats
- The ledger currently assumes non-negative stock prices (`p >= Decimal("0.00")`). In Indian NSE equity markets, equity share prices have limited liability and cannot trade below 0.01 INR. If upstream market data ever supplied negative prices on exit, the code would compute negative proceeds; upstream bar loader / PIT ingestion must reject negative prices (verified covered in `bars.py`).
- Slippage and market impact beyond statutory fees (0.224% round trip) are out of scope for Milestone 2 ledger accounting and are handled in downstream execution simulation.

## 4. Conclusion
**VERDICT: APPROVE**

`src/quant_system/research_xs_monthly/tranche_ledger.py` satisfies all R2 requirements and passes all empirical adversarial stress tests:
- Leverage invariant `total_exposure() <= Decimal("1.0000")` strictly holds across extreme surges (+1000%, +10,000%), crashes (-99.9%, -100%), and 500 Monte Carlo price shocks.
- Cash non-negativity is mathematically and empirically guaranteed across micro-capital boundaries, extreme share prices, and 50 multi-cycle churning stress runs.
- Lookahead leakage guard fails closed atomically when `execution_date < decision_date`.
- Circuit-lock entry skips and exit carry-overs function accurately without forced liquidation.
- 100% of 168 tests pass with clean Ruff and strict Mypy.

## 5. Verification Method
To independently verify this empirical evaluation:
```powershell
# 1. Run adversarial stress test suite
uv run pytest tests/test_xs_portfolio_alpha/test_tranche_ledger_adversarial.py -v

# 2. Run unit and acceptance suites
uv run pytest tests/test_xs_portfolio_alpha/test_tranche_ledger.py tests/test_xs_portfolio_alpha/test_e2e_acceptance.py -v

# 3. Run linting
uv run ruff check src/quant_system/research_xs_monthly/ tests/test_xs_portfolio_alpha/

# 4. Run static type checking
uv run mypy src/quant_system/research_xs_monthly/tranche_ledger.py tests/test_xs_portfolio_alpha/test_tranche_ledger.py tests/test_xs_portfolio_alpha/test_tranche_ledger_adversarial.py

# 5. Run agent claims and disk layout audits
powershell -ExecutionPolicy Bypass -File scripts/audit-agent-claims.ps1
powershell -ExecutionPolicy Bypass -File scripts/audit-disk-layout.ps1
```

Invalidation conditions:
- Any test failure in `test_tranche_ledger_adversarial.py`.
- Any observed state where `total_exposure() > Decimal("1.0000")` or `cash < Decimal("0.00")`.
- Any unhandled exception or non-fail-closed behavior on `execution_date < decision_date`.
