"""Forward paper watch for the FROZEN XS-monthly rule (new stack, research only).

Frozen rule (identical constants to ``screen.py`` — tuning here is forbidden):
  score = trailing 21-session close momentum → top 20% → next-open entry →
  hold 21 sessions → exit at open, net of 0.224% round trip.

This module places no orders, imports no broker, no execution/paper path, no
server. It only computes signals from cached bars and tracks hypothetical
open/closed legs in a JSON state file the runner owns. Stdlib + bars/screen.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, localcontext
from typing import Final

from quant_system.research_xs_monthly.bars import Bar
from quant_system.research_xs_monthly.screen import (
    COST_RATIO,
    FORMATION_SESSIONS,
    HOLD_SESSIONS,
    TOP_FRAC,
    WARMUP_SESSIONS,
    ScreenError,
    _index_symbol,
    build_calendar,
    formation_score,
    forward_net,
)

FROZEN_RULE: Final = {
    "formation_sessions": FORMATION_SESSIONS,
    "hold_sessions": HOLD_SESSIONS,
    "top_frac": str(TOP_FRAC),
    "cost_ratio": str(COST_RATIO),
}

#: Separate notional book for the XS-monthly watch. Display-only accounting:
#: no orders, no shared ledger, no touch on paper_pilot/paper_portfolio.
NOTIONAL_CAPITAL_INR: Final = Decimal("1000000")


def size_positions(
    holdings: list[dict],
    capital: Decimal = NOTIONAL_CAPITAL_INR,
) -> tuple[list[dict], Decimal]:
    """Split capital equally across holdings into integer shares (NSE cash has
    no fractional shares). Returns (legs, cash_leftover)."""
    if not holdings:
        raise ScreenError("INSUFFICIENT_DATA: no holdings to size")
    if capital <= 0:
        raise ScreenError("BAD_PARAM: capital must be positive")
    per_leg = capital / Decimal(len(holdings))
    legs: list[dict] = []
    used = Decimal(0)
    for h in holdings:
        entry = Decimal(str(h["entry_open"]))
        shares = int(per_leg // entry)
        value = Decimal(shares) * entry
        used += value
        legs.append(
            {
                "symbol": h["symbol"],
                "entry_date": h["entry_date"],
                "entry_open": str(entry),
                "shares": shares,
                "entry_value": str(value),
            }
        )
    return legs, capital - used


def _book_closed(pos: dict, exit_bar_open: Decimal) -> dict:
    """Cash fields for a closed leg. Cost = full round trip on entry notional,
    charged exactly once — same 0.224% model as the screen."""
    shares = int(pos.get("shares", 0))
    entry_open = Decimal(str(pos["entry_open"]))
    entry_value = Decimal(str(pos.get("entry_value", Decimal(shares) * entry_open)))
    with localcontext() as ctx:
        ctx.prec = 28
        exit_value = Decimal(shares) * exit_bar_open
        cost = COST_RATIO * entry_value
        proceeds = exit_value - cost
        net_cash = proceeds - entry_value
    return {
        "shares": shares,
        "entry_value": str(entry_value),
        "exit_open": str(exit_bar_open),
        "exit_value": str(exit_value),
        "cost": str(cost),
        "proceeds": str(proceeds),
        "net_cash": str(net_cash),
    }


def _book_open(pos: dict, latest_open: Decimal) -> dict:
    shares = int(pos.get("shares", 0))
    entry_value = Decimal(str(pos.get("entry_value", "0")))
    with localcontext() as ctx:
        ctx.prec = 28
        market_value = Decimal(shares) * latest_open
        unrealized = market_value - entry_value
    return {
        "shares": shares,
        "entry_value": str(entry_value),
        "market_value": str(market_value),
        "unrealized": str(unrealized),
    }


def latest_signal(
    bars_by_symbol: dict[str, list[Bar]],
    top_frac: Decimal = TOP_FRAC,
) -> dict:
    """Compute the latest complete rebalance signal.

    Decision date = last calendar session with a following session available
    for next-open entry. Holdings carry entry opens; locked entries are
    skipped and counted, never filled at a locked price.
    """
    if not bars_by_symbol:
        raise ScreenError("INSUFFICIENT_DATA: empty universe")
    calendar = build_calendar(bars_by_symbol)
    decision_pos = len(calendar) - 2  # entry open must exist at +1
    if decision_pos < WARMUP_SESSIONS - 1:
        raise ScreenError("INSUFFICIENT_DATA: no complete decision slot yet")
    indexed = {symbol: _index_symbol(bars) for symbol, bars in bars_by_symbol.items()}
    scored: list[tuple[str, Decimal]] = []
    for symbol, idx in indexed.items():
        score = formation_score(idx, calendar, decision_pos)
        if score is not None:
            scored.append((symbol, score))
    if not scored:
        raise ScreenError("INSUFFICIENT_DATA: no scored names at latest decision")
    scored.sort(key=lambda item: item[1], reverse=True)
    width = max(1, int(Decimal(len(scored)) * top_frac))
    entry_pos = decision_pos + 1
    holdings: list[dict] = []
    skipped_locked = 0
    skipped_missing = 0
    for symbol, score in scored[:width]:
        bar = indexed[symbol].get(calendar[entry_pos])
        if bar is None:
            skipped_missing += 1
            continue
        if bar.volume == 0 or bar.high == bar.low:
            skipped_locked += 1
            continue
        holdings.append(
            {
                "symbol": symbol,
                "score": str(score),
                "entry_date": calendar[entry_pos].isoformat(),
                "entry_open": str(bar.open),
            }
        )
    return {
        "rule": FROZEN_RULE,
        "decision_date": calendar[decision_pos].isoformat(),
        "entry_date": calendar[entry_pos].isoformat(),
        "calendar_end": calendar[-1].isoformat(),
        "scored_names": len(scored),
        "holdings": holdings,
        "skipped_locked": skipped_locked,
        "skipped_missing": skipped_missing,
    }


def settle_positions(
    positions: list[dict],
    bars_by_symbol: dict[str, list[Bar]],
    hold: int = HOLD_SESSIONS,
) -> dict:
    """Split positions into closed legs vs open marks at the latest bar.

    Closed leg: exit open exists hold sessions after entry → full COST_RATIO
    charged exactly once. Open leg: marked gross at the latest available open,
    cost pending, never deducted early.
    """
    calendar = build_calendar(bars_by_symbol)
    indexed = {symbol: _index_symbol(bars) for symbol, bars in bars_by_symbol.items()}
    pos_of = {d: i for i, d in enumerate(calendar)}
    closed: list[dict] = []
    opened: list[dict] = []
    for pos in positions:
        symbol = pos["symbol"]
        entry_open = Decimal(str(pos["entry_open"]))
        entry_date = date.fromisoformat(str(pos["entry_date"]))
        idx = indexed.get(symbol, {})
        if entry_date not in pos_of:
            continue
        exit_pos = pos_of[entry_date] + hold
        if exit_pos < len(calendar):
            net, locked = forward_net(idx, calendar, pos_of[entry_date], exit_pos)
            if net is None:
                if locked:
                    continue  # locked exit: leg stays pending, never forced
                continue
            leg = {
                "symbol": symbol,
                "entry_date": pos["entry_date"],
                "exit_date": calendar[exit_pos].isoformat(),
                "entry_open": str(entry_open),
                "net": str(net),
            }
            if "shares" in pos:
                exit_bar = idx.get(calendar[exit_pos])
                if exit_bar is not None:
                    leg.update(_book_closed(pos, exit_bar.open))
            closed.append(leg)
        else:
            latest_bar = idx.get(calendar[-1])
            if latest_bar is None or entry_open <= 0:
                continue
            with localcontext() as ctx:
                ctx.prec = 28
                gross = (latest_bar.open - entry_open) / entry_open
            leg = {
                "symbol": symbol,
                "entry_date": pos["entry_date"],
                "entry_open": str(entry_open),
                "asof_date": calendar[-1].isoformat(),
                "gross_mark": str(gross),
                "cost_pending": str(COST_RATIO),
            }
            if "shares" in pos:
                leg.update(_book_open(pos, latest_bar.open))
            opened.append(leg)
    return {"closed": closed, "open": opened, "asof": calendar[-1].isoformat()}
