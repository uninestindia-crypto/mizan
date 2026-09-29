"""Run one lab backtest end to end and return a JSON-ready result."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date, timedelta
from decimal import Decimal
from typing import Any, Literal

import numpy as np

from quant_system.lab.costs import COSTS_COVERED_FROM, BrokerCharges, RetailCostModel
from quant_system.lab.simulator import SimConfig, SimResult, simulate
from quant_system.lab.stats import WHOLE_LIST, excess_probability, performance, verdict
from quant_system.lab.strategies import BuyAndHold, Panel, build_strategy, warmup_sessions
from quant_system.lab.templates import get_template
from quant_system.market.index import BENCHMARK_SYMBOL, BarSeries, MarketIndex, SymbolNotFoundError

MAX_STOCKS = 20
MAX_TRADES_RETURNED = 1000
_LIST_NOTIONAL = Decimal("1000000000")
UNIVERSES = {"liquid": "Liquid 423 (10-year, ₹5 cr+/day)", "nifty500": "NIFTY 500"}


class LabError(ValueError):
    """A request the lab refuses, with a message written for the user."""


@dataclass(frozen=True, slots=True)
class LabRequest:
    template_id: str
    params: dict[str, Any] = field(default_factory=dict)
    scope: Literal["stocks", "universe"] = "stocks"
    symbols: tuple[str, ...] = ()
    universe: str | None = None
    start: str | None = None
    end: str | None = None
    capital: Decimal = Decimal("1000000")
    slippage_bps: Decimal = Decimal("5")


def run_lab(
    index: MarketIndex,
    request: LabRequest,
    broker: BrokerCharges | None = None,
    prior_trials: int = 0,
) -> dict[str, Any]:
    try:
        template = get_template(request.template_id)
        params = template.resolve(request.params)
    except ValueError as err:
        raise LabError(str(err)) from err
    if request.scope not in template.scopes:
        raise LabError(f"{template.name} cannot be run on a {request.scope}.")
    if not Decimal("10000") <= request.capital <= Decimal("1000000000"):
        raise LabError("Capital must be between ₹10,000 and ₹100 crore.")

    symbols = _resolve_symbols(index, request)
    try:
        bench_info = index.symbol_info(BENCHMARK_SYMBOL)
    except SymbolNotFoundError as err:
        raise LabError("The NIFTYBEES benchmark is missing from the market data.") from err

    trade_start = max(_parse_date(request.start) or COSTS_COVERED_FROM, COSTS_COVERED_FROM)
    bench_last = date.fromisoformat(str(bench_info["last_date"]))
    end = min(_parse_date(request.end) or bench_last, bench_last)
    if (end - trade_start).days < 30:
        raise LabError(
            f"The test period is too short. Trades can start on {COSTS_COVERED_FROM:%d %b %Y} at the "
            f"earliest and the benchmark data ends on {bench_last:%d %b %Y}."
        )

    notes: list[str] = []
    excluded: list[dict[str, str]] = []
    breaks = index.breaking_actions(symbols, trade_start.isoformat(), end.isoformat())
    if breaks:
        if request.scope == "stocks":
            symbol, events = next(iter(sorted(breaks.items())))
            raise LabError(
                f"{symbol} had a {events[0]['subject'].lower()} on {events[0]['ex_date']}. Its price "
                "history across that date is not comparable, so the lab will not test across it. "
                "Pick a period that ends before or starts after it."
            )
        for symbol, events in sorted(breaks.items()):
            excluded.append(
                {"symbol": symbol, "reason": f"{events[0]['subject']} on {events[0]['ex_date']}"}
            )
        symbols = [s for s in symbols if s not in breaks]

    data_breaks = index.flags_in_window(symbols, trade_start.isoformat(), end.isoformat())
    if data_breaks and request.scope == "stocks":
        symbol, events = next(iter(sorted(data_breaks.items())))
        raise LabError(
            f"{symbol}'s price data has a break on {events[0]['d']}: {events[0]['note']} The lab will "
            "not test across it. Pick a period that ends before or starts after it."
        )

    warm = warmup_sessions(template.id, params)
    load_from = trade_start - timedelta(days=int(warm * 1.6) + 40)
    series = index.bars_many(
        [*symbols, BENCHMARK_SYMBOL], start=load_from.isoformat(), end=end.isoformat()
    )
    bench = series.get(BENCHMARK_SYMBOL)
    if bench is None or not bench.dates:
        raise LabError("NIFTYBEES has no prices in the chosen period.")
    tradable = [
        s
        for s in symbols
        if s in series and any(d >= trade_start.isoformat() for d in series[s].dates)
    ]
    for symbol in symbols:
        if symbol not in tradable:
            excluded.append({"symbol": symbol, "reason": "No prices in the test period"})
    if not tradable:
        raise LabError("None of the chosen stocks has prices in the test period.")
    late = [s for s in tradable if series[s].dates[0] > trade_start.isoformat()]
    if late:
        notes.append(
            f"{len(late)} stock{'s' if len(late) != 1 else ''} started trading after the test began "
            f"and only take part from their listing: {', '.join(late[:8])}{'…' if len(late) > 8 else ''}."
        )

    dates = sorted({d for s in [*tradable, BENCHMARK_SYMBOL] for d in series[s].dates})
    first_trade = next(i for i, d in enumerate(dates) if d >= trade_start.isoformat())
    panel = _panel(dates, {s: series[s] for s in tradable})
    bench_panel = _panel(dates, {BENCHMARK_SYMBOL: bench})

    fee_model = RetailCostModel(broker)
    config = SimConfig(capital=request.capital, slippage_bps=request.slippage_bps)
    strategy_result = simulate(
        panel, build_strategy(template.id, params, first_trade), first_trade, fee_model.fee, config
    )
    bench_result = simulate(
        bench_panel, BuyAndHold(first_trade), first_trade, fee_model.fee, config
    )

    strategy_perf = performance(strategy_result)
    bench_perf = performance(bench_result)
    trials = prior_trials + 1
    sessions = len(strategy_result.dates) - 1
    counts_trades = template.id != "buy_hold"

    list_result: SimResult | None = None
    if request.scope == "universe":
        # Judge stock-picking against owning the same list equally: both share the list's
        # survivorship bias, so the comparison isolates the picking. The list is bought with enough
        # notional money to afford every stock, then scaled to the user's capital.
        at_start = [s for s in tradable if not math.isnan(panel.close[s][first_trade])]
        list_panel = _panel(dates, {s: series[s] for s in at_start})
        list_config = SimConfig(capital=_LIST_NOTIONAL, slippage_bps=request.slippage_bps)
        raw = simulate(list_panel, BuyAndHold(first_trade), first_trade, fee_model.fee, list_config)
        scale = request.capital / _LIST_NOTIONAL
        list_result = SimResult(
            dates=raw.dates,
            equity=[value * scale for value in raw.equity],
            invested=[value * scale for value in raw.invested],
            fills=raw.fills,
        )
        comparison_equity = list_result.equity
        comparison_perf = performance(list_result)
        probability = excess_probability(strategy_result.equity, comparison_equity, trials)
        judgement = verdict(
            strategy_perf,
            comparison_perf,
            probability,
            trials,
            sessions,
            counts_trades,
            against=WHOLE_LIST,
            cap_reason=(
                "But the stock list was chosen with today's knowledge: it only holds companies that "
                "exist and are large now, which flatters any strategy that buys rising stocks. "
                "QuantOS does not call that proof."
            ),
        )
    else:
        probability = excess_probability(strategy_result.equity, bench_result.equity, trials)
        judgement = verdict(strategy_perf, bench_perf, probability, trials, sessions, counts_trades)

    for symbol, events in sorted(data_breaks.items()):
        for event in events:
            if _held_on(strategy_result, symbol, str(event["d"])):
                notes.append(
                    f"{symbol} was held on {event['d']}, when its price data breaks "
                    f"({event['note']}) This test includes that jump."
                )

    broker_used = fee_model.broker
    assumptions = [
        (
            f"Trades start on {dates[first_trade]}. Exact NSE charges are only defined from "
            f"{COSTS_COVERED_FROM:%d %b %Y}, when stamp duty became uniform nationwide."
        ),
        (
            "Decisions are made at a session's close and filled at the next session's open, with "
            f"{request.slippage_bps} basis points of slippage."
        ),
        (
            "Charges: NSE statutory charges in force on each trade date, plus your broker's "
            f"₹{broker_used.delivery_per_order} per order and ₹{broker_used.dp_charge_per_sell} DP "
            "charge per sell (with 18% GST)."
        ),
        "Prices exclude dividends for both the strategy and NIFTYBEES. Income tax on gains is not included.",
        "Benchmark: NIFTYBEES (a NIFTY 50 ETF) bought at the first open and held, with the same charges.",
    ]
    if request.scope == "universe":
        assumptions.append(
            "Survivorship: only companies listed today are in the data. Companies that failed or were "
            "delisted are missing, which makes stock-picking look better than it was."
        )

    return {
        "template": template.as_dict(),
        "params": params,
        "scope": {
            "kind": request.scope,
            "universe": request.universe,
            "universe_label": UNIVERSES.get(request.universe or "", None),
            "requested": list(request.symbols) if request.scope == "stocks" else None,
            "used": len(tradable),
            "symbols": tradable if len(tradable) <= 50 else tradable[:50],
            "excluded": excluded,
        },
        "period": {
            "start": dates[first_trade],
            "end": dates[-1],
            "sessions": sessions,
            "requested_start": request.start,
            "requested_end": request.end,
        },
        "capital": float(request.capital),
        "strategy": strategy_perf.as_dict(),
        "benchmark": bench_perf.as_dict(),
        "comparison": (
            {"label": "Whole list, equal weight", "performance": performance(list_result).as_dict()}
            if list_result is not None
            else None
        ),
        "verdict": judgement.as_dict(),
        "equity": [
            [
                d,
                float(s),
                float(b),
                float(list_result.equity[i]) if list_result is not None else None,
            ]
            for i, (d, s, b) in enumerate(
                zip(strategy_result.dates, strategy_result.equity, bench_result.equity, strict=True)
            )
        ],
        "trades": _trades(strategy_result),
        "open_positions": [
            {
                "symbol": p.symbol,
                "quantity": p.quantity,
                "average_price": float(p.average_price),
                "last_close": float(p.last_close),
                "unrealized_pnl": float(p.unrealized_pnl),
            }
            for p in strategy_result.open_positions
        ],
        "notes": notes + [f"Skipped order: {text}" for text in strategy_result.skipped[:10]],
        "assumptions": assumptions,
    }


def _resolve_symbols(index: MarketIndex, request: LabRequest) -> list[str]:
    if request.scope == "universe":
        if request.universe not in UNIVERSES:
            raise LabError("Choose the Liquid 423 or NIFTY 500 universe.")
        symbols = [s for s in index.universe(request.universe) if s != BENCHMARK_SYMBOL]
        if not symbols:
            raise LabError("That universe has no stocks in the market data.")
        return symbols
    symbols = list(dict.fromkeys(s.strip().upper() for s in request.symbols if s.strip()))
    if not 1 <= len(symbols) <= MAX_STOCKS:
        raise LabError(f"Choose between 1 and {MAX_STOCKS} stocks.")
    for symbol in symbols:
        try:
            index.symbol_info(symbol)
        except SymbolNotFoundError as err:
            raise LabError(f"{symbol} is not in the market data.") from err
    return symbols


def _panel(dates: list[str], series: dict[str, BarSeries]) -> Panel:
    position = {d: i for i, d in enumerate(dates)}
    opens: dict[str, np.ndarray] = {}
    closes: dict[str, np.ndarray] = {}
    for symbol, bars in series.items():
        o = np.full(len(dates), np.nan, dtype=np.float64)
        c = np.full(len(dates), np.nan, dtype=np.float64)
        idx = np.fromiter((position[d] for d in bars.dates), dtype=np.int64, count=len(bars.dates))
        o[idx] = bars.open
        c[idx] = bars.close
        opens[symbol], closes[symbol] = o, c
    return Panel(dates=dates, symbols=sorted(series), open=opens, close=closes)


def _held_on(result: SimResult, symbol: str, day: str) -> bool:
    """Whether the strategy held ``symbol`` over the night before ``day`` (fills are in date order)."""
    quantity = 0
    for fill in result.fills:
        if fill.date >= day:
            break
        if fill.symbol == symbol:
            quantity += fill.quantity if fill.side == "BUY" else -fill.quantity
    return quantity > 0


def _trades(result: SimResult) -> list[dict[str, Any]]:
    trips = result.round_trips[-MAX_TRADES_RETURNED:]
    return [
        {
            "symbol": t.symbol,
            "entry_date": t.entry_date,
            "exit_date": t.exit_date,
            "quantity": t.quantity,
            "entry_price": float(t.entry_price),
            "exit_price": float(t.exit_price),
            "pnl": float(t.pnl),
            "return_pct": t.return_pct if math.isfinite(t.return_pct) else None,
            "sessions": t.sessions,
        }
        for t in trips
    ]


def _parse_date(text: str | None) -> date | None:
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError as err:
        raise LabError(f"{text} is not a valid date (use YYYY-MM-DD).") from err
