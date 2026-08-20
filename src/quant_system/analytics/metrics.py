"""Quantitative performance metrics (Sharpe, Sortino, Calmar, Max Drawdown, CAGR)."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from quant_system.core.domain import Fill, PortfolioSnapshot, Side


@dataclass(frozen=True, slots=True)
class QuantStats:
    total_return_pct: float
    cagr_pct: float
    annualized_volatility: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    max_drawdown_pct: float
    max_drawdown_duration_bars: int
    win_rate: float
    profit_factor: float
    total_trades: int
    avg_trade_pnl: float


class PerformanceMetrics:
    """Calculates risk-adjusted returns and drawdown diagnostics."""

    @classmethod
    def calculate(
        cls,
        equity_curve: Sequence[PortfolioSnapshot],
        fills: Sequence[Fill],
        risk_free_rate: float = 0.07,
        periods_per_year: int = 252,
    ) -> QuantStats:
        if len(equity_curve) < 2:
            return QuantStats(
                total_return_pct=0.0,
                cagr_pct=0.0,
                annualized_volatility=0.0,
                sharpe_ratio=0.0,
                sortino_ratio=0.0,
                calmar_ratio=0.0,
                max_drawdown_pct=0.0,
                max_drawdown_duration_bars=0,
                win_rate=0.0,
                profit_factor=0.0,
                total_trades=0,
                avg_trade_pnl=0.0,
            )

        equities = [float(s.total_equity) for s in equity_curve]
        initial_eq = equities[0]
        final_eq = equities[-1]

        # Total Return
        total_ret = (final_eq - initial_eq) / initial_eq

        # Daily Returns
        daily_returns = [
            (equities[i] - equities[i - 1]) / equities[i - 1] for i in range(1, len(equities))
        ]

        # CAGR
        years = len(daily_returns) / periods_per_year
        cagr = (
            ((final_eq / initial_eq) ** (1.0 / max(1e-4, years))) - 1.0 if years > 0 else total_ret
        )

        # Volatility
        mean_ret = sum(daily_returns) / len(daily_returns)
        var = sum((r - mean_ret) ** 2 for r in daily_returns) / max(1, len(daily_returns) - 1)
        daily_vol = math.sqrt(var)
        ann_vol = daily_vol * math.sqrt(periods_per_year)

        # Sharpe Ratio
        rf_daily = risk_free_rate / periods_per_year
        excess_mean = mean_ret - rf_daily
        sharpe = (
            (excess_mean / daily_vol) * math.sqrt(periods_per_year) if daily_vol > 1e-8 else 0.0
        )

        # Sortino Ratio (Downside deviation only)
        downside_diffs = [min(0.0, r - rf_daily) ** 2 for r in daily_returns]
        downside_dev = math.sqrt(sum(downside_diffs) / max(1, len(downside_diffs)))
        sortino = (
            (excess_mean / downside_dev) * math.sqrt(periods_per_year)
            if downside_dev > 1e-8
            else 0.0
        )

        # Max Drawdown & Duration
        max_dd = 0.0
        peak = equities[0]
        curr_dd_dur = 0
        max_dd_dur = 0

        for eq in equities:
            if eq > peak:
                peak = eq
                curr_dd_dur = 0
            else:
                dd = (peak - eq) / peak
                if dd > max_dd:
                    max_dd = dd
                curr_dd_dur += 1
                if curr_dd_dur > max_dd_dur:
                    max_dd_dur = curr_dd_dur

        # Calmar Ratio
        calmar = (cagr / max_dd) if max_dd > 1e-6 else 0.0

        # Trade-level metrics (Paired Buy & Sell)
        win_rate, profit_factor, avg_trade_pnl = cls._calculate_trade_stats(fills)

        return QuantStats(
            total_return_pct=total_ret,
            cagr_pct=cagr,
            annualized_volatility=ann_vol,
            sharpe_ratio=sharpe,
            sortino_ratio=sortino,
            calmar_ratio=calmar,
            max_drawdown_pct=max_dd,
            max_drawdown_duration_bars=max_dd_dur,
            win_rate=win_rate,
            profit_factor=profit_factor,
            total_trades=len(fills),
            avg_trade_pnl=avg_trade_pnl,
        )

    @staticmethod
    def _calculate_trade_stats(fills: Sequence[Fill]) -> tuple[float, float, float]:
        """Calculates closed-trade statistics using exact FIFO matching for both Long and Short positions."""
        if not fills:
            return 0.0, 0.0, 0.0

        pnl_list: list[float] = []
        open_lots: dict[str, list[dict[str, Any]]] = {}

        for fill in fills:
            symbol = fill.symbol
            lots = open_lots.setdefault(symbol, [])

            if not lots or lots[0]["side"] == fill.side:
                fee_per_unit = fill.fee / Decimal(fill.quantity)
                lots.append(
                    {
                        "quantity": fill.quantity,
                        "price": fill.price,
                        "fee_per_unit": fee_per_unit,
                        "side": fill.side,
                    }
                )
            else:
                # Opposite side fill closes open positions
                qty_needed = fill.quantity
                fill_fee_per_unit = fill.fee / Decimal(fill.quantity)

                while qty_needed > 0 and lots and lots[0]["side"] != fill.side:
                    lot = lots[0]
                    matched_qty = min(qty_needed, int(lot["quantity"]))

                    if lot["side"] == Side.BUY:
                        # Closing LONG with SELL
                        entry_val = lot["price"] * Decimal(matched_qty)
                        entry_fee = lot["fee_per_unit"] * Decimal(matched_qty)
                        exit_val = fill.price * Decimal(matched_qty)
                        exit_fee = fill_fee_per_unit * Decimal(matched_qty)
                        pnl = float(exit_val - entry_val - entry_fee - exit_fee)
                    else:
                        # Closing SHORT with BUY
                        entry_val = lot["price"] * Decimal(matched_qty)
                        entry_fee = lot["fee_per_unit"] * Decimal(matched_qty)
                        exit_val = fill.price * Decimal(matched_qty)
                        exit_fee = fill_fee_per_unit * Decimal(matched_qty)
                        pnl = float(entry_val - exit_val - entry_fee - exit_fee)

                    pnl_list.append(pnl)
                    lot["quantity"] -= matched_qty
                    qty_needed -= matched_qty

                    if lot["quantity"] == 0:
                        lots.pop(0)

                # If fill had excess quantity, open new lot
                if qty_needed > 0:
                    lots.append(
                        {
                            "quantity": qty_needed,
                            "price": fill.price,
                            "fee_per_unit": fill_fee_per_unit,
                            "side": fill.side,
                        }
                    )

        if not pnl_list:
            return 0.0, 0.0, 0.0

        wins = sum(1 for p in pnl_list if p > 0)
        gross_profits = sum(p for p in pnl_list if p > 0)
        gross_losses = sum(abs(p) for p in pnl_list if p < 0)

        win_rate = wins / len(pnl_list)
        profit_factor = (
            (gross_profits / gross_losses)
            if gross_losses > 0
            else (999.0 if gross_profits > 0 else 0.0)
        )
        avg_trade_pnl = sum(pnl_list) / len(pnl_list)

        return win_rate, profit_factor, avg_trade_pnl
