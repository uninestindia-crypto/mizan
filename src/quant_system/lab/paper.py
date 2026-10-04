"""Paper books: a Strategy Lab rule followed forward in time with virtual money.

A paper book is a saved lab specification plus a start session. Its state is never stored as a
running total; it is *replayed*: the same deterministic simulator the lab uses is run from the start
session to the latest session in the market data. That is what live paper trading would have done,
because the simulator already decides at a close using only past prices and fills at the next
session's open, with the same dated NSE charges and slippage. There is no second engine to disagree
with the lab.

* The book starts at the latest session in the data when it is created. Its first decision uses
  prices up to that close; its first fills are the next session's real opens.
* Orders decided at the latest close are returned as ``queued``: tomorrow's orders.
* A book can be stopped (frozen at a session) but never deleted, for the same reason lab runs are
  never deleted: failures must stay visible.
* A stock the book touched that had a demerger or rights issue inside the window cannot be valued,
  and the book says so rather than guessing.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Literal

from quant_system.lab.costs import COSTS_COVERED_FROM, BrokerCharges, RetailCostModel
from quant_system.lab.runner import (
    UNIVERSES,
    LabError,
    LabRequest,
    _panel,
    _resolve_symbols,
)
from quant_system.lab.simulator import SimConfig, simulate
from quant_system.lab.stats import performance
from quant_system.lab.strategies import BuyAndHold, build_strategy, warmup_sessions
from quant_system.lab.templates import get_template
from quant_system.market.index import BENCHMARK_SYMBOL, MarketIndex, SymbolNotFoundError

MAX_TRADES_SHOWN = 500
# Under this many sessions a paper book says plainly that it cannot show skill yet.
EARLY_SESSIONS = 60


@dataclass(frozen=True, slots=True)
class PaperSpec:
    template_id: str
    params: dict[str, Any]
    scope: Literal["stocks", "universe"]
    symbols: tuple[str, ...]
    universe: str | None
    capital: Decimal
    slippage_bps: Decimal
    start_session: str  # the first decision is taken at this session's close
    stop_session: str | None = None  # frozen here when the book was stopped


def latest_session(index: MarketIndex) -> str:
    """The newest session the market data holds (NIFTYBEES is the reference series)."""
    try:
        return str(index.symbol_info(BENCHMARK_SYMBOL)["last_date"])
    except SymbolNotFoundError as err:
        raise LabError("The NIFTYBEES benchmark is missing from the market data.") from err


def evaluate_book(
    index: MarketIndex, spec: PaperSpec, broker: BrokerCharges | None = None
) -> dict[str, Any]:
    """Replay the book from its start session to the latest (or stop) session."""
    try:
        template = get_template(spec.template_id)
        params = template.resolve(spec.params)
    except ValueError as err:
        raise LabError(str(err)) from err
    request = LabRequest(
        spec.template_id, params, spec.scope, spec.symbols, spec.universe, None, None
    )
    symbols = _resolve_symbols(index, request)
    last = latest_session(index)
    end = min(spec.stop_session or last, last)
    start = date.fromisoformat(spec.start_session)
    if start < COSTS_COVERED_FROM:
        raise LabError(
            f"Exact NSE charges are only defined from {COSTS_COVERED_FROM:%d %b %Y}, so a paper "
            "book cannot start earlier."
        )
    if date.fromisoformat(end) < start:
        raise LabError("The market data ends before this book's start session.")

    warm = warmup_sessions(template.id, params)
    load_from = start - timedelta(days=int(warm * 1.6) + 40)
    series = index.bars_many([*symbols, BENCHMARK_SYMBOL], start=load_from.isoformat(), end=end)
    bench = series.get(BENCHMARK_SYMBOL)
    if bench is None or not bench.dates:
        raise LabError("NIFTYBEES has no prices for this book.")
    tradable = [s for s in symbols if s in series]
    if not tradable:
        raise LabError("None of this book's stocks has prices in the market data.")

    dates = sorted({d for s in [*tradable, BENCHMARK_SYMBOL] for d in series[s].dates})
    first_trade = next((i for i, d in enumerate(dates) if d >= spec.start_session), None)
    if first_trade is None:
        raise LabError("The market data has no session on or after this book's start.")
    panel = _panel(dates, {s: series[s] for s in tradable})
    bench_panel = _panel(dates, {BENCHMARK_SYMBOL: bench})

    fee_model = RetailCostModel(broker)
    config = SimConfig(capital=spec.capital, slippage_bps=spec.slippage_bps)
    result = simulate(
        panel,
        build_strategy(template.id, params, first_trade),
        first_trade,
        fee_model.fee,
        config,
        queue_last=True,
    )
    bench_result = simulate(
        bench_panel, BuyAndHold(first_trade), first_trade, fee_model.fee, config
    )
    perf = performance(result)
    bench_perf = performance(bench_result)

    sessions = len(result.dates) - 1
    touched = (
        {f.symbol for f in result.fills}
        | {p.symbol for p in result.open_positions}
        | {q.symbol for q in result.queued}
    )
    attention: list[str] = []
    breaks = index.breaking_actions(sorted(touched), spec.start_session, end) if touched else {}
    for symbol, events in sorted(breaks.items()):
        attention.append(
            f"{symbol} had a {events[0]['subject'].lower()} on {events[0]['ex_date']}. "
            "What one share represents changed and its size is not published, so this book's "
            "value cannot be trusted from that date. Stop the book and start a new one."
        )
    flagged = index.flags_in_window(sorted(touched), spec.start_session, end) if touched else {}
    for symbol, events in sorted(flagged.items()):
        attention.append(
            f"{symbol}'s price data has a break on {events[0]['d']}: {events[0]['note']} "
            "The book's value includes that jump."
        )

    last_close = {p.symbol: float(p.last_close) for p in result.open_positions}
    equity_now = float(result.equity[-1])
    positions = [
        {
            "symbol": p.symbol,
            "quantity": p.quantity,
            "average_price": float(p.average_price),
            "last_close": float(p.last_close),
            "market_value": float(p.last_close) * p.quantity,
            "unrealized_pnl": float(p.unrealized_pnl),
            "weight": (float(p.last_close) * p.quantity) / equity_now if equity_now else 0.0,
        }
        for p in sorted(result.open_positions, key=lambda x: -float(x.last_close) * x.quantity)
    ]
    invested = float(result.invested[-1])
    stopped = spec.stop_session is not None
    if stopped:
        status = "STOPPED"
    elif sessions < 1 and not result.fills:
        status = "WAITING"
    else:
        status = "RUNNING"
    if attention and not stopped:
        status = "ATTENTION"

    return {
        "status": status,
        "template": {"id": template.id, "name": template.name, "summary": template.summary},
        "params": params,
        "scope": {
            "kind": spec.scope,
            "symbols": list(spec.symbols) if spec.scope == "stocks" else None,
            "universe": spec.universe,
            "universe_label": UNIVERSES.get(spec.universe or "", None),
            "used": len(tradable),
        },
        "capital": float(spec.capital),
        "slippage_bps": float(spec.slippage_bps),
        "start_session": spec.start_session,
        "last_session": result.dates[-1],
        "stop_session": spec.stop_session,
        "sessions": sessions,
        "equity": equity_now,
        "cash": equity_now - invested,
        "return": perf.total_return,
        "benchmark_return": bench_perf.total_return,
        "excess": perf.total_return - bench_perf.total_return,
        "charges": perf.charges,
        "slippage": perf.slippage,
        "positions": positions,
        "queued": [
            {
                "side": q.side,
                "symbol": q.symbol,
                "quantity": q.quantity,
                "reference_price": float(q.reference_price) if q.reference_price else None,
            }
            for q in sorted(result.queued, key=lambda x: (x.side, x.symbol))
        ],
        "trades": [
            {
                "date": f.date,
                "symbol": f.symbol,
                "side": f.side,
                "quantity": f.quantity,
                "price": float(f.price),
                "fee": float(f.fee),
                "slippage": float(f.slippage),
            }
            for f in reversed(result.fills[-MAX_TRADES_SHOWN:])
        ],
        "curve": [
            [d, float(e), float(b)]
            for d, e, b in zip(result.dates, result.equity, bench_result.equity, strict=True)
        ],
        "session_equity": {d: float(e) for d, e in zip(result.dates, result.equity, strict=True)},
        "round_trips": perf.round_trips,
        "win_rate": perf.win_rate,
        "max_drawdown": perf.max_drawdown,
        "attention": attention,
        "skipped": result.skipped[-20:],
        "reading": _reading(sessions, perf.total_return - bench_perf.total_return),
        "marks": last_close,
    }


def _reading(sessions: int, excess: float) -> dict[str, str]:
    """What these numbers can and cannot say, in plain words."""
    if sessions < EARLY_SESSIONS:
        return {
            "level": "TOO_EARLY",
            "title": "Too early to tell",
            "body": (
                f"{sessions} trading session{'s' if sessions != 1 else ''} so far. A few weeks of "
                "results are mostly what the market did, minus charges. They cannot show that a "
                "rule has skill."
            ),
        }
    side = "ahead of" if excess > 0 else "behind"
    return {
        "level": "SOME_HISTORY",
        "title": "Some history, still not proof",
        "body": (
            f"{sessions} sessions so far, {abs(excess) * 100:,.1f} percentage points {side} simply "
            "holding NIFTY. That is one stretch of market. Judge a rule over a year or more, and "
            "against how many ideas you tried."
        ),
    }
