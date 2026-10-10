"""Portfolio valuation for manually entered holdings, and a read-only view of the paper books."""

from __future__ import annotations

import json
from bisect import bisect_left, bisect_right
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from quant_system.core.domain import Side
from quant_system.lab.costs import BrokerCharges, RetailCostModel
from quant_system.lab.simulator import to_decimal
from quant_system.market.index import BENCHMARK_SYMBOL, BarSeries, MarketIndex, SymbolNotFoundError
from quant_system.server.v2.holding_periods import holding_period
from quant_system.server.v2.state import Holding

CONCENTRATION_LIMIT = 0.25
PAPER_LABEL = "Market plus costs. Not evidence that the model has skill."


def _close_on_or_before(series: BarSeries, day: str) -> tuple[str, float] | None:
    i = bisect_right(series.dates, day) - 1
    return (series.dates[i], float(series.close[i])) if i >= 0 else None


def _close_on_or_after(series: BarSeries, day: str) -> tuple[str, float] | None:
    i = bisect_left(series.dates, day)
    return (series.dates[i], float(series.close[i])) if i < len(series.dates) else None


def portfolio_summary(
    index: MarketIndex, holdings: list[Holding], broker: BrokerCharges, today: date
) -> dict[str, Any]:
    model = RetailCostModel(broker)
    try:
        bench: BarSeries | None = index.bars(BENCHMARK_SYMBOL)
    except SymbolNotFoundError:
        bench = None
    compare_on = bench.dates[-1] if bench is not None and bench.dates else None

    rows: list[dict[str, Any]] = []
    for holding in holdings:
        row: dict[str, Any] = {
            "id": holding.id,
            "account_id": holding.account_id,
            "symbol": holding.symbol,
            "quantity": holding.quantity,
            "avg_price": float(holding.avg_price),
            "buy_date": holding.buy_date,
            "note": holding.note,
            "cost": float(holding.avg_price * holding.quantity),
            "lot": holding_period(holding.buy_date, today),
        }
        try:
            info = index.symbol_info(holding.symbol)
            series = index.bars(holding.symbol)
        except SymbolNotFoundError:
            row["error"] = "Not in the market data"
            rows.append(row)
            continue
        snap = info["snapshot"] or {}
        close = float(snap.get("close") or 0.0)
        prev = snap.get("prev_close")
        value = close * holding.quantity
        exit_charges = (
            model.charges(Side.SELL, holding.quantity, to_decimal(close), today).total
            if close
            else Decimal("0")
        )
        row.update(
            {
                "name": info["name"],
                "asof": snap.get("asof"),
                "close": close,
                "value": value,
                "pnl": value - row["cost"],
                "pnl_pct": value / row["cost"] - 1.0 if row["cost"] else None,
                "day_change": (close - float(prev)) * holding.quantity if prev else None,
                "exit_charges": float(exit_charges),
            }
        )
        row["vs_nifty"] = _vs_nifty(series, bench, holding, compare_on)
        rows.append(row)

    valued = [r for r in rows if "value" in r]
    total_value = sum(r["value"] for r in valued)
    total_cost = sum(r["cost"] for r in valued)
    for r in valued:
        r["weight"] = r["value"] / total_value if total_value else 0.0
    compared = [r["vs_nifty"] for r in valued if r.get("vs_nifty")]
    return {
        "holdings": rows,
        "totals": {
            "value": total_value,
            "cost": total_cost,
            "pnl": total_value - total_cost,
            "pnl_pct": total_value / total_cost - 1.0 if total_cost else None,
            "day_change": sum(r["day_change"] or 0.0 for r in valued),
            "exit_charges": sum(r["exit_charges"] for r in valued),
        },
        "warnings": [
            f"{r['symbol']} is {r['weight']:.0%} of your portfolio (above {CONCENTRATION_LIMIT:.0%})."
            for r in valued
            if r["weight"] > CONCENTRATION_LIMIT
        ],
        "nifty": (
            {
                "compare_on": compare_on,
                "holdings_value": sum(c["holding_value"] for c in compared),
                "nifty_value": sum(c["nifty_value"] for c in compared),
                "count": len(compared),
            }
            if compared
            else None
        ),
    }


def _vs_nifty(
    series: BarSeries, bench: BarSeries | None, holding: Holding, compare_on: str | None
) -> dict[str, Any] | None:
    """Same money in NIFTYBEES on the buy date, both valued on the last date NIFTY data covers."""
    if bench is None or compare_on is None or holding.buy_date > compare_on:
        return None
    bought = _close_on_or_after(bench, holding.buy_date)
    bench_end = _close_on_or_before(bench, compare_on)
    stock_end = _close_on_or_before(series, compare_on)
    if bought is None or bench_end is None or stock_end is None or stock_end[0] < holding.buy_date:
        return None
    cost = float(holding.avg_price) * holding.quantity
    return {
        "holding_value": stock_end[1] * holding.quantity,
        "nifty_value": cost * bench_end[1] / bought[1],
        "compare_on": compare_on,
    }


def paper_books(workspace: Path | None, index: MarketIndex | None) -> list[dict[str, Any]]:
    """Read-only summaries of the running paper books. Never starts, stops or edits a book."""
    if workspace is None:
        return []
    books: list[dict[str, Any]] = []
    xs = workspace / "logs" / "xs_monthly_new" / "paper_watch" / "state.json"
    if xs.is_file():
        books.append(_xs_book(xs, index))
    flagship = workspace / "logs" / "paper_runs" / "live_paper_status.json"
    if flagship.is_file():
        books.append(_flagship_book(flagship))
    elif (workspace / "logs" / "paper_runs").is_dir():
        books.append(
            {
                "id": "flagship",
                "name": "Mizan flagship",
                "status": "WAITING",
                "message": "No flagship session has completed since the books restarted.",
                "label": PAPER_LABEL,
            }
        )
    return books


def _xs_book(path: Path, index: MarketIndex | None) -> dict[str, Any]:
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as err:
        return {
            "id": "xs-monthly",
            "name": "XS-Monthly",
            "status": "UNREADABLE",
            "message": str(err),
            "label": PAPER_LABEL,
        }
    capital = float(state.get("capital") or 0)
    cash = float(state.get("cash") or 0)
    positions: list[dict[str, Any]] = []
    marked_on: set[str] = set()
    for pos in state.get("open") or []:
        symbol = str(pos.get("symbol"))
        shares = int(pos.get("shares") or 0)
        entry_value = float(pos.get("entry_value") or 0)
        mark = float(pos.get("market_value") or entry_value)
        asof = str(pos.get("asof_date") or pos.get("entry_date") or "")
        if index is not None:
            try:
                snap = index.symbol_info(symbol)["snapshot"] or {}
                if snap.get("asof") and str(snap["asof"]) >= str(pos.get("entry_date") or ""):
                    mark = float(snap["close"]) * shares
                    asof = str(snap["asof"])
            except SymbolNotFoundError:
                pass
        marked_on.add(asof)
        positions.append(
            {
                "symbol": symbol,
                "shares": shares,
                "entry_date": pos.get("entry_date"),
                "entry_value": entry_value,
                "market_value": mark,
                "unrealized": mark - entry_value,
                "asof": asof,
            }
        )
    equity = cash + sum(p["market_value"] for p in positions)
    positions.sort(key=lambda p: p["market_value"], reverse=True)
    entries = [str(p["entry_date"]) for p in positions if p["entry_date"]]
    return {
        "id": "xs-monthly",
        "name": "XS-Monthly (cross-sectional)",
        "status": "RUNNING",
        "capital": capital,
        "cash": cash,
        "equity": equity,
        "return": equity / capital - 1.0 if capital else None,
        "started": min(entries) if entries else None,
        "asof": max(marked_on) if marked_on else None,
        "position_count": len(positions),
        "positions": positions[:15],
        "closed_count": len(state.get("closed") or []),
        "unresolved_count": len(state.get("unresolved") or []),
        "label": PAPER_LABEL,
    }


def _flagship_book(path: Path) -> dict[str, Any]:
    try:
        status = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as err:
        return {
            "id": "flagship",
            "name": "Mizan flagship",
            "status": "UNREADABLE",
            "message": str(err),
            "label": PAPER_LABEL,
        }

    def num(key: str) -> float | None:
        try:
            return float(status[key])
        except (KeyError, TypeError, ValueError):
            return None

    capital = num("initial_cash")
    equity = num("total_equity")
    return {
        "id": "flagship",
        "name": "Mizan flagship",
        "status": str(status.get("status") or "UNKNOWN"),
        "capital": capital,
        "cash": num("cash"),
        "equity": equity,
        "return": (equity / capital - 1.0) if capital and equity is not None else None,
        "net_pnl": num("net_pnl"),
        "fees": num("total_fees_paid"),
        "position_count": status.get("open_positions"),
        "asof": status.get("timestamp_ist"),
        "model": status.get("model_name"),
        "halt_reason": status.get("halt_reason") or status.get("abort_reason"),
        "label": PAPER_LABEL,
    }
