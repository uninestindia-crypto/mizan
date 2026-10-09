"""How a person's holdings have moved together: the numbers, what is left out, and what is said when there is not enough.

The covariance is Qlib's Ledoit-Wolf shrinkage estimator (``research/qlib/riskmodel.py``). The tests build price histories with
a known structure (identical, independent, one flat, one short) and check the answers against arithmetic done by hand.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np
import pytest

from quant_system.market.index import BarSeries, SymbolNotFoundError
from quant_system.server.v2.portfolio_risk import (
    MIN_SESSIONS,
    NO_MOVEMENT,
    NOTE,
    RiskHolding,
    portfolio_risk,
    risk_from_quantities,
    risk_summary,
)

START = np.datetime64("2025-01-01")


def dates(count: int, skip: int = 0) -> list[str]:
    days = np.arange(START, START + np.timedelta64(count + skip + 400, "D"))
    business = [str(d) for d in days if np.is_busday(d)]
    return business[skip : skip + count]


def series(symbol: str, closes: np.ndarray, skip: int = 0) -> BarSeries:
    n = len(closes)
    flat = np.zeros(n)
    return BarSeries(symbol, dates(n, skip), flat, flat, flat, closes.astype(float), flat)


def walk(returns: np.ndarray, start: float = 100.0) -> np.ndarray:
    return start * np.concatenate([[1.0], np.cumprod(1.0 + returns)])


@dataclass
class FakeIndex:
    table: dict[str, BarSeries]
    breaks: dict[str, list[dict[str, object]]] = field(default_factory=dict)

    def bars(self, symbol: str, start: str | None = None, end: str | None = None) -> BarSeries:
        if symbol not in self.table:
            raise SymbolNotFoundError(symbol)
        return self.table[symbol]

    def flags_in_window(
        self, symbols: list[str], start: str, end: str
    ) -> dict[str, list[dict[str, object]]]:
        return {
            s: [f for f in self.breaks.get(s, []) if start < str(f["d"]) <= end]
            for s in symbols
            if s in self.breaks
        }


def rng_returns(n: int, seed: int, sigma: float = 0.01) -> np.ndarray:
    return np.random.default_rng(seed).normal(0.0005, sigma, n)


# --------------------------------------------------------------------------------- the numbers


def test_a_single_holding_has_its_own_volatility_and_all_the_risk() -> None:
    r = rng_returns(300, 1)
    index = FakeIndex({"AAA": series("AAA", walk(r))})
    out = portfolio_risk(index, [RiskHolding("AAA", 50_000.0)])
    window = r[-252:]
    assert out["available"] is True
    assert out["volatility_pct"] == pytest.approx(window.std() * math.sqrt(252) * 100, abs=0.01)
    assert out["effective_bets"] == pytest.approx(1.0)
    assert [(h["symbol"], h["money_pct"], h["risk_pct"]) for h in out["holdings"]] == [
        ("AAA", 100.0, 100.0)
    ]


def test_two_identical_holdings_are_one_bet_and_the_volatility_does_not_fall() -> None:
    r = rng_returns(300, 2)
    index = FakeIndex({"AAA": series("AAA", walk(r)), "BBB": series("BBB", walk(r))})
    out = portfolio_risk(index, [RiskHolding("AAA", 1.0), RiskHolding("BBB", 1.0)])
    alone = portfolio_risk(FakeIndex({"AAA": series("AAA", walk(r))}), [RiskHolding("AAA", 1.0)])
    assert out["effective_bets"] == pytest.approx(1.0, abs=0.02)
    assert out["volatility_pct"] == pytest.approx(alone["volatility_pct"], rel=0.02)


def test_many_independent_holdings_behave_like_many_bets_and_the_volatility_falls() -> None:
    table = {f"S{i}": series(f"S{i}", walk(rng_returns(300, 10 + i))) for i in range(6)}
    out = portfolio_risk(FakeIndex(table), [RiskHolding(s, 1000.0) for s in table])
    one = portfolio_risk(FakeIndex({"S0": table["S0"]}), [RiskHolding("S0", 1.0)])
    assert out["effective_bets"] > 4.5
    assert out["volatility_pct"] < one["volatility_pct"] * 0.6
    assert out["diversification"]["holdings"] == 6


def test_money_and_risk_each_add_up_and_the_riskiest_holding_comes_first() -> None:
    calm = series("CALM", walk(rng_returns(300, 3, sigma=0.004)))
    wild = series("WILD", walk(rng_returns(300, 4, sigma=0.03)))
    out = portfolio_risk(
        FakeIndex({"CALM": calm, "WILD": wild}),
        [RiskHolding("CALM", 60.0), RiskHolding("WILD", 40.0)],
    )
    rows = out["holdings"]
    assert sum(h["money_pct"] for h in rows) == pytest.approx(100.0, abs=0.2)
    assert sum(h["risk_pct"] for h in rows) == pytest.approx(100.0, abs=0.2)
    assert rows[0]["symbol"] == "WILD"
    assert (
        rows[0]["money_pct"] == 40.0 and rows[0]["risk_pct"] > 90.0
    )  # 40% of the money, most of the risk


def test_the_same_share_held_twice_is_one_holding() -> None:
    index = FakeIndex({"AAA": series("AAA", walk(rng_returns(300, 5)))})
    out = portfolio_risk(index, [RiskHolding("AAA", 10.0), RiskHolding("AAA", 30.0)])
    assert [h["symbol"] for h in out["holdings"]] == ["AAA"]


def test_the_window_is_the_last_year_and_is_stated() -> None:
    index = FakeIndex({"AAA": series("AAA", walk(rng_returns(600, 6)))})
    out = portfolio_risk(index, [RiskHolding("AAA", 1.0)])
    assert out["window"]["sessions"] == 252
    assert out["window"]["from"] < out["window"]["to"]
    assert out["note"] == NOTE and "not a forecast" in NOTE


# --------------------------------------------------------------------------------- what is left out


def test_a_share_not_in_the_market_data_is_left_out_and_named() -> None:
    index = FakeIndex(
        {
            "AAA": series("AAA", walk(rng_returns(300, 7))),
            "BBB": series("BBB", walk(rng_returns(300, 8))),
        }
    )
    out = portfolio_risk(
        index, [RiskHolding("AAA", 1.0), RiskHolding("BBB", 1.0), RiskHolding("ZZZ", 1.0)]
    )
    assert out["available"] is True
    assert out["left_out"] == [{"symbol": "ZZZ", "reason": "Not in your market data."}]
    assert {h["symbol"] for h in out["holdings"]} == {"AAA", "BBB"}


def test_a_share_with_too_little_history_is_left_out_so_it_does_not_shorten_the_rest() -> None:
    long = series("LONG", walk(rng_returns(300, 9)))
    other = series("OTHER", walk(rng_returns(300, 10)))
    new = series("NEWLY", walk(rng_returns(20, 11)), skip=280)  # listed 20 sessions ago
    out = portfolio_risk(
        FakeIndex({"LONG": long, "OTHER": other, "NEWLY": new}),
        [RiskHolding(s, 1.0) for s in ("LONG", "OTHER", "NEWLY")],
    )
    assert out["window"]["sessions"] == 252
    assert [e["symbol"] for e in out["left_out"]] == ["NEWLY"]
    assert "history" in out["left_out"][0]["reason"]


def test_when_nothing_has_enough_history_it_says_so_and_names_the_click() -> None:
    index = FakeIndex({"AAA": series("AAA", walk(rng_returns(MIN_SESSIONS - 5, 12)))})
    out = portfolio_risk(index, [RiskHolding("AAA", 1.0)])
    assert out["available"] is False and out["volatility_pct"] is None
    assert "price history" in out["message"]


def test_no_holdings_and_no_value_are_said_plainly() -> None:
    assert portfolio_risk(FakeIndex({}), [])["available"] is False
    assert portfolio_risk(FakeIndex({}), [RiskHolding("AAA", 0.0)])["available"] is False


def test_days_the_index_flags_as_data_breaks_are_left_out_and_counted() -> None:
    r = rng_returns(300, 13)
    closes = walk(r)
    index = FakeIndex(
        {"AAA": series("AAA", closes), "BBB": series("BBB", walk(rng_returns(300, 14)))}
    )
    broken_day = index.table["AAA"].dates[-40]
    index.breaks["AAA"] = [
        {"d": broken_day, "kind": "UNADJUSTED_SPLIT", "change": -0.5, "note": "x"}
    ]
    out = portfolio_risk(index, [RiskHolding("AAA", 1.0), RiskHolding("BBB", 1.0)])
    assert out["window"]["days_left_out"] == 1
    assert out["available"] is True


# --------------------------------------------------------------------------------- from quantities, and the short summary


def test_values_come_from_the_latest_close_times_the_quantity() -> None:
    a, b = series("AAA", walk(rng_returns(300, 15))), series("BBB", walk(rng_returns(300, 16)))
    out = risk_from_quantities(FakeIndex({"AAA": a, "BBB": b}), {"AAA": 10, "BBB": 20})
    want_a, want_b = float(a.close[-1]) * 10, float(b.close[-1]) * 20
    money = {h["symbol"]: h["money_pct"] for h in out["holdings"]}
    assert money["AAA"] == pytest.approx(want_a / (want_a + want_b) * 100, abs=0.1)


def test_the_short_summary_keeps_only_what_an_assistant_needs() -> None:
    table = {f"S{i}": series(f"S{i}", walk(rng_returns(300, 20 + i))) for i in range(5)}
    out = portfolio_risk(
        FakeIndex(table), [RiskHolding(s, 100.0 * (i + 1)) for i, s in enumerate(table)]
    )
    short = risk_summary(out)
    assert short is not None
    assert set(short) == {
        "volatility_pct",
        "effective_bets",
        "holdings_counted",
        "sessions",
        "largest_risks",
        "note",
    }
    assert len(short["largest_risks"]) == 3
    assert risk_summary({"available": False}) is None


def test_the_reply_is_plain_numbers_and_words_with_no_developer_terms() -> None:
    index = FakeIndex(
        {
            "AAA": series("AAA", walk(rng_returns(300, 30))),
            "BBB": series("BBB", walk(rng_returns(300, 31))),
        }
    )
    out = portfolio_risk(index, [RiskHolding("AAA", 1.0), RiskHolding("BBB", 2.0)])
    text = repr(out)
    for word in ("nan", "inf", "numpy", "Traceback"):
        assert word not in text
    assert out["shrinkage"] is not None and 0.0 <= out["shrinkage"] <= 1.0


def test_holdings_that_move_in_opposite_directions_never_count_as_more_bets_than_there_are_holdings() -> (
    None
):
    r = rng_returns(300, 77)
    mirror = -r + rng_returns(300, 78, sigma=0.001)
    index = FakeIndex({"UP": series("UP", walk(r)), "DOWN": series("DOWN", walk(mirror))})
    out = portfolio_risk(index, [RiskHolding("UP", 1.0), RiskHolding("DOWN", 1.0)])
    assert out["diversification"]["average_correlation"] < -0.9
    assert out["effective_bets"] == 2.0
    assert out["volatility_pct"] < 2.0  # they cancel almost exactly


def test_a_perfect_hedge_or_a_flat_price_says_nothing_has_moved_not_that_history_is_short() -> None:
    r = rng_returns(300, 79)
    hedge = FakeIndex({"UP": series("UP", walk(r)), "DOWN": series("DOWN", walk(-r))})
    assert (
        portfolio_risk(hedge, [RiskHolding("UP", 1.0), RiskHolding("DOWN", 1.0)])["message"]
        == NO_MOVEMENT
    )
    flat = FakeIndex({"FLAT": series("FLAT", np.full(300, 100.0))})
    assert portfolio_risk(flat, [RiskHolding("FLAT", 1.0)])["message"] == NO_MOVEMENT
