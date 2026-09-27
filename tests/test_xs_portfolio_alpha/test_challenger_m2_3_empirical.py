"""Empirical Challenger Verification & Stress Test Suite (Milestone 2 Defects).

Target: `src/quant_system/research_xs_monthly/tranche_ledger.py`
Challenger: challenger_m2_3

Independent, adversarial empirical tests verifying that the 4 reported defects
have been definitively resolved:
1. Empty dicts `highs={}` and `lows={}` do NOT falsely lock candidate buys or existing positions.
2. Partial high/low dicts do NOT lock unquoted stocks.
3. Duplicate candidate symbols in `selected_symbols` allocate each symbol exactly once
   without double fee or cash destruction.
4. Non-positive exit prices cannot drive cash balance negative.
5. `execution_date <= decision_date` strictly raises `ValueError` and fails closed.
6. Stress & property fuzzing harness verifying capital preservation and cash non-negativity.
"""

from __future__ import annotations

import random
import time
from datetime import date, timedelta
from decimal import Decimal

import pytest

from quant_system.research_xs_monthly.tranche_ledger import (
    StaggeredTrancheLedger,
    TranchePosition,
)

# =================================================================================================
# Defect 1: Empty dicts `highs={}` and `lows={}` do NOT lock candidate buys or existing positions
# =================================================================================================


def test_empirical_empty_highs_lows_does_not_lock_buys() -> None:
    """Verify passing empty dicts highs={} and lows={} buys all candidate stocks."""
    ledger = StaggeredTrancheLedger(Decimal("100000.00"), num_tranches=4)
    # Tranche 0 capital = 25,000.00
    candidates = ["SYM_ALPHA", "SYM_BETA", "SYM_GAMMA"]
    prices = {s: Decimal("100.00") for s in candidates}

    res = ledger.rebalance_tranche(
        tranche_id=0,
        decision_date=date(2024, 1, 1),
        execution_date=date(2024, 1, 2),
        selected_symbols=candidates,
        open_prices=prices,
        highs={},
        lows={},
    )

    assert set(res.bought_symbols) == set(candidates), (
        f"Expected all candidates {candidates} to be bought, but got {res.bought_symbols}"
    )
    for sym in candidates:
        assert sym in ledger.tranches[0].positions
        assert ledger.tranches[0].positions[sym].quantity > 0
    assert ledger.tranches[0].cash >= Decimal("0.00")


def test_empirical_empty_highs_lows_does_not_lock_sells() -> None:
    """Verify passing empty dicts highs={} and lows={} liquidates all positions on exit."""
    ledger = StaggeredTrancheLedger(Decimal("100000.00"), num_tranches=4)
    symbols = ["POS_1", "POS_2"]
    prices_entry = {s: Decimal("50.00") for s in symbols}

    # Step 1: Establish positions
    ledger.rebalance_tranche(
        tranche_id=0,
        decision_date=date(2024, 1, 1),
        execution_date=date(2024, 1, 2),
        selected_symbols=symbols,
        open_prices=prices_entry,
    )
    assert len(ledger.tranches[0].positions) == 2

    # Step 2: Liquidate with empty dicts highs={} and lows={}
    prices_exit = {s: Decimal("60.00") for s in symbols}
    res = ledger.rebalance_tranche(
        tranche_id=0,
        decision_date=date(2024, 1, 22),
        execution_date=date(2024, 1, 23),
        selected_symbols=[],
        open_prices=prices_exit,
        highs={},
        lows={},
    )

    assert set(res.sold_symbols) == set(symbols), (
        f"Expected {symbols} to be sold on liquidation, but got {res.sold_symbols}"
    )
    assert len(ledger.tranches[0].positions) == 0
    assert res.new_cash > Decimal("25000.00")  # Profitable liquidation minus fees


def test_empirical_empty_highs_lows_with_empty_volumes() -> None:
    """Verify empty dicts across highs, lows, and volumes together never trigger circuit lock."""
    ledger = StaggeredTrancheLedger(Decimal("100000.00"), num_tranches=4)
    res = ledger.rebalance_tranche(
        tranche_id=0,
        decision_date=date(2024, 1, 1),
        execution_date=date(2024, 1, 2),
        selected_symbols=["TEST_SYM"],
        open_prices={"TEST_SYM": Decimal("100.00")},
        volumes={},
        highs={},
        lows={},
    )
    assert res.bought_symbols == ["TEST_SYM"]
    assert "TEST_SYM" in ledger.tranches[0].positions


# =================================================================================================
# Defect 2: Partial high/low dicts do NOT lock unquoted stocks
# =================================================================================================


def test_empirical_partial_highs_lows_unquoted_not_locked_on_buy() -> None:
    """Verify partial high/low dicts lock only symbols present with high == low, permitting others."""
    ledger = StaggeredTrancheLedger(Decimal("100000.00"), num_tranches=4)
    # Five symbols representing all combinatorial states of high/low presence:
    symbols = [
        "SYM_EQUAL_LOCK",  # high == low -> MUST LOCK
        "SYM_DIFF_UNLOCKED",  # high != low -> MUST NOT LOCK
        "SYM_HIGH_ONLY",  # only high present -> MUST NOT LOCK
        "SYM_LOW_ONLY",  # only low present -> MUST NOT LOCK
        "SYM_OMITTED",  # neither present -> MUST NOT LOCK
    ]
    prices = {s: Decimal("100.00") for s in symbols}
    highs = {
        "SYM_EQUAL_LOCK": Decimal("100.00"),
        "SYM_DIFF_UNLOCKED": Decimal("105.00"),
        "SYM_HIGH_ONLY": Decimal("100.00"),
    }
    lows = {
        "SYM_EQUAL_LOCK": Decimal("100.00"),
        "SYM_DIFF_UNLOCKED": Decimal("95.00"),
        "SYM_LOW_ONLY": Decimal("100.00"),
    }

    res = ledger.rebalance_tranche(
        tranche_id=0,
        decision_date=date(2024, 1, 1),
        execution_date=date(2024, 1, 2),
        selected_symbols=symbols,
        open_prices=prices,
        highs=highs,
        lows=lows,
    )

    assert "SYM_EQUAL_LOCK" not in res.bought_symbols
    assert "SYM_DIFF_UNLOCKED" in res.bought_symbols
    assert "SYM_HIGH_ONLY" in res.bought_symbols
    assert "SYM_LOW_ONLY" in res.bought_symbols
    assert "SYM_OMITTED" in res.bought_symbols
    assert len(res.bought_symbols) == 4


def test_empirical_partial_highs_lows_unquoted_not_locked_on_exit() -> None:
    """Verify partial high/low dicts on exit only retain high == low symbols and liquidate others."""
    ledger = StaggeredTrancheLedger(Decimal("100000.00"), num_tranches=4)
    symbols = ["POS_LOCKED", "POS_UNLOCKED", "POS_HIGH_ONLY", "POS_LOW_ONLY", "POS_OMITTED"]

    # Manually populate tranche positions to test exit isolation
    for s in symbols:
        ledger.tranches[0].positions[s] = TranchePosition(
            symbol=s,
            quantity=10,
            entry_price=Decimal("100.00"),
            current_price=Decimal("100.00"),
            entry_date=date(2024, 1, 2),
        )

    prices = {s: Decimal("100.00") for s in symbols}
    highs = {
        "POS_LOCKED": Decimal("100.00"),
        "POS_UNLOCKED": Decimal("105.00"),
        "POS_HIGH_ONLY": Decimal("100.00"),
    }
    lows = {
        "POS_LOCKED": Decimal("100.00"),
        "POS_UNLOCKED": Decimal("95.00"),
        "POS_LOW_ONLY": Decimal("100.00"),
    }

    res = ledger.rebalance_tranche(
        tranche_id=0,
        decision_date=date(2024, 1, 22),
        execution_date=date(2024, 1, 23),
        selected_symbols=[],
        open_prices=prices,
        highs=highs,
        lows=lows,
    )

    # Only POS_LOCKED should remain in positions
    assert "POS_LOCKED" in ledger.tranches[0].positions
    assert "POS_LOCKED" not in res.sold_symbols

    # All others must be sold
    for s in ["POS_UNLOCKED", "POS_HIGH_ONLY", "POS_LOW_ONLY", "POS_OMITTED"]:
        assert s in res.sold_symbols
        assert s not in ledger.tranches[0].positions


# =================================================================================================
# Defect 3: Duplicate candidate symbols in `selected_symbols` allocate each symbol exactly once
# =================================================================================================


def test_empirical_duplicate_symbols_exact_accounting_and_no_cash_destruction() -> None:
    """Verify duplicate candidate symbols are deduplicated with exact cash and fee accounting."""
    ledger = StaggeredTrancheLedger(Decimal("100000.00"), num_tranches=4)
    initial_cash = ledger.tranches[0].cash  # 25,000.00

    # selected_symbols contains heavy duplicates
    selected = ["INFY", "INFY", "TCS", "INFY", "TCS", "TCS"]
    prices = {"INFY": Decimal("1500.00"), "TCS": Decimal("3500.00")}

    res = ledger.rebalance_tranche(
        tranche_id=0,
        decision_date=date(2024, 1, 1),
        execution_date=date(2024, 1, 2),
        selected_symbols=selected,
        open_prices=prices,
    )

    # Must buy INFY and TCS exactly once in order
    assert res.bought_symbols == ["INFY", "TCS"]
    assert len(ledger.tranches[0].positions) == 2

    # Theoretical expectation:
    # 2 unique stocks -> capital per stock = 25000.00 / 2 = 12500.00
    cap_per_stock = initial_cash / Decimal(2)
    fee_rate = StaggeredTrancheLedger.FEE_ONE_WAY

    # INFY
    eff_p_infy = Decimal("1500.00") * (Decimal("1.0") + fee_rate)
    expected_qty_infy = int(cap_per_stock // eff_p_infy)
    expected_cost_infy = expected_qty_infy * Decimal("1500.00")
    expected_fee_infy = (expected_cost_infy * fee_rate).quantize(Decimal("0.01"))

    # TCS
    eff_p_tcs = Decimal("3500.00") * (Decimal("1.0") + fee_rate)
    expected_qty_tcs = int(cap_per_stock // eff_p_tcs)
    expected_cost_tcs = expected_qty_tcs * Decimal("3500.00")
    expected_fee_tcs = (expected_cost_tcs * fee_rate).quantize(Decimal("0.01"))

    expected_cash = initial_cash - (
        expected_cost_infy + expected_fee_infy + expected_cost_tcs + expected_fee_tcs
    )

    assert ledger.tranches[0].positions["INFY"].quantity == expected_qty_infy
    assert ledger.tranches[0].positions["TCS"].quantity == expected_qty_tcs
    assert res.new_cash == expected_cash
    assert ledger.tranches[0].cash == expected_cash
    assert res.statutory_fees == expected_fee_infy + expected_fee_tcs


def test_empirical_extreme_duplicates_one_hundred_fold() -> None:
    """Verify 100 identical duplicates allocate single position without double fees."""
    ledger = StaggeredTrancheLedger(Decimal("100000.00"), num_tranches=4)
    res = ledger.rebalance_tranche(
        tranche_id=0,
        decision_date=date(2024, 1, 1),
        execution_date=date(2024, 1, 2),
        selected_symbols=["SOLO"] * 100,
        open_prices={"SOLO": Decimal("200.00")},
    )
    assert res.bought_symbols == ["SOLO"]
    assert len(ledger.tranches[0].positions) == 1
    # Full capital 25,000 / 1 stock -> 25000 // (200 * 1.00112) = 124 shares
    assert ledger.tranches[0].positions["SOLO"].quantity == 124
    cost = Decimal("124") * Decimal("200.00")
    fee = (cost * StaggeredTrancheLedger.FEE_ONE_WAY).quantize(Decimal("0.01"))
    assert res.statutory_fees == fee
    assert ledger.tranches[0].cash == Decimal("25000.00") - cost - fee


def test_empirical_duplicates_preserve_first_seen_order() -> None:
    """Verify deduplication strictly preserves first-seen ranking order."""
    ledger = StaggeredTrancheLedger(Decimal("100000.00"), num_tranches=4)
    # Order: C, B, A
    res = ledger.rebalance_tranche(
        tranche_id=0,
        decision_date=date(2024, 1, 1),
        execution_date=date(2024, 1, 2),
        selected_symbols=["SYM_C", "SYM_B", "SYM_C", "SYM_A", "SYM_B", "SYM_A"],
        open_prices={
            "SYM_A": Decimal("100.00"),
            "SYM_B": Decimal("100.00"),
            "SYM_C": Decimal("100.00"),
        },
    )
    assert res.bought_symbols == ["SYM_C", "SYM_B", "SYM_A"]


# =================================================================================================
# Defect 4: Non-positive exit prices cannot drive cash balance negative
# =================================================================================================


def test_empirical_zero_exit_price_does_not_drain_cash() -> None:
    """Verify exit price of 0.00 does not liquidate position or drive cash negative."""
    ledger = StaggeredTrancheLedger(Decimal("100000.00"), num_tranches=4)
    # Setup position
    ledger.rebalance_tranche(
        tranche_id=0,
        decision_date=date(2024, 1, 1),
        execution_date=date(2024, 1, 2),
        selected_symbols=["STK_ZERO"],
        open_prices={"STK_ZERO": Decimal("50.00")},
    )
    cash_before_exit = ledger.tranches[0].cash

    # Attempt liquidation at 0.00
    res = ledger.rebalance_tranche(
        tranche_id=0,
        decision_date=date(2024, 1, 22),
        execution_date=date(2024, 1, 23),
        selected_symbols=[],
        open_prices={"STK_ZERO": Decimal("0.00")},
    )
    assert "STK_ZERO" not in res.sold_symbols
    assert "STK_ZERO" in ledger.tranches[0].positions
    assert ledger.tranches[0].cash == cash_before_exit
    assert ledger.tranches[0].cash >= Decimal("0.00")


def test_empirical_negative_exit_price_does_not_drain_cash() -> None:
    """Verify negative exit price does not liquidate position or drive cash negative."""
    ledger = StaggeredTrancheLedger(Decimal("100000.00"), num_tranches=4)
    # Setup position
    ledger.rebalance_tranche(
        tranche_id=0,
        decision_date=date(2024, 1, 1),
        execution_date=date(2024, 1, 2),
        selected_symbols=["STK_NEG"],
        open_prices={"STK_NEG": Decimal("50.00")},
    )
    cash_before_exit = ledger.tranches[0].cash

    # Attempt liquidation at -100.00
    res = ledger.rebalance_tranche(
        tranche_id=0,
        decision_date=date(2024, 1, 22),
        execution_date=date(2024, 1, 23),
        selected_symbols=[],
        open_prices={"STK_NEG": Decimal("-100.00")},
    )
    assert "STK_NEG" not in res.sold_symbols
    assert "STK_NEG" in ledger.tranches[0].positions
    assert ledger.tranches[0].cash == cash_before_exit
    assert ledger.tranches[0].cash >= Decimal("0.00")


def test_empirical_mixed_exit_prices_positive_sold_non_positive_held() -> None:
    """Verify in mixed exit prices, positive ones are sold normally and non-positive ones held."""
    ledger = StaggeredTrancheLedger(Decimal("100000.00"), num_tranches=4)
    symbols = ["POS_GOOD", "POS_ZERO", "POS_NEG"]
    ledger.rebalance_tranche(
        tranche_id=0,
        decision_date=date(2024, 1, 1),
        execution_date=date(2024, 1, 2),
        selected_symbols=symbols,
        open_prices={s: Decimal("100.00") for s in symbols},
    )
    cash_before = ledger.tranches[0].cash

    res = ledger.rebalance_tranche(
        tranche_id=0,
        decision_date=date(2024, 1, 22),
        execution_date=date(2024, 1, 23),
        selected_symbols=[],
        open_prices={
            "POS_GOOD": Decimal("150.00"),
            "POS_ZERO": Decimal("0.00"),
            "POS_NEG": Decimal("-50.00"),
        },
    )

    assert res.sold_symbols == ["POS_GOOD"]
    assert "POS_GOOD" not in ledger.tranches[0].positions
    assert "POS_ZERO" in ledger.tranches[0].positions
    assert "POS_NEG" in ledger.tranches[0].positions
    assert ledger.tranches[0].cash > cash_before  # Proceeds from POS_GOOD added
    assert ledger.tranches[0].cash >= Decimal("0.00")


# =================================================================================================
# Defect 5: `execution_date <= decision_date` strictly raises `ValueError`
# =================================================================================================


def test_empirical_same_day_execution_strictly_raises_value_error() -> None:
    """Verify execution_date == decision_date raises ValueError and preserves state."""
    ledger = StaggeredTrancheLedger(Decimal("100000.00"), num_tranches=4)
    test_date = date(2024, 6, 15)
    initial_cash = ledger.tranches[0].cash

    with pytest.raises(ValueError, match="cannot precede decision date"):
        ledger.rebalance_tranche(
            tranche_id=0,
            decision_date=test_date,
            execution_date=test_date,
            selected_symbols=["INFY"],
            open_prices={"INFY": Decimal("1500.00")},
        )

    # State fail-closed check
    assert ledger.tranches[0].cash == initial_cash
    assert len(ledger.tranches[0].positions) == 0


def test_empirical_past_date_execution_strictly_raises_value_error() -> None:
    """Verify execution_date < decision_date raises ValueError."""
    ledger = StaggeredTrancheLedger(Decimal("100000.00"), num_tranches=4)
    with pytest.raises(ValueError, match="cannot precede decision date"):
        ledger.rebalance_tranche(
            tranche_id=0,
            decision_date=date(2024, 6, 15),
            execution_date=date(2024, 6, 14),
            selected_symbols=["INFY"],
            open_prices={"INFY": Decimal("1500.00")},
        )


def test_empirical_next_day_execution_succeeds() -> None:
    """Verify execution_date == decision_date + 1 day succeeds."""
    ledger = StaggeredTrancheLedger(Decimal("100000.00"), num_tranches=4)
    res = ledger.rebalance_tranche(
        tranche_id=0,
        decision_date=date(2024, 6, 15),
        execution_date=date(2024, 6, 16),
        selected_symbols=["INFY"],
        open_prices={"INFY": Decimal("1500.00")},
    )
    assert res.bought_symbols == ["INFY"]


# =================================================================================================
# 6. Stress & Property Fuzzing Harness
# =================================================================================================


def test_empirical_stress_fuzzing_all_defects_combined() -> None:
    """Fuzzing harness combining duplicate symbols, partial dicts, corrupted prices across 200 cycles."""
    rng = random.Random(20260925)
    ledger = StaggeredTrancheLedger(Decimal("500000.00"), num_tranches=4)
    universe = [f"STK_{i:02d}" for i in range(25)]

    cur_date = date(2024, 1, 1)
    start_time = time.perf_counter()

    for cycle in range(200):
        t_id = cycle % 4
        dec_date = cur_date
        exec_date = cur_date + timedelta(days=1)

        # Generate selected symbols with heavy duplicates
        num_picks = rng.randint(1, 15)
        raw_picks = [rng.choice(universe) for _ in range(num_picks * 3)]

        # Generate prices, occasionally non-positive or corrupted
        prices: dict[str, Decimal] = {}
        highs: dict[str, Decimal] = {}
        lows: dict[str, Decimal] = {}

        for sym in universe:
            price_type = rng.random()
            if price_type < 0.05:
                # Corrupt non-positive price
                p = Decimal(f"{rng.uniform(-50.0, 0.0):.2f}")
            else:
                p = Decimal(f"{rng.uniform(10.0, 3000.0):.2f}")
            prices[sym] = p

            # Randomly include in highs/lows or omit
            dict_presence = rng.random()
            if dict_presence < 0.2:
                pass  # Omitted from both
            elif dict_presence < 0.4:
                highs[sym] = p  # High only
            elif dict_presence < 0.6:
                lows[sym] = p  # Low only
            elif dict_presence < 0.8:
                # Circuit locked (high == low)
                highs[sym] = p
                lows[sym] = p
            else:
                # Normal unquoted trading (high != low)
                highs[sym] = p + Decimal("5.00")
                lows[sym] = max(Decimal("0.01"), p - Decimal("5.00"))

        res = ledger.rebalance_tranche(
            tranche_id=t_id,
            decision_date=dec_date,
            execution_date=exec_date,
            selected_symbols=raw_picks,
            open_prices=prices,
            highs=highs,
            lows=lows,
        )

        # Verify invariants
        assert res.new_cash >= Decimal("0.00"), f"Cycle {cycle}: cash negative: {res.new_cash}"
        assert ledger.tranches[t_id].cash >= Decimal("0.00")
        assert res.new_exposure <= Decimal("1.0000"), (
            f"Cycle {cycle}: exposure > 1.0: {res.new_exposure}"
        )
        assert ledger.total_exposure() <= Decimal("1.0000")

        # Mark to market validation
        nav = ledger.mark_to_market(
            exec_date, {s: max(Decimal("0.01"), prices[s]) for s in universe}
        )
        assert nav.total_exposure <= Decimal("1.0000")
        assert nav.total_exposure >= Decimal("0.0000")
        assert nav.cash >= Decimal("0.00")
        assert nav.total_nav == nav.cash + nav.positions_value

        cur_date += timedelta(days=5)

    elapsed = time.perf_counter() - start_time
    print(f"\n[Stress Fuzzing] 200 cycles executed in {elapsed:.3f}s. All invariants held.")
