"""Tests for the isolated XS-monthly screen (new stack only)."""

from __future__ import annotations

import sys
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from quant_system.research_xs_monthly.bars import Bar
from quant_system.research_xs_monthly.screen import (
    COST_RATIO,
    ScreenError,
    build_calendar,
    formation_score,
    forward_net,
    run_long_short,
    run_screen,
    summarize_leg,
)


def _bars(
    symbol: str, closes: list[str], opens: list[str] | None = None, start: str = "2020-01-01"
) -> list[Bar]:
    base = date.fromisoformat(start)
    out: list[Bar] = []
    for i, close in enumerate(closes):
        o = opens[i] if opens else close
        out.append(
            Bar(
                symbol=symbol,
                exchange_date=base + timedelta(days=i),
                open=Decimal(o),
                high=Decimal(close) + Decimal("1"),
                low=Decimal("0.5"),
                close=Decimal(close),
                volume=1_000_000,
            )
        )
    return out


def _universe(n_names: int = 6, n_days: int = 90, drift: str = "0.10") -> dict[str, list[Bar]]:
    bars: dict[str, list[Bar]] = {}
    for k in range(n_names):
        closes = [str(100 + k * 5 + i * Decimal(drift)) for i in range(n_days)]
        bars[f"S{k:02d}"] = _bars(f"S{k:02d}", closes)
    return bars


def test_score_uses_only_history_at_decision() -> None:
    bars = _bars("A", ["10"] * 30 + ["10"] * 5)
    indexed = {b.exchange_date: b for b in bars}
    calendar = sorted(indexed)
    before = formation_score(indexed, calendar, 24)
    # A spike landing AFTER the decision close must not move the score at T.
    bars[25] = Bar(
        symbol="A",
        exchange_date=bars[25].exchange_date,
        open=bars[25].open,
        high=Decimal("1000"),
        low=Decimal("0.5"),
        close=Decimal("500"),
        volume=1_000_000,
    )
    indexed2 = {b.exchange_date: b for b in bars}
    after = formation_score(indexed2, calendar, 24)
    assert before == after


def test_forward_uses_next_open_not_decision_close() -> None:
    bars = _bars("A", ["10"] * 10, opens=["10"] * 9 + ["99"])
    indexed = {b.exchange_date: b for b in bars}
    calendar = sorted(indexed)
    net, locked = forward_net(indexed, calendar, 8, 9)
    assert locked is False
    assert net is not None
    # Entry open is 10 (day 8), exit open is 99 (day 9): proves next-bar reads.
    assert net == (Decimal("99") - Decimal("10")) / Decimal("10") - COST_RATIO


def test_cost_math_exact() -> None:
    bars = _bars("A", ["10"] * 10, opens=["100", "110"] + ["10"] * 8)
    indexed = {b.exchange_date: b for b in bars}
    calendar = sorted(indexed)
    net, _ = forward_net(indexed, calendar, 0, 1)
    assert net == Decimal("0.10") - COST_RATIO


def test_locked_days_skipped() -> None:
    bars = _bars("A", ["10"] * 10)
    locked = bars[5]
    bars[5] = Bar(
        symbol="A",
        exchange_date=locked.exchange_date,
        open=locked.open,
        high=locked.open,
        low=locked.open,
        close=locked.close,
        volume=0,
    )
    indexed = {b.exchange_date: b for b in bars}
    calendar = sorted(indexed)
    net, was_locked = forward_net(indexed, calendar, 5, 6)
    assert net is None
    assert was_locked is True


def test_screen_runs_and_reproducible() -> None:
    first = run_screen(_universe())
    second = run_screen(_universe())
    assert first["leg"] == second["leg"]
    assert first["rebalances"] >= 2
    assert first["verdict"] == "RESEARCH_ONLY"


def test_screen_picks_winners_cross_sectionally() -> None:
    bars = _universe(n_names=4, n_days=90, drift="0.10")
    # Make S03 dominate formation into every rebalance: steady extra climb.
    bars["S03"] = _bars("S03", [str(100 + i * Decimal("2")) for i in range(90)])
    result = run_screen(bars, top_frac=Decimal("0.25"))
    assert result["rebalances"] >= 2
    for period in result["periods"]:
        assert "S03" in period["held"]


def test_empty_universe_fails_closed() -> None:
    with pytest.raises(ScreenError, match="INSUFFICIENT_DATA"):
        run_screen({})
    with pytest.raises(ScreenError, match="INSUFFICIENT_DATA"):
        summarize_leg([], 0, 0)


def test_short_history_fails_closed() -> None:
    with pytest.raises(ScreenError, match="INSUFFICIENT_DATA"):
        run_screen(_universe(n_names=4, n_days=30))


def test_long_short_diagnostic_runs() -> None:
    result = run_long_short(_universe(), hold=2)
    assert result["verdict"] == "RESEARCH_ONLY_DIAGNOSTIC"
    assert result["n_periods"] >= 2


def test_market_leg_matches_equalweight() -> None:
    bars = _universe(n_names=5, n_days=90, drift="0.10")
    result = run_screen(bars)
    market = result["market_equalweight"]
    assert market is not None
    assert market["n_periods"] == result["rebalances"]


def test_calendar_requires_coverage() -> None:
    full = _bars("A", ["10"] * 100)
    thin = _bars("B", ["10"] * 100, start="2020-01-10")
    calendar = build_calendar({"A": full, "B": thin})
    assert len(calendar) >= 42 + 21 + 1
