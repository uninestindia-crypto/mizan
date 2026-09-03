"""Tests for the XS-monthly forward paper watch (new stack only)."""

from __future__ import annotations

import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quant_system.research_xs_monthly.bars import Bar
from quant_system.research_xs_monthly.paper import (
    NOTIONAL_CAPITAL_INR,
    latest_signal,
    settle_positions,
    size_positions,
)
from quant_system.research_xs_monthly.screen import COST_RATIO, ScreenError


def _bars(symbol: str, closes: list[str], start: str = "2020-01-01") -> list[Bar]:
    base = date.fromisoformat(start)
    return [
        Bar(
            symbol=symbol,
            exchange_date=base + timedelta(days=i),
            open=Decimal(c),
            high=Decimal(c) + Decimal("1"),
            low=Decimal("0.5"),
            close=Decimal(c),
            volume=1_000_000,
        )
        for i, c in enumerate(closes)
    ]


def _universe() -> dict[str, list[Bar]]:
    bars = {f"S{k:02d}": _bars(f"S{k:02d}", [str(100 + i) for i in range(90)]) for k in range(5)}
    bars["WIN"] = _bars("WIN", [str(100 + i * 3) for i in range(90)])
    return bars


def test_signal_picks_top_momentum() -> None:
    signal = latest_signal(_universe())
    names = [h["symbol"] for h in signal["holdings"]]
    assert "WIN" in names
    assert signal["rule"]["formation_sessions"] == 21


def test_signal_enters_at_next_open() -> None:
    bars = _universe()
    signal = latest_signal(bars)
    assert signal["entry_date"] > signal["decision_date"]
    win_hold = next(h for h in signal["holdings"] if h["symbol"] == "WIN")
    entry_bar = next(b for b in bars["WIN"] if b.exchange_date.isoformat() == signal["entry_date"])
    assert Decimal(win_hold["entry_open"]) == entry_bar.open


def test_closed_leg_charges_full_cost_once() -> None:
    bars = _universe()
    signal = latest_signal(bars)
    held = [
        {"symbol": h["symbol"], "entry_date": h["entry_date"], "entry_open": h["entry_open"]}
        for h in signal["holdings"]
    ]
    # Extend history 21 sessions past entry so exits exist.
    base = date.fromisoformat("2020-01-01")
    for symbol, blist in bars.items():
        last_close = blist[-1].close
        for j in range(1, 25):
            d = base + timedelta(days=90 + j - 1)
            bars[symbol].append(
                Bar(
                    symbol=symbol,
                    exchange_date=d,
                    open=last_close,
                    high=last_close + Decimal("1"),
                    low=Decimal("0.5"),
                    close=last_close,
                    volume=1_000_000,
                )
            )
    settled = settle_positions(held, bars)
    assert len(settled["closed"]) == len(held)
    assert settled["open"] == []
    # Extended bars are flat at the entry open: gross 0, full cost charged once.
    for leg in settled["closed"]:
        assert Decimal(leg["net"]) == -COST_RATIO


def test_open_leg_marks_gross_with_cost_pending() -> None:
    bars = _universe()
    signal = latest_signal(bars)
    held = [
        {"symbol": h["symbol"], "entry_date": h["entry_date"], "entry_open": h["entry_open"]}
        for h in signal["holdings"]
    ]
    settled = settle_positions(held, bars)  # no exit bars yet: all open
    assert settled["closed"] == []
    assert len(settled["open"]) == len(held)
    for leg in settled["open"]:
        assert "gross_mark" in leg
        assert leg["cost_pending"] == str(COST_RATIO)


def test_locked_entry_skipped() -> None:
    bars = _universe()
    win = bars["WIN"]
    locked = win[-1]
    win[-1] = Bar(
        symbol="WIN",
        exchange_date=locked.exchange_date,
        open=locked.open,
        high=locked.open,
        low=locked.open,
        close=locked.close,
        volume=0,
    )
    signal = latest_signal(bars)
    names = [h["symbol"] for h in signal["holdings"]]
    # WIN is still top-scored on closes but its entry bar is locked: excluded.
    assert "WIN" not in names
    assert signal["skipped_locked"] == 1


def test_fresh_open_carries_settled_shape() -> None:
    bars = _universe()
    signal = latest_signal(bars)
    fresh = [
        {"symbol": h["symbol"], "entry_date": h["entry_date"], "entry_open": h["entry_open"]}
        for h in signal["holdings"]
    ]
    opened = settle_positions(fresh, bars)["open"]
    assert len(opened) == len(fresh)
    for leg in opened:
        assert leg["asof_date"] and leg["gross_mark"] and leg["cost_pending"]


def test_book_splits_capital_into_integer_shares() -> None:
    holdings = [
        {"symbol": "A", "entry_date": "2020-03-30", "entry_open": "100"},
        {"symbol": "B", "entry_date": "2020-03-30", "entry_open": "30"},
    ]
    legs, leftover = size_positions(holdings, Decimal("1000"))
    assert legs[0]["shares"] == 5  # 500 // 100
    assert legs[1]["shares"] == 16  # 500 // 30 floors
    assert leftover == Decimal("1000") - (Decimal(500) + Decimal(480))
    assert sum(Decimal(leg["entry_value"]) for leg in legs) + leftover == Decimal("1000")


def test_book_defaults_to_ten_lakh() -> None:
    assert NOTIONAL_CAPITAL_INR == Decimal("1000000")


def test_book_closed_leg_cash_conserves() -> None:
    bars = _universe()
    signal = latest_signal(bars)
    fresh = [
        {"symbol": h["symbol"], "entry_date": h["entry_date"], "entry_open": h["entry_open"]}
        for h in signal["holdings"]
    ]
    sized, leftover = size_positions(fresh, Decimal("100000"))
    base = date.fromisoformat("2020-01-01")
    for symbol, blist in bars.items():
        last_close = blist[-1].close
        for j in range(1, 25):
            d = base + timedelta(days=90 + j - 1)
            bars[symbol].append(
                Bar(
                    symbol=symbol,
                    exchange_date=d,
                    open=last_close,
                    high=last_close + Decimal("1"),
                    low=Decimal("0.5"),
                    close=last_close,
                    volume=1_000_000,
                )
            )
    settled = settle_positions(sized, bars)
    for leg in settled["closed"]:
        # Flat exits: proceeds = entry_value - cost, net_cash = -cost.
        assert Decimal(leg["proceeds"]) == Decimal(leg["entry_value"]) - Decimal(leg["cost"])
        assert Decimal(leg["net_cash"]) == -Decimal(leg["cost"])
    total_out = leftover + sum(Decimal(leg["proceeds"]) for leg in settled["closed"])
    total_in = sum(Decimal(leg["entry_value"]) for leg in settled["closed"]) + leftover
    assert total_out == total_in - sum(Decimal(leg["cost"]) for leg in settled["closed"])


def test_empty_universe_fails_closed() -> None:
    with pytest.raises(ScreenError, match="INSUFFICIENT_DATA"):
        latest_signal({})


def test_watch_imports_no_money_paths() -> None:
    text = Path("src/quant_system/research_xs_monthly/paper.py").read_text(encoding="utf-8") + Path(
        "scripts/run_xs_monthly_paper_watch.py"
    ).read_text(encoding="utf-8")
    import_lines = [ln for ln in text.splitlines() if ln.lstrip().startswith(("import ", "from "))]
    for forbidden in ("paper_pilot", "paper_portfolio", "risk.governor", "server", "broker"):
        assert not any(forbidden in ln for ln in import_lines), forbidden
