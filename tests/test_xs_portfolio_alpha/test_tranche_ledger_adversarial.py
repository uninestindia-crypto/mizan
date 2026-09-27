"""Adversarial Stress Testing & Capital Invariant Empirical Verification Harness (M2).

Adversarial Challenger Test Suite targeting:
`src/quant_system/research_xs_monthly/tranche_ledger.py`

Verifies:
1. Leverage Invariant Stress Tests:
   - Extreme price spikes (+1000%, +10000%) across holding periods.
   - Extreme price crashes (-99.9%, -99.999%, -100.0%) across holding periods.
   - Asymmetric multi-tranche stress (surges, crashes, circuit locks, cash in parallel).
   - Monte Carlo fuzzing (500 randomized price paths with shocks in [-99.9%, +2000%]).
   - Guarantee: aggregate portfolio total_exposure strictly <= Decimal("1.0000") and >= Decimal("0.0000").
2. Cash Non-Negativity Stress Tests:
   - Micro-capital boundary (₹1.00 initial capital, sub-rupee tranche allocations).
   - Nano-capital boundary (₹0.04 initial capital, 1 paisa per tranche).
   - Ultra-expensive share boundary (share price > available cash).
   - Exact half-paisa fee rounding boundaries.
   - Exhaustive mathematical domain check across 10,000 discrete trade sizes.
   - Multi-round churning fuzzing (50 consecutive rebalances with volatile prices).
   - Guarantee: cash balance is NEVER negative under any combination of prices, fees, and quantities.
3. Lookahead Leakage Guard Tests:
   - Rejection when execution_date < decision_date raises ValueError.
   - Extreme lookahead violation (1 year in the past).
   - Fail-closed atomicity: state is 100% unchanged (no-op) upon rejection.
   - Next-open execution fill pricing verification.
4. Circuit Lock & Boundary Robustness Tests:
   - 100% circuit-locked entry (volume == 0 and high == low).
   - 100% circuit-locked exit (carry over without forced liquidation).
   - Zero-price / bankruptcy liquidation.
   - Zero-cash rebalancing attempts (no division by zero).
   - Missing price mark-to-market fallbacks.
"""

from __future__ import annotations

import random
from datetime import date, timedelta
from decimal import Decimal

import pytest

from quant_system.research_xs_monthly.tranche_ledger import (
    StaggeredTrancheLedger,
    Tranche,
)

# =================================================================================================
# 1. LEVERAGE INVARIANT STRESS TESTS (Spikes +1000%, Crashes -99.9%, Fuzzing)
# =================================================================================================


def test_adversarial_single_asset_surge_1000_pct() -> None:
    """Verify extreme price spike of +1000% strictly maintains total_exposure <= 1.0000."""
    initial = Decimal("100000.00")
    ledger = StaggeredTrancheLedger(initial, num_tranches=4)
    # Entry at 100.00
    res = ledger.rebalance_tranche(
        tranche_id=0,
        decision_date=date(2024, 1, 5),
        execution_date=date(2024, 1, 8),
        selected_symbols=["ROCKET"],
        open_prices={"ROCKET": Decimal("100.00")},
    )
    assert "ROCKET" in res.bought_symbols

    # Surge +1000% -> price becomes 1100.00
    surge_prices = {"ROCKET": Decimal("1100.00")}
    nav = ledger.mark_to_market(date(2024, 1, 15), surge_prices)

    assert nav.total_exposure <= Decimal("1.0000")
    assert nav.total_exposure >= Decimal("0.0000")
    assert ledger.total_exposure() <= Decimal("1.0000")
    assert nav.total_nav > initial


def test_adversarial_multi_asset_hyper_surge_10000_pct() -> None:
    """Verify hyper-surge of +10,000% across all 4 tranches maintains exposure <= 1.0000."""
    initial = Decimal("1000000.00")
    ledger = StaggeredTrancheLedger(initial, num_tranches=4)
    symbols = [f"SURGE_{i}" for i in range(8)]
    base_prices = {s: Decimal("50.00") for s in symbols}

    for t_id in range(4):
        picks = symbols[t_id * 2 : t_id * 2 + 2]
        ledger.rebalance_tranche(
            tranche_id=t_id,
            decision_date=date(2024, 1, 5),
            execution_date=date(2024, 1, 8),
            selected_symbols=picks,
            open_prices=base_prices,
        )

    # 100x spike (+10,000%): 50.00 -> 5050.00
    hyper_prices = {s: Decimal("5050.00") for s in symbols}
    nav = ledger.mark_to_market(date(2024, 1, 20), hyper_prices)

    assert nav.total_exposure <= Decimal("1.0000")
    assert nav.total_exposure >= Decimal("0.0000")
    assert ledger.total_exposure() <= Decimal("1.0000")
    assert nav.total_nav > initial * 10


def test_adversarial_single_asset_crash_99_9_pct() -> None:
    """Verify extreme price crash of -99.9% strictly maintains total_exposure <= 1.0000 and >= 0."""
    initial = Decimal("100000.00")
    ledger = StaggeredTrancheLedger(initial, num_tranches=4)
    res = ledger.rebalance_tranche(
        tranche_id=0,
        decision_date=date(2024, 1, 5),
        execution_date=date(2024, 1, 8),
        selected_symbols=["DOOM"],
        open_prices={"DOOM": Decimal("1000.00")},
    )
    assert "DOOM" in res.bought_symbols

    # Crash -99.9% -> price drops from 1000.00 to 1.00
    crash_prices = {"DOOM": Decimal("1.00")}
    nav = ledger.mark_to_market(date(2024, 1, 15), crash_prices)

    assert nav.total_exposure <= Decimal("1.0000")
    assert nav.total_exposure >= Decimal("0.0000")
    assert ledger.total_exposure() <= Decimal("1.0000")
    assert nav.total_nav < initial
    assert nav.cash >= Decimal("0.00")


def test_adversarial_micro_penny_crash_99_999_pct() -> None:
    """Verify catastrophic crash to 1 paisa (₹0.01) maintains exposure <= 1.0000."""
    initial = Decimal("100000.00")
    ledger = StaggeredTrancheLedger(initial, num_tranches=4)
    ledger.rebalance_tranche(
        tranche_id=0,
        decision_date=date(2024, 1, 5),
        execution_date=date(2024, 1, 8),
        selected_symbols=["PENNY_CRASH"],
        open_prices={"PENNY_CRASH": Decimal("500.00")},
    )

    # 500.00 -> 0.01 (-99.998%)
    nav = ledger.mark_to_market(date(2024, 1, 15), {"PENNY_CRASH": Decimal("0.01")})
    assert nav.total_exposure <= Decimal("1.0000")
    assert nav.total_exposure >= Decimal("0.0000")
    assert nav.cash > Decimal("0.00")


def test_adversarial_total_wipeout_zero_price_crash() -> None:
    """Verify 100% wipeout (price = 0.00) yields exposure == 0.0000 without crashing."""
    initial = Decimal("100000.00")
    ledger = StaggeredTrancheLedger(initial, num_tranches=4)
    ledger.rebalance_tranche(
        tranche_id=0,
        decision_date=date(2024, 1, 5),
        execution_date=date(2024, 1, 8),
        selected_symbols=["ZEROED"],
        open_prices={"ZEROED": Decimal("100.00")},
    )

    # All positions drop to 0.00
    nav = ledger.mark_to_market(date(2024, 1, 15), {"ZEROED": Decimal("0.00")})
    assert nav.positions_value == Decimal("0.00")
    assert nav.total_exposure == Decimal("0.0000")
    assert nav.total_nav == nav.cash
    assert nav.total_exposure <= Decimal("1.0000")


def test_adversarial_asymmetric_cross_tranche_extremes() -> None:
    """Verify asymmetric cross-tranche stress: spikes, crashes, locks, and cash in parallel."""
    initial = Decimal("400000.00")
    ledger = StaggeredTrancheLedger(initial, num_tranches=4)

    # Tranche 0: will spike +1000%
    ledger.rebalance_tranche(
        0, date(2024, 1, 1), date(2024, 1, 2), ["SPIKE"], {"SPIKE": Decimal("100.00")}
    )
    # Tranche 1: will crash -99.9%
    ledger.rebalance_tranche(
        1, date(2024, 1, 8), date(2024, 1, 9), ["CRASH"], {"CRASH": Decimal("1000.00")}
    )
    # Tranche 2: will be circuit locked
    ledger.rebalance_tranche(
        2, date(2024, 1, 15), date(2024, 1, 16), ["LOCKED"], {"LOCKED": Decimal("50.00")}
    )
    # Tranche 3: remains 100% cash

    # Stress evaluation
    stress_prices = {
        "SPIKE": Decimal("1100.00"),  # +1000%
        "CRASH": Decimal("1.00"),  # -99.9%
        "LOCKED": Decimal("50.00"),
    }
    nav = ledger.mark_to_market(date(2024, 1, 25), stress_prices)

    assert nav.total_exposure <= Decimal("1.0000")
    assert nav.total_exposure >= Decimal("0.0000")
    assert ledger.total_exposure() <= Decimal("1.0000")
    assert nav.cash >= Decimal("100000.00")  # Tranche 3 cash + uninvested cash


def test_adversarial_monte_carlo_price_fuzzing_500_trials() -> None:
    """Adversarial stress test: 500 randomized trials of extreme price shifts."""
    rng = random.Random(42)
    universe = [f"SYM_{i:02d}" for i in range(20)]
    initial = Decimal("1000000.00")
    ledger = StaggeredTrancheLedger(initial, num_tranches=4)

    base_prices = {s: Decimal(f"{rng.uniform(10.0, 5000.0):.2f}") for s in universe}

    # Invest across all 4 tranches
    for t_id in range(4):
        picks = universe[t_id * 4 : t_id * 4 + 4]
        ledger.rebalance_tranche(
            t_id,
            date(2024, 1, 5),
            date(2024, 1, 8),
            picks,
            base_prices,
        )

    # 500 randomized market shocks
    for trial in range(500):
        shock_prices: dict[str, Decimal] = {}
        for s in universe:
            # Multiplier between 0.001 (-99.9%) and 21.0 (+2000%)
            mult = rng.uniform(0.001, 21.0)
            base_p = float(base_prices[s])
            shocked_p = Decimal(f"{max(0.01, base_p * mult):.2f}")
            shock_prices[s] = shocked_p

        nav = ledger.mark_to_market(date(2024, 1, 20), shock_prices)
        assert nav.total_exposure <= Decimal("1.0000"), (
            f"Trial {trial} failed: exposure {nav.total_exposure} > 1.0"
        )
        assert nav.total_exposure >= Decimal("0.0000")
        assert nav.total_nav == nav.cash + nav.positions_value


# =================================================================================================
# 2. CASH NON-NEGATIVITY STRESS TESTS (Micro-capital, Fees, Churning)
# =================================================================================================


def test_adversarial_micro_capital_one_rupee() -> None:
    """Verify micro-capital (₹1.00 total, ₹0.25 per tranche) maintains cash >= 0."""
    initial = Decimal("1.00")
    ledger = StaggeredTrancheLedger(initial, num_tranches=4)
    assert ledger.tranches[0].cash == Decimal("0.25")

    # Prices around 0.25
    prices = {
        "A": Decimal("0.10"),
        "B": Decimal("0.20"),
        "C": Decimal("0.24"),
        "D": Decimal("0.25"),
        "E": Decimal("0.26"),
    }
    res = ledger.rebalance_tranche(
        0, date(2024, 1, 5), date(2024, 1, 8), ["A", "B", "C", "D", "E"], prices
    )
    assert ledger.tranches[0].cash >= Decimal("0.00")
    assert res.new_cash >= Decimal("0.00")


def test_adversarial_nano_capital_four_paise() -> None:
    """Verify nano-capital (₹0.04 total, ₹0.01 per tranche) maintains cash >= 0."""
    initial = Decimal("0.04")
    ledger = StaggeredTrancheLedger(initial, num_tranches=4)
    for t_id in range(4):
        assert ledger.tranches[t_id].cash == Decimal("0.01")

    # Try buying stocks costing ₹0.01
    prices = {"TINY": Decimal("0.01")}
    res = ledger.rebalance_tranche(0, date(2024, 1, 5), date(2024, 1, 8), ["TINY"], prices)
    assert ledger.tranches[0].cash >= Decimal("0.00")
    assert res.new_cash >= Decimal("0.00")


def test_adversarial_expensive_stocks_exceeding_capital() -> None:
    """Verify stocks priced well above available capital result in 0 shares and leave cash intact."""
    initial = Decimal("50000.00")  # 12,500 per tranche
    ledger = StaggeredTrancheLedger(initial, num_tranches=4)

    prices = {
        "MRF": Decimal("140000.00"),
        "PAGEIND": Decimal("45000.00"),
        "HONAUT": Decimal("38000.00"),
    }
    res = ledger.rebalance_tranche(
        0, date(2024, 1, 5), date(2024, 1, 8), list(prices.keys()), prices
    )
    assert len(res.bought_symbols) == 0
    assert ledger.tranches[0].cash == Decimal("12500.00")
    assert len(ledger.tranches[0].positions) == 0


def test_adversarial_half_paisa_fee_rounding_exactness() -> None:
    """Verify half-paisa fee rounding boundaries never deduct excess cash."""
    initial = Decimal("10000.00")
    ledger = StaggeredTrancheLedger(initial, num_tranches=4)
    # Tranche cash = 2500.00
    # Find price where cost * 0.00112 is close to 0.005
    prices = {"SYM_ROUND": Decimal("4.46"), "SYM_ROUND2": Decimal("4.47")}
    res = ledger.rebalance_tranche(
        0, date(2024, 1, 5), date(2024, 1, 8), list(prices.keys()), prices
    )
    assert ledger.tranches[0].cash >= Decimal("0.00")
    assert res.statutory_fees >= Decimal("0.00")


def test_adversarial_exhaustive_fee_deduction_domain() -> None:
    """Exhaustively verify across 10,000 discrete trade values that net proceeds >= 0."""
    fee_rate = StaggeredTrancheLedger.FEE_ONE_WAY
    for paise in range(1, 10001):
        proceeds = Decimal(paise) / Decimal("100.00")
        fee = (proceeds * fee_rate).quantize(Decimal("0.01"))
        net = proceeds - fee
        assert net >= Decimal("0.00"), f"Net proceeds negative at {proceeds}: {net}"
        assert fee >= Decimal("0.00")


def test_adversarial_fifty_cycle_churning_fuzz() -> None:
    """Stress test: 50 rapid sequential rebalance cycles with random prices maintain cash >= 0."""
    rng = random.Random(1337)
    initial = Decimal("500000.00")
    ledger = StaggeredTrancheLedger(initial, num_tranches=4)
    universe = [f"STK_{i}" for i in range(15)]

    cur_date = date(2024, 1, 1)
    for cycle in range(50):
        t_id = cycle % 4
        dec_date = cur_date
        exec_date = cur_date + timedelta(days=1)

        prices = {s: Decimal(f"{rng.uniform(1.0, 2000.0):.2f}") for s in universe}
        sample_size = rng.randint(1, 8)
        picks = rng.sample(universe, sample_size)

        res = ledger.rebalance_tranche(t_id, dec_date, exec_date, picks, prices)

        assert res.new_cash >= Decimal("0.00"), f"Negative cash in cycle {cycle}: {res.new_cash}"
        assert ledger.tranches[t_id].cash >= Decimal("0.00")
        assert res.new_exposure <= Decimal("1.0000")
        assert ledger.total_exposure() <= Decimal("1.0000")

        cur_date += timedelta(days=5)


# =================================================================================================
# 3. LOOKAHEAD LEAKAGE GUARD TESTS
# =================================================================================================


def test_adversarial_lookahead_execution_precedes_decision_fails_closed() -> None:
    """Verify execution_date < decision_date raises ValueError and performs zero state changes."""
    ledger = StaggeredTrancheLedger(Decimal("100000.00"), num_tranches=4)
    initial_cash = ledger.tranches[0].cash
    initial_fees = ledger.total_statutory_fees()

    with pytest.raises(ValueError, match="cannot precede decision date"):
        ledger.rebalance_tranche(
            tranche_id=0,
            decision_date=date(2024, 5, 10),
            execution_date=date(2024, 5, 9),  # 1 day prior (leakage attempt)
            selected_symbols=["INFY"],
            open_prices={"INFY": Decimal("1500.00")},
        )

    # State must be completely unchanged (atomic fail-closed)
    assert ledger.tranches[0].cash == initial_cash
    assert len(ledger.tranches[0].positions) == 0
    assert ledger.total_statutory_fees() == initial_fees


def test_adversarial_lookahead_extreme_past_date_fails_closed() -> None:
    """Verify execution date 1 year in the past raises ValueError and preserves state."""
    ledger = StaggeredTrancheLedger(Decimal("100000.00"), num_tranches=4)
    with pytest.raises(ValueError, match="cannot precede decision date"):
        ledger.rebalance_tranche(
            tranche_id=1,
            decision_date=date(2024, 12, 31),
            execution_date=date(2023, 12, 31),
            selected_symbols=["INFY"],
            open_prices={"INFY": Decimal("1500.00")},
        )
    assert len(ledger.tranches[1].positions) == 0


def test_adversarial_next_open_execution_pricing_fidelity() -> None:
    """Verify fill occurs strictly at execution_date open price, not decision close price."""
    ledger = StaggeredTrancheLedger(Decimal("100000.00"), num_tranches=4)
    # Decision at T (close price was 2000.00)
    # Execution at T+1 (open price is 2050.00)
    execution_prices = {"RELIANCE": Decimal("2050.00")}

    ledger.rebalance_tranche(
        tranche_id=0,
        decision_date=date(2024, 3, 1),
        execution_date=date(2024, 3, 4),
        selected_symbols=["RELIANCE"],
        open_prices=execution_prices,
    )
    pos = ledger.tranches[0].positions["RELIANCE"]
    assert pos.entry_price == Decimal("2050.00")
    assert pos.entry_date == date(2024, 3, 4)


# =================================================================================================
# 4. CIRCUIT LOCK & BOUNDARY ROBUSTNESS TESTS
# =================================================================================================


def test_adversarial_all_symbols_circuit_locked_on_entry() -> None:
    """Verify when 100% of candidate symbols are circuit locked, zero buys occur and cash is untouched."""
    ledger = StaggeredTrancheLedger(Decimal("100000.00"), num_tranches=4)
    candidates = ["LOCK_A", "LOCK_B", "LOCK_C"]
    prices = {s: Decimal("100.00") for s in candidates}
    volumes = {"LOCK_A": 0, "LOCK_B": 0, "LOCK_C": 0}

    res = ledger.rebalance_tranche(
        0, date(2024, 1, 5), date(2024, 1, 8), candidates, prices, volumes=volumes
    )
    assert len(res.bought_symbols) == 0
    assert ledger.tranches[0].cash == Decimal("25000.00")
    assert len(ledger.tranches[0].positions) == 0


def test_adversarial_all_symbols_limit_locked_on_entry() -> None:
    """Verify when 100% of candidate symbols have high == low, zero buys occur."""
    ledger = StaggeredTrancheLedger(Decimal("100000.00"), num_tranches=4)
    candidates = ["LIMIT_A", "LIMIT_B"]
    prices = {"LIMIT_A": Decimal("100.00"), "LIMIT_B": Decimal("200.00")}
    highs = {"LIMIT_A": Decimal("100.00"), "LIMIT_B": Decimal("200.00")}
    lows = {"LIMIT_A": Decimal("100.00"), "LIMIT_B": Decimal("200.00")}

    res = ledger.rebalance_tranche(
        0, date(2024, 1, 5), date(2024, 1, 8), candidates, prices, highs=highs, lows=lows
    )
    assert len(res.bought_symbols) == 0
    assert ledger.tranches[0].cash == Decimal("25000.00")


def test_adversarial_circuit_locked_exit_persists_unliquidated() -> None:
    """Verify positions locked on exit are retained in tranche book with zero forced liquidation."""
    ledger = StaggeredTrancheLedger(Decimal("100000.00"), num_tranches=4)
    ledger.rebalance_tranche(
        0, date(2024, 1, 5), date(2024, 1, 8), ["HOLD_ME"], {"HOLD_ME": Decimal("100.00")}
    )
    orig_qty = ledger.tranches[0].positions["HOLD_ME"].quantity

    # Attempt liquidation during upper circuit lock (high == low)
    res_exit = ledger.rebalance_tranche(
        0,
        date(2024, 2, 5),
        date(2024, 2, 6),
        [],
        {"HOLD_ME": Decimal("120.00")},
        highs={"HOLD_ME": Decimal("120.00")},
        lows={"HOLD_ME": Decimal("120.00")},
    )
    assert "HOLD_ME" not in res_exit.sold_symbols
    assert "HOLD_ME" in ledger.tranches[0].positions
    assert ledger.tranches[0].positions["HOLD_ME"].quantity == orig_qty


def test_adversarial_rebalance_with_zero_cash_survives() -> None:
    """Verify rebalance on a tranche with exactly 0 cash does not divide by zero or error."""
    ledger = StaggeredTrancheLedger(Decimal("100000.00"), num_tranches=4)
    # Manually drain tranche 0 cash to zero
    ledger.tranches[0] = Tranche(
        tranche_id=0,
        allocation_capital=Decimal("25000.00"),
        entry_date=date(2024, 1, 1),
        exit_date=date(2024, 1, 31),
        positions={},
        cash=Decimal("0.00"),
    )

    res = ledger.rebalance_tranche(
        0,
        date(2024, 2, 1),
        date(2024, 2, 2),
        ["INFY"],
        {"INFY": Decimal("1500.00")},
    )
    assert len(res.bought_symbols) == 0
    assert res.new_cash == Decimal("0.00")
    assert res.new_exposure == Decimal("0.00")


def test_adversarial_duplicate_selected_symbols_safe() -> None:
    """Verify passing duplicate symbols in selected_symbols does not corrupt cash balance."""
    ledger = StaggeredTrancheLedger(Decimal("100000.00"), num_tranches=4)
    res = ledger.rebalance_tranche(
        0,
        date(2024, 1, 5),
        date(2024, 1, 8),
        ["TCS", "TCS", "TCS"],
        {"TCS": Decimal("3000.00")},
    )
    assert res.new_cash >= Decimal("0.00")
    assert ledger.tranches[0].cash >= Decimal("0.00")
    assert ledger.total_exposure() <= Decimal("1.0000")


def test_adversarial_empty_selection_clears_positions() -> None:
    """Verify rebalancing with empty selection liquidates all liquid positions to cash."""
    ledger = StaggeredTrancheLedger(Decimal("100000.00"), num_tranches=4)
    ledger.rebalance_tranche(
        0, date(2024, 1, 5), date(2024, 1, 8), ["SYM_1"], {"SYM_1": Decimal("100.00")}
    )
    assert len(ledger.tranches[0].positions) == 1

    # Liquidate to empty
    res = ledger.rebalance_tranche(
        0, date(2024, 2, 5), date(2024, 2, 6), [], {"SYM_1": Decimal("110.00")}
    )
    assert len(ledger.tranches[0].positions) == 0
    assert len(res.sold_symbols) == 1
    assert ledger.tranches[0].cash > Decimal("25000.00")  # profit after fees
    assert ledger.tranches[0].cash >= Decimal("0.00")
