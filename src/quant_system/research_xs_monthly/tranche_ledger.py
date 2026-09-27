"""Staggered Tranche Portfolio Ledger for Cross-Sectional Monthly Alpha (R2).

Maintains a 4-tranche weekly-rebalanced portfolio ledger with:
1. 4 autonomous weekly tranches, 25% max capital allocation per tranche.
2. 21 trading sessions holding period with 5-session weekly stagger.
3. Top quintile selection (15-20% of universe, ~84 names) ranked by multi-factor engine.
4. Next-open (T+1) execution fill pricing with circuit-lock checks (volume == 0 or high == low).
5. Exact 0.224% round-trip statutory fee model (11.2 bps entry + 11.2 bps exit) in Decimal math.
6. Capital preservation invariant: total portfolio leverage strictly <= 100% (<= 1.0000) at all times.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class TranchePosition:
    """Position held within a specific tranche."""

    symbol: str
    quantity: int
    entry_price: Decimal
    current_price: Decimal
    entry_date: date


@dataclass(frozen=True)
class Tranche:
    """Autonomous sub-portfolio tranche with dedicated capital and holding window."""

    tranche_id: int
    allocation_capital: Decimal
    entry_date: date
    exit_date: date
    positions: dict[str, TranchePosition] = field(default_factory=dict)
    cash: Decimal = Decimal("0.00")


@dataclass(frozen=True)
class TrancheRebalanceResult:
    """Execution and cash accounting outcome of a tranche rebalance."""

    tranche_id: int
    decision_date: date
    execution_date: date
    bought_symbols: list[str]
    sold_symbols: list[str]
    statutory_fees: Decimal
    new_cash: Decimal
    new_exposure: Decimal


@dataclass(frozen=True)
class LedgerNAV:
    """Mark-to-market net asset value and exposure breakdown across all tranches."""

    as_of_date: date
    total_nav: Decimal
    total_exposure: Decimal
    cash: Decimal
    positions_value: Decimal


def select_top_quintile(
    ranked_symbols: Sequence[Any],
    top_fraction: float = 0.20,
) -> list[str]:
    """Select the top quintile of symbols from ranked universe.

    Args:
        ranked_symbols: Sequence of symbols (strings) or objects with a `symbol` attribute.
        top_fraction: Fraction of universe to select (nominal 0.20 for top quintile).

    Returns:
        List of symbol strings selected for investment.
    """
    if not ranked_symbols:
        return []
    if not (0.0 < top_fraction <= 1.0):
        raise ValueError(f"top_fraction must be in (0.0, 1.0], got {top_fraction}")
    k = int(len(ranked_symbols) * top_fraction)
    selected: list[str] = []
    for item in ranked_symbols[:k]:
        if isinstance(item, str):
            selected.append(item)
        elif hasattr(item, "symbol"):
            selected.append(str(item.symbol))
        else:
            selected.append(str(item))
    return selected


class StaggeredTrancheLedger:
    """Staggered Tranche Portfolio Ledger enforcing R2 portfolio invariants.

    Invariants:
    - 4 autonomous sub-ledgers (staggered weekly, rebalanced every 5 sessions, held 21 sessions).
    - 25% max capital per tranche (1 / num_tranches).
    - Cash balance >= 0 at all times; no margin or borrowed capital.
    - Leverage strictly <= 1.0000 across all tranches at all times.
    - Next-open (T+1) execution pricing relative to decision date T.
    - Full 0.224% round-trip statutory fee model (11.2 bps entry + 11.2 bps exit).
    - Circuit-locked symbols (volume == 0 or high == low) skipped on entry and carried over on exit.
    """

    FEE_ONE_WAY: Decimal = Decimal("0.00112")
    FEE_ROUND_TRIP: Decimal = Decimal("0.00224")

    def __init__(self, initial_capital: Decimal, num_tranches: int = 4) -> None:
        if initial_capital <= Decimal("0.00"):
            raise ValueError(f"Initial capital must be strictly positive, got {initial_capital}")
        if num_tranches <= 0:
            raise ValueError(f"num_tranches must be >= 1, got {num_tranches}")

        self.initial_capital = initial_capital
        self.num_tranches = num_tranches
        self.tranche_capital = (initial_capital / Decimal(num_tranches)).quantize(Decimal("0.01"))
        self.tranches: dict[int, Tranche] = {}

        for t_id in range(num_tranches):
            self.tranches[t_id] = Tranche(
                tranche_id=t_id,
                allocation_capital=self.tranche_capital,
                entry_date=date(1970, 1, 1),
                exit_date=date(1970, 1, 1),
                positions={},
                cash=self.tranche_capital,
            )

        self._total_statutory_fees: Decimal = Decimal("0.00")

    def rebalance_tranche(
        self,
        tranche_id: int,
        decision_date: date,
        execution_date: date,
        selected_symbols: list[str],
        open_prices: dict[str, Decimal],
        volumes: dict[str, int] | None = None,
        highs: dict[str, Decimal] | None = None,
        lows: dict[str, Decimal] | None = None,
    ) -> TrancheRebalanceResult:
        """Rebalance a specific tranche on execution_date (T+1) based on decision_date (T).

        1. Liquidates non-locked existing positions at open_prices[sym] deducting FEE_ONE_WAY.
        2. Filters candidate symbols for circuit locks (volume == 0 or high == low).
        3. Buys eligible symbols equal-weighted with available cash, deducting FEE_ONE_WAY.
        4. Updates tranche state atomically, guaranteeing cash >= 0 and leverage <= 1.0000.
        """
        if tranche_id not in self.tranches:
            raise KeyError(f"Invalid tranche ID {tranche_id}")
        if execution_date <= decision_date:
            raise ValueError(
                f"Execution date {execution_date} cannot precede decision date {decision_date}"
            )

        selected_symbols = list(dict.fromkeys(selected_symbols))

        tranche = self.tranches[tranche_id]
        sold_symbols: list[str] = []
        bought_symbols: list[str] = []
        new_positions: dict[str, TranchePosition] = dict(tranche.positions)
        cash = tranche.cash
        period_fees = Decimal("0.00")

        # 1. Liquidate existing positions
        for sym, pos in list(tranche.positions.items()):
            is_locked = False
            if volumes is not None and volumes.get(sym, 1) == 0:
                is_locked = True
            if highs is not None and lows is not None:
                h_price = highs.get(sym)
                l_price = lows.get(sym)
                if h_price is not None and l_price is not None and h_price == l_price:
                    is_locked = True

            if is_locked:
                # Carry over locked position rather than forcibly liquidating
                continue

            if sym in open_prices:
                p_exit = open_prices[sym]
                if p_exit <= Decimal("0.00"):
                    continue
                proceeds = pos.quantity * p_exit
                fee = (proceeds * self.FEE_ONE_WAY).quantize(Decimal("0.01"))
                cash += proceeds - fee
                period_fees += fee
                sold_symbols.append(sym)
                del new_positions[sym]

        # 2. Filter candidate buys for circuit locks on entry
        eligible_buys: list[str] = []
        for sym in selected_symbols:
            if sym not in open_prices:
                continue
            if open_prices[sym] <= Decimal("0.00"):
                continue
            if volumes is not None and volumes.get(sym, 1) == 0:
                continue
            if highs is not None and lows is not None:
                h_price = highs.get(sym)
                l_price = lows.get(sym)
                if h_price is not None and l_price is not None and h_price == l_price:
                    continue
            eligible_buys.append(sym)

        # 3. Buy eligible new positions (equal-weight within available cash)
        if eligible_buys and cash > Decimal("0.00"):
            capital_per_stock = cash / Decimal(len(eligible_buys))
            for sym in eligible_buys:
                p_open = open_prices[sym]
                if p_open <= Decimal("0.00"):
                    continue
                effective_price = p_open * (Decimal("1.0") + self.FEE_ONE_WAY)
                qty = int(capital_per_stock // effective_price)
                if qty > 0:
                    cost = qty * p_open
                    fee = (cost * self.FEE_ONE_WAY).quantize(Decimal("0.01"))
                    if cash >= (cost + fee):
                        cash -= cost + fee
                        period_fees += fee
                        new_positions[sym] = TranchePosition(
                            symbol=sym,
                            quantity=qty,
                            entry_price=p_open,
                            current_price=p_open,
                            entry_date=execution_date,
                        )
                        bought_symbols.append(sym)

        self._total_statutory_fees += period_fees
        pos_val = sum(
            (
                pos.quantity * open_prices.get(s, pos.entry_price)
                for s, pos in new_positions.items()
            ),
            start=Decimal("0.00"),
        )
        tot_val = cash + pos_val
        exposure = pos_val / tot_val if tot_val > Decimal("0.00") else Decimal("0.00")

        self.tranches[tranche_id] = Tranche(
            tranche_id=tranche_id,
            allocation_capital=tranche.allocation_capital,
            entry_date=execution_date,
            exit_date=execution_date + timedelta(days=30),
            positions=new_positions,
            cash=cash,
        )

        return TrancheRebalanceResult(
            tranche_id=tranche_id,
            decision_date=decision_date,
            execution_date=execution_date,
            bought_symbols=bought_symbols,
            sold_symbols=sold_symbols,
            statutory_fees=period_fees,
            new_cash=cash,
            new_exposure=exposure,
        )

    def mark_to_market(self, as_of_date: date, current_prices: dict[str, Decimal]) -> LedgerNAV:
        """Mark all tranches to market at current prices and return consolidated NAV.

        Guarantees total exposure <= 1.0000.
        """
        total_cash = Decimal("0.00")
        total_pos_val = Decimal("0.00")

        for tranche in self.tranches.values():
            total_cash += tranche.cash
            for sym, pos in tranche.positions.items():
                p = current_prices.get(sym, pos.current_price)
                total_pos_val += pos.quantity * p

        nav = total_cash + total_pos_val
        exp = total_pos_val / nav if nav > Decimal("0.00") else Decimal("0.00")

        if exp > Decimal("1.0000"):
            raise ValueError(
                f"Leverage invariant violation: total exposure {exp} exceeds 1.0000 ceiling"
            )

        return LedgerNAV(
            as_of_date=as_of_date,
            total_nav=nav,
            total_exposure=exp,
            cash=total_cash,
            positions_value=total_pos_val,
        )

    def total_exposure(self) -> Decimal:
        """Return aggregate portfolio exposure across all tranches."""
        nav = self.mark_to_market(date(2000, 1, 1), {})
        return nav.total_exposure

    def total_statutory_fees(self) -> Decimal:
        """Return cumulative statutory fees incurred across all tranche transactions."""
        return self._total_statutory_fees


__all__ = [
    "LedgerNAV",
    "StaggeredTrancheLedger",
    "Tranche",
    "TranchePosition",
    "TrancheRebalanceResult",
    "select_top_quintile",
]
