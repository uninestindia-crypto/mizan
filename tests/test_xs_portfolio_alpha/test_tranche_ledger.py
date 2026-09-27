"""Comprehensive Unit Tests for Staggered Tranche Portfolio Ledger (R2).

Verifies:
1. 4-tranche autonomous weekly capital allocation (25% max capital each, cash isolation).
2. Next-open (T+1) execution pricing and cash accounting (decision at T, fill at T+1 open).
3. Exact 0.224% round-trip statutory fee model (11.2 bps entry + 11.2 bps exit) in Decimal math.
4. Circuit-lock protections (volume == 0 or high == low) on both buys and sells.
5. Capital preservation invariant: total portfolio leverage strictly <= 1.0000 under all market moves.
6. Mark-to-market NAV calculation with mixed prices, cash balance, and exact paisa reconciliation.
7. Top quintile selection (nominal 20%, 15% custom, 423-name scaling, RankedSymbol support).
8. Multi-cycle staggered cadence and integer share rounding without fractional shares.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from quant_system.research_xs_monthly.ranking import FactorComponents, RankedSymbol
from quant_system.research_xs_monthly.tranche_ledger import (
    LedgerNAV,
    StaggeredTrancheLedger,
    Tranche,
    TranchePosition,
    TrancheRebalanceResult,
    select_top_quintile,
)

# =================================================================================================
# 1. 4-Tranche Autonomous Capital Allocation & Initialization
# =================================================================================================


def test_ledger_initialization_four_autonomous_tranches() -> None:
    """Verify default initialization creates 4 independent tranches with 25% capital each."""
    initial = Decimal("1000000.00")
    ledger = StaggeredTrancheLedger(initial, num_tranches=4)
    assert ledger.num_tranches == 4
    assert len(ledger.tranches) == 4
    for t_id in range(4):
        tranche = ledger.tranches[t_id]
        assert isinstance(tranche, Tranche)
        assert tranche.tranche_id == t_id
        assert tranche.allocation_capital == Decimal("250000.00")
        assert tranche.cash == Decimal("250000.00")
        assert len(tranche.positions) == 0


def test_ledger_initialization_custom_tranches() -> None:
    """Verify ledger supports custom number of tranches with proportional capital."""
    initial = Decimal("600000.00")
    ledger = StaggeredTrancheLedger(initial, num_tranches=3)
    assert ledger.num_tranches == 3
    assert len(ledger.tranches) == 3
    for t_id in range(3):
        assert ledger.tranches[t_id].allocation_capital == Decimal("200000.00")
        assert ledger.tranches[t_id].cash == Decimal("200000.00")


def test_ledger_initialization_invalid_parameters_fail_closed() -> None:
    """Verify non-positive initial capital or invalid tranche count raises ValueError."""
    with pytest.raises(ValueError, match="strictly positive"):
        StaggeredTrancheLedger(Decimal("0.00"))

    with pytest.raises(ValueError, match="strictly positive"):
        StaggeredTrancheLedger(Decimal("-5000.00"))

    with pytest.raises(ValueError, match="num_tranches must be >= 1"):
        StaggeredTrancheLedger(Decimal("100000.00"), num_tranches=0)


def test_cash_isolation_between_tranches() -> None:
    """Verify trades in one tranche strictly do not affect cash or positions of other tranches."""
    ledger = StaggeredTrancheLedger(Decimal("1000000.00"), num_tranches=4)
    prices = {"RELIANCE": Decimal("2500.00")}

    res = ledger.rebalance_tranche(
        tranche_id=0,
        decision_date=date(2024, 1, 5),
        execution_date=date(2024, 1, 8),
        selected_symbols=["RELIANCE"],
        open_prices=prices,
    )
    assert res.tranche_id == 0
    assert ledger.tranches[0].cash < Decimal("250000.00")
    assert "RELIANCE" in ledger.tranches[0].positions

    # Tranches 1, 2, 3 must remain untouched with full cash and zero positions
    for t_id in [1, 2, 3]:
        assert ledger.tranches[t_id].cash == Decimal("250000.00")
        assert len(ledger.tranches[t_id].positions) == 0


# =================================================================================================
# 2. Next-Open (T+1) Execution Pricing & Timing
# =================================================================================================


def test_next_open_execution_fill_price() -> None:
    """Verify fill price is the next-open execution price, not decision close price."""
    ledger = StaggeredTrancheLedger(Decimal("100000.00"), num_tranches=4)
    open_prices = {"INFY": Decimal("1500.00")}

    res = ledger.rebalance_tranche(
        tranche_id=0,
        decision_date=date(2024, 3, 1),
        execution_date=date(2024, 3, 4),
        selected_symbols=["INFY"],
        open_prices=open_prices,
    )
    assert res.bought_symbols == ["INFY"]
    pos = ledger.tranches[0].positions["INFY"]
    assert isinstance(pos, TranchePosition)
    assert pos.entry_price == Decimal("1500.00")
    assert pos.current_price == Decimal("1500.00")
    assert pos.entry_date == date(2024, 3, 4)


def test_rebalance_rejection_when_execution_precedes_decision() -> None:
    """Verify execution date strictly cannot precede decision date (fail-closed lookahead guard)."""
    ledger = StaggeredTrancheLedger(Decimal("100000.00"))
    with pytest.raises(ValueError, match="cannot precede decision date"):
        ledger.rebalance_tranche(
            tranche_id=0,
            decision_date=date(2024, 3, 5),
            execution_date=date(2024, 3, 4),
            selected_symbols=["INFY"],
            open_prices={"INFY": Decimal("1500.00")},
        )


def test_invalid_tranche_id_raises_key_error() -> None:
    """Verify rebalancing a non-existent tranche ID raises KeyError."""
    ledger = StaggeredTrancheLedger(Decimal("100000.00"), num_tranches=4)
    with pytest.raises(KeyError, match="Invalid tranche ID"):
        ledger.rebalance_tranche(
            tranche_id=99,
            decision_date=date(2024, 3, 1),
            execution_date=date(2024, 3, 4),
            selected_symbols=["INFY"],
            open_prices={"INFY": Decimal("1500.00")},
        )


# =================================================================================================
# 3. Exact 0.224% Statutory Fee Model Accounting
# =================================================================================================


def test_statutory_fee_constants() -> None:
    """Verify FEE_ONE_WAY is 11.2 bps and FEE_ROUND_TRIP is 22.4 bps."""
    assert StaggeredTrancheLedger.FEE_ONE_WAY == Decimal("0.00112")
    assert StaggeredTrancheLedger.FEE_ROUND_TRIP == Decimal("0.00224")


def test_fee_entry_accounting_identity() -> None:
    """Verify entry fee is deducted atomically and cash reconciles exactly."""
    initial = Decimal("100000.00")
    ledger = StaggeredTrancheLedger(initial, num_tranches=4)
    tranche_cap = ledger.tranches[0].cash
    assert tranche_cap == Decimal("25000.00")

    p_open = Decimal("200.00")
    ledger.rebalance_tranche(
        tranche_id=0,
        decision_date=date(2024, 1, 5),
        execution_date=date(2024, 1, 8),
        selected_symbols=["TCS"],
        open_prices={"TCS": p_open},
    )

    t0 = ledger.tranches[0]
    pos = t0.positions["TCS"]
    cost = pos.quantity * p_open
    expected_fee = (cost * Decimal("0.00112")).quantize(Decimal("0.01"))

    assert ledger.total_statutory_fees() == expected_fee
    assert t0.cash + cost + expected_fee == tranche_cap


def test_fee_round_trip_reconciliation() -> None:
    """Verify round-trip transaction incurs both entry and exit statutory fees."""
    ledger = StaggeredTrancheLedger(Decimal("100000.00"), num_tranches=4)

    # Entry
    res_entry = ledger.rebalance_tranche(
        tranche_id=0,
        decision_date=date(2024, 1, 5),
        execution_date=date(2024, 1, 8),
        selected_symbols=["TCS"],
        open_prices={"TCS": Decimal("100.00")},
    )
    entry_fee = res_entry.statutory_fees
    assert entry_fee > Decimal("0.00")

    # Exit at same price
    res_exit = ledger.rebalance_tranche(
        tranche_id=0,
        decision_date=date(2024, 2, 5),
        execution_date=date(2024, 2, 6),
        selected_symbols=[],
        open_prices={"TCS": Decimal("100.00")},
    )
    exit_fee = res_exit.statutory_fees
    assert exit_fee > Decimal("0.00")

    assert ledger.total_statutory_fees() == entry_fee + exit_fee
    # Both legs at 100.00 with identical quantity produce equal fees
    assert entry_fee == exit_fee


# =================================================================================================
# 4. Circuit-Lock Protections
# =================================================================================================


def test_circuit_lock_entry_zero_volume_skipped() -> None:
    """Verify candidate stock with volume == 0 is skipped on entry."""
    ledger = StaggeredTrancheLedger(Decimal("100000.00"), num_tranches=4)
    prices = {"FROZEN": Decimal("100.00"), "LIQUID": Decimal("100.00")}
    volumes = {"FROZEN": 0, "LIQUID": 25000}

    res = ledger.rebalance_tranche(
        tranche_id=0,
        decision_date=date(2024, 1, 5),
        execution_date=date(2024, 1, 8),
        selected_symbols=["FROZEN", "LIQUID"],
        open_prices=prices,
        volumes=volumes,
    )
    assert "FROZEN" not in res.bought_symbols
    assert "LIQUID" in res.bought_symbols
    assert "FROZEN" not in ledger.tranches[0].positions
    assert "LIQUID" in ledger.tranches[0].positions


def test_circuit_lock_entry_high_equals_low_skipped() -> None:
    """Verify candidate stock locked at limit (high == low) is skipped on entry."""
    ledger = StaggeredTrancheLedger(Decimal("100000.00"), num_tranches=4)
    prices = {"UP_LOCKED": Decimal("100.00"), "NORMAL": Decimal("100.00")}
    highs = {"UP_LOCKED": Decimal("100.00"), "NORMAL": Decimal("105.00")}
    lows = {"UP_LOCKED": Decimal("100.00"), "NORMAL": Decimal("95.00")}

    res = ledger.rebalance_tranche(
        tranche_id=0,
        decision_date=date(2024, 1, 5),
        execution_date=date(2024, 1, 8),
        selected_symbols=["UP_LOCKED", "NORMAL"],
        open_prices=prices,
        highs=highs,
        lows=lows,
    )
    assert "UP_LOCKED" not in res.bought_symbols
    assert "NORMAL" in res.bought_symbols


def test_circuit_lock_exit_zero_volume_carried_over() -> None:
    """Verify position locked on exit (volume == 0) is carried over and not sold."""
    ledger = StaggeredTrancheLedger(Decimal("100000.00"), num_tranches=4)
    ledger.rebalance_tranche(
        tranche_id=0,
        decision_date=date(2024, 1, 5),
        execution_date=date(2024, 1, 8),
        selected_symbols=["LOCK_SYM"],
        open_prices={"LOCK_SYM": Decimal("100.00")},
    )
    assert "LOCK_SYM" in ledger.tranches[0].positions

    # Exit session: volume == 0
    res_exit = ledger.rebalance_tranche(
        tranche_id=0,
        decision_date=date(2024, 2, 5),
        execution_date=date(2024, 2, 6),
        selected_symbols=[],
        open_prices={"LOCK_SYM": Decimal("100.00")},
        volumes={"LOCK_SYM": 0},
    )
    assert "LOCK_SYM" not in res_exit.sold_symbols
    assert "LOCK_SYM" in ledger.tranches[0].positions


def test_circuit_lock_exit_high_equals_low_carried_over() -> None:
    """Verify position locked at lower limit (high == low) is carried over and not sold."""
    ledger = StaggeredTrancheLedger(Decimal("100000.00"), num_tranches=4)
    ledger.rebalance_tranche(
        tranche_id=0,
        decision_date=date(2024, 1, 5),
        execution_date=date(2024, 1, 8),
        selected_symbols=["LOCK_DOWN"],
        open_prices={"LOCK_DOWN": Decimal("100.00")},
    )
    assert "LOCK_DOWN" in ledger.tranches[0].positions

    # Exit session: high == low
    res_exit = ledger.rebalance_tranche(
        tranche_id=0,
        decision_date=date(2024, 2, 5),
        execution_date=date(2024, 2, 6),
        selected_symbols=[],
        open_prices={"LOCK_DOWN": Decimal("80.00")},
        highs={"LOCK_DOWN": Decimal("80.00")},
        lows={"LOCK_DOWN": Decimal("80.00")},
    )
    assert "LOCK_DOWN" not in res_exit.sold_symbols
    assert "LOCK_DOWN" in ledger.tranches[0].positions


# =================================================================================================
# 5. Capital Preservation & Leverage Invariant Proof
# =================================================================================================


def test_leverage_invariant_strictly_le_one_nominal() -> None:
    """Verify total exposure is strictly <= 1.0000 across all 4 tranches."""
    ledger = StaggeredTrancheLedger(Decimal("1000000.00"), num_tranches=4)
    prices = {f"STOCK_{i}": Decimal("100.00") for i in range(12)}

    for t_id in range(4):
        picks = [f"STOCK_{t_id * 3 + j}" for j in range(3)]
        ledger.rebalance_tranche(
            tranche_id=t_id,
            decision_date=date(2024, 1, 5),
            execution_date=date(2024, 1, 8),
            selected_symbols=picks,
            open_prices=prices,
        )

    nav = ledger.mark_to_market(date(2024, 1, 8), prices)
    assert nav.total_exposure <= Decimal("1.0000")
    assert ledger.total_exposure() <= Decimal("1.0000")


def test_leverage_invariant_under_extreme_price_surge() -> None:
    """Verify extreme price increase (+300%) maintains exposure <= 1.0000."""
    ledger = StaggeredTrancheLedger(Decimal("100000.00"), num_tranches=4)
    ledger.rebalance_tranche(
        tranche_id=0,
        decision_date=date(2024, 1, 5),
        execution_date=date(2024, 1, 8),
        selected_symbols=["SURGE"],
        open_prices={"SURGE": Decimal("50.00")},
    )
    # Price surges to 200.00
    nav = ledger.mark_to_market(date(2024, 1, 15), {"SURGE": Decimal("200.00")})
    assert nav.total_nav > Decimal("100000.00")
    assert nav.total_exposure <= Decimal("1.0000")


def test_leverage_invariant_under_extreme_price_crash() -> None:
    """Verify extreme price decrease (-90%) maintains exposure <= 1.0000."""
    ledger = StaggeredTrancheLedger(Decimal("100000.00"), num_tranches=4)
    ledger.rebalance_tranche(
        tranche_id=0,
        decision_date=date(2024, 1, 5),
        execution_date=date(2024, 1, 8),
        selected_symbols=["CRASH"],
        open_prices={"CRASH": Decimal("100.00")},
    )
    # Price crashes to 10.00
    nav = ledger.mark_to_market(date(2024, 1, 15), {"CRASH": Decimal("10.00")})
    assert nav.total_nav < Decimal("100000.00")
    assert nav.total_exposure <= Decimal("1.0000")


def test_leverage_with_all_cash() -> None:
    """Verify 100% cash portfolio has exposure exactly equal to 0.0000."""
    ledger = StaggeredTrancheLedger(Decimal("500000.00"), num_tranches=4)
    nav = ledger.mark_to_market(date(2024, 1, 1), {})
    assert nav.total_exposure == Decimal("0.0000")
    assert nav.positions_value == Decimal("0.00")
    assert nav.cash == Decimal("500000.00")
    assert nav.total_nav == Decimal("500000.00")


# =================================================================================================
# 6. Mark-to-Market NAV Calculation & Reconciliation
# =================================================================================================


def test_mark_to_market_accounting_identity() -> None:
    """Verify total_nav == cash + positions_value always holds exactly."""
    ledger = StaggeredTrancheLedger(Decimal("400000.00"), num_tranches=4)
    prices = {"SYM_A": Decimal("50.00"), "SYM_B": Decimal("150.00")}

    ledger.rebalance_tranche(0, date(2024, 1, 5), date(2024, 1, 8), ["SYM_A"], prices)
    ledger.rebalance_tranche(1, date(2024, 1, 12), date(2024, 1, 15), ["SYM_B"], prices)

    eval_prices = {"SYM_A": Decimal("55.00"), "SYM_B": Decimal("140.00")}
    nav = ledger.mark_to_market(date(2024, 1, 20), eval_prices)

    assert isinstance(nav, LedgerNAV)
    assert nav.total_nav == nav.cash + nav.positions_value
    assert nav.total_exposure == nav.positions_value / nav.total_nav


def test_mark_to_market_missing_price_fallback() -> None:
    """Verify mark_to_market falls back to current/entry price when price is missing."""
    ledger = StaggeredTrancheLedger(Decimal("100000.00"), num_tranches=4)
    ledger.rebalance_tranche(
        0,
        date(2024, 1, 5),
        date(2024, 1, 8),
        ["SYM_X"],
        {"SYM_X": Decimal("75.00")},
    )
    # Evaluate with empty price dictionary
    nav = ledger.mark_to_market(date(2024, 1, 10), {})
    pos = ledger.tranches[0].positions["SYM_X"]
    expected_pos_val = pos.quantity * Decimal("75.00")
    assert nav.positions_value == expected_pos_val


# =================================================================================================
# 7. Top Quintile Selection Helper
# =================================================================================================


def test_select_top_quintile_nominal_20_percent() -> None:
    """Verify top quintile of 100 names is exactly 20 names."""
    names = [f"SYM_{i:03d}" for i in range(100)]
    selected = select_top_quintile(names, top_fraction=0.20)
    assert len(selected) == 20
    assert selected == names[:20]


def test_select_top_quintile_liquid_universe_scaling() -> None:
    """Verify top 20% of 423 names yields exactly 84 names."""
    names = [f"STOCK_{i}" for i in range(423)]
    selected = select_top_quintile(names, top_fraction=0.20)
    assert len(selected) == 84


def test_select_top_quintile_custom_fraction() -> None:
    """Verify custom top fraction (e.g. 15%) selects expected count."""
    names = [f"SYM_{i}" for i in range(100)]
    selected = select_top_quintile(names, top_fraction=0.15)
    assert len(selected) == 15


def test_select_top_quintile_with_ranked_symbol_objects() -> None:
    """Verify select_top_quintile correctly extracts symbol strings from RankedSymbol objects."""
    ranked = [
        RankedSymbol(
            symbol=f"SYM_{i}",
            rank=i + 1,
            score=100.0 - i,
            components=FactorComponents(0.0, 0.0, 0.0, 100.0 - i),
        )
        for i in range(50)
    ]
    selected = select_top_quintile(ranked, top_fraction=0.20)
    assert len(selected) == 10
    assert selected == [f"SYM_{i}" for i in range(10)]


def test_select_top_quintile_invalid_fraction_raises() -> None:
    """Verify invalid top_fraction (<= 0 or > 1) raises ValueError."""
    with pytest.raises(ValueError, match="top_fraction must be in"):
        select_top_quintile(["A", "B"], top_fraction=0.0)

    with pytest.raises(ValueError, match="top_fraction must be in"):
        select_top_quintile(["A", "B"], top_fraction=1.5)


def test_select_top_quintile_empty_input() -> None:
    """Verify empty input returns empty list."""
    assert select_top_quintile([]) == []


# =================================================================================================
# 8. Integer Share Rounding & Unaffordable Price Boundaries
# =================================================================================================


def test_integer_share_rounding_strict() -> None:
    """Verify quantities are strictly integers and fractional shares are not created."""
    ledger = StaggeredTrancheLedger(Decimal("100000.00"), num_tranches=4)
    # 25,000 cash per tranche / 3 names = 8,333.33 per name
    # Price 777.77 -> 8333.33 // (777.77 * 1.00112) = 10 shares
    prices = {"SYM_A": Decimal("777.77"), "SYM_B": Decimal("333.33"), "SYM_C": Decimal("111.11")}
    res = ledger.rebalance_tranche(
        0,
        date(2024, 1, 5),
        date(2024, 1, 8),
        list(prices.keys()),
        prices,
    )
    for sym in res.bought_symbols:
        qty = ledger.tranches[0].positions[sym].quantity
        assert isinstance(qty, int)
        assert qty > 0


def test_unaffordable_stock_skipped_safely() -> None:
    """Verify stock whose price exceeds available capital per stock results in 0 shares and leaves cash intact."""
    ledger = StaggeredTrancheLedger(Decimal("100000.00"), num_tranches=4)
    # Available cash per stock = 25,000 / 2 = 12,500
    # MRF price = 130,000 > 12,500
    prices = {"MRF": Decimal("130000.00"), "AFFORDABLE": Decimal("100.00")}
    res = ledger.rebalance_tranche(
        0,
        date(2024, 1, 5),
        date(2024, 1, 8),
        ["MRF", "AFFORDABLE"],
        prices,
    )
    assert "MRF" not in res.bought_symbols
    assert "AFFORDABLE" in res.bought_symbols


def test_zero_or_negative_price_skipped_safely() -> None:
    """Verify symbols with zero or negative open prices are skipped."""
    ledger = StaggeredTrancheLedger(Decimal("100000.00"), num_tranches=4)
    prices = {"ZERO_P": Decimal("0.00"), "NEG_P": Decimal("-10.00"), "VALID": Decimal("100.00")}
    res = ledger.rebalance_tranche(
        0,
        date(2024, 1, 5),
        date(2024, 1, 8),
        ["ZERO_P", "NEG_P", "VALID"],
        prices,
    )
    assert "ZERO_P" not in res.bought_symbols
    assert "NEG_P" not in res.bought_symbols
    assert "VALID" in res.bought_symbols


# =================================================================================================
# 9. Multi-Cycle Staggered Rolling & Exact Paisa Ledger Reconciliation
# =================================================================================================


def test_staggered_weekly_multi_cycle_rolling() -> None:
    """Verify 4 tranches roll across multiple weekly rebalance cycles with complete cash reconciliation."""
    ledger = StaggeredTrancheLedger(Decimal("1000000.00"), num_tranches=4)
    universe = [f"NAME_{i:02d}" for i in range(40)]
    prices = {s: Decimal("100.00") for s in universe}

    cur_date = date(2024, 1, 5)
    for cycle in range(8):
        t_id = cycle % 4
        dec_date = cur_date
        exec_date = cur_date + timedelta(days=3)
        picks = universe[cycle * 4 : cycle * 4 + 8]

        res = ledger.rebalance_tranche(t_id, dec_date, exec_date, picks, prices)
        assert isinstance(res, TrancheRebalanceResult)
        assert res.tranche_id == t_id
        assert res.statutory_fees >= Decimal("0.00")

        nav = ledger.mark_to_market(exec_date, prices)
        assert nav.total_exposure <= Decimal("1.0000")
        assert nav.total_nav == nav.cash + nav.positions_value

        cur_date += timedelta(days=7)

    assert ledger.total_statutory_fees() > Decimal("0.00")


# =================================================================================================
# 10. Edge-Case Refinements & Regression Tests (M2 Iteration 2)
# =================================================================================================


def test_circuit_lock_empty_highs_lows_dicts_never_locks_symbols() -> None:
    """Verify empty highs={} and lows={} dicts do NOT evaluate None == None as circuit locked."""
    ledger = StaggeredTrancheLedger(Decimal("100000.00"), num_tranches=4)

    # 1. Entry with empty highs/lows dicts: candidate must be bought
    res_entry = ledger.rebalance_tranche(
        tranche_id=0,
        decision_date=date(2024, 1, 1),
        execution_date=date(2024, 1, 2),
        selected_symbols=["INFY"],
        open_prices={"INFY": Decimal("100.00")},
        highs={},
        lows={},
    )
    assert "INFY" in res_entry.bought_symbols
    assert "INFY" in ledger.tranches[0].positions

    # 2. Exit with empty highs/lows dicts: position must be cleanly liquidated, not locked
    res_exit = ledger.rebalance_tranche(
        tranche_id=0,
        decision_date=date(2024, 1, 20),
        execution_date=date(2024, 1, 21),
        selected_symbols=[],
        open_prices={"INFY": Decimal("105.00")},
        highs={},
        lows={},
    )
    assert "INFY" in res_exit.sold_symbols
    assert "INFY" not in ledger.tranches[0].positions
    assert res_exit.new_cash > Decimal("25000.00")


def test_circuit_lock_partial_highs_lows_dicts_behavior() -> None:
    """Verify missing keys in partial highs/lows dicts do not lock omitted symbols."""
    ledger = StaggeredTrancheLedger(Decimal("100000.00"), num_tranches=4)
    prices = {
        "LOCKED": Decimal("100.00"),
        "NOT_IN_DICTS": Decimal("100.00"),
        "HIGH_ONLY": Decimal("100.00"),
        "LOW_ONLY": Decimal("100.00"),
    }
    highs = {"LOCKED": Decimal("100.00"), "HIGH_ONLY": Decimal("100.00")}
    lows = {"LOCKED": Decimal("100.00"), "LOW_ONLY": Decimal("100.00")}

    res = ledger.rebalance_tranche(
        tranche_id=0,
        decision_date=date(2024, 1, 1),
        execution_date=date(2024, 1, 2),
        selected_symbols=["LOCKED", "NOT_IN_DICTS", "HIGH_ONLY", "LOW_ONLY"],
        open_prices=prices,
        highs=highs,
        lows=lows,
    )
    # LOCKED has high == low, so it is locked
    assert "LOCKED" not in res.bought_symbols
    # NOT_IN_DICTS, HIGH_ONLY, LOW_ONLY do not have both high and low matching, so they are bought
    assert "NOT_IN_DICTS" in res.bought_symbols
    assert "HIGH_ONLY" in res.bought_symbols
    assert "LOW_ONLY" in res.bought_symbols


def test_rebalance_duplicate_symbols_preserves_cash_and_single_allocation() -> None:
    """Verify duplicate symbols in selected_symbols are deduplicated without destroying cash."""
    ledger = StaggeredTrancheLedger(Decimal("100000.00"), num_tranches=4)
    # Tranche 0 capital is 25,000.00
    res = ledger.rebalance_tranche(
        tranche_id=0,
        decision_date=date(2024, 1, 1),
        execution_date=date(2024, 1, 2),
        selected_symbols=["INFY", "INFY", "INFY"],
        open_prices={"INFY": Decimal("100.00")},
    )
    assert res.bought_symbols == ["INFY"]
    pos = ledger.tranches[0].positions["INFY"]
    # 25000 // (100.00 * 1.00112) = 25000 // 100.112 = 249 shares
    assert pos.quantity == 249
    cost = Decimal("249") * Decimal("100.00")
    fee = (cost * StaggeredTrancheLedger.FEE_ONE_WAY).quantize(Decimal("0.01"))
    assert res.new_cash == Decimal("25000.00") - cost - fee
    assert ledger.tranches[0].cash == res.new_cash

    # Mark to market should preserve full NAV (only friction deducted)
    nav = ledger.mark_to_market(date(2024, 1, 2), {"INFY": Decimal("100.00")})
    assert nav.total_nav == Decimal("100000.00") - fee


def test_rebalance_non_positive_exit_prices_safely_held_as_locked() -> None:
    """Verify positions with non-positive exit prices (<= 0.00) are not liquidated and cash is not reduced."""
    ledger = StaggeredTrancheLedger(Decimal("100000.00"), num_tranches=4)

    # 1. Establish initial position
    ledger.rebalance_tranche(
        tranche_id=0,
        decision_date=date(2024, 1, 1),
        execution_date=date(2024, 1, 2),
        selected_symbols=["SYM_A"],
        open_prices={"SYM_A": Decimal("100.00")},
    )
    initial_cash = ledger.tranches[0].cash
    assert "SYM_A" in ledger.tranches[0].positions

    # 2. Rebalance with open_price == 0.00
    res_zero = ledger.rebalance_tranche(
        tranche_id=0,
        decision_date=date(2024, 1, 10),
        execution_date=date(2024, 1, 11),
        selected_symbols=[],
        open_prices={"SYM_A": Decimal("0.00")},
    )
    assert "SYM_A" not in res_zero.sold_symbols
    assert "SYM_A" in ledger.tranches[0].positions
    assert ledger.tranches[0].cash == initial_cash

    # 3. Rebalance with negative open_price == -50.00
    res_neg = ledger.rebalance_tranche(
        tranche_id=0,
        decision_date=date(2024, 1, 20),
        execution_date=date(2024, 1, 21),
        selected_symbols=[],
        open_prices={"SYM_A": Decimal("-50.00")},
    )
    assert "SYM_A" not in res_neg.sold_symbols
    assert "SYM_A" in ledger.tranches[0].positions
    assert ledger.tranches[0].cash == initial_cash
    assert ledger.tranches[0].cash >= Decimal("0.00")


def test_rebalance_lookahead_same_day_execution_rejected() -> None:
    """Verify execution_date == decision_date is strictly rejected with ValueError."""
    ledger = StaggeredTrancheLedger(Decimal("100000.00"), num_tranches=4)
    same_date = date(2024, 5, 10)

    with pytest.raises(ValueError, match="cannot precede decision date"):
        ledger.rebalance_tranche(
            tranche_id=0,
            decision_date=same_date,
            execution_date=same_date,
            selected_symbols=["INFY"],
            open_prices={"INFY": Decimal("1500.00")},
        )
