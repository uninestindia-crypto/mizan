"""Paper books: a lab rule replayed forward with virtual money, never a second engine."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from quant_system.lab import LabError
from quant_system.lab.paper import PaperSpec, evaluate_book, latest_session
from quant_system.market import MarketIndex
from quant_system.market.index_builder import build_market_index
from tests.market_fixtures import DATES, build_standard_store


@pytest.fixture()
def index(tmp_path: Path) -> MarketIndex:
    folder = tmp_path / "data"
    build_standard_store(folder)
    build_market_index(folder, tmp_path / "index")
    return MarketIndex(tmp_path / "index")


def _spec(start: str, **changes: object) -> PaperSpec:
    base: dict[str, object] = {
        "template_id": "buy_hold",
        "params": {},
        "scope": "stocks",
        "symbols": ("AAA",),
        "universe": None,
        "capital": Decimal("100000"),
        "slippage_bps": Decimal("5"),
        "start_session": start,
    }
    base.update(changes)
    return PaperSpec(**base)  # type: ignore[arg-type]


def test_the_latest_session_is_the_benchmarks_last_day(index: MarketIndex) -> None:
    assert latest_session(index) == DATES[299]


def test_a_book_started_on_the_last_session_waits_and_shows_tomorrows_orders(
    index: MarketIndex,
) -> None:
    state = evaluate_book(index, _spec(DATES[299]))
    assert state["status"] == "WAITING"
    assert state["sessions"] == 0 and state["equity"] == 100_000.0
    assert state["trades"] == [] and state["positions"] == []
    # The decision taken at the last close is queued for the next open, not executed.
    assert [(q["side"], q["symbol"]) for q in state["queued"]] == [("BUY", "AAA")]
    assert state["queued"][0]["quantity"] > 0
    assert (
        state["queued"][0]["reference_price"] > 0
    )  # sized from the last close, shown to the person
    assert state["reading"]["level"] == "TOO_EARLY"


def test_a_running_book_has_real_fills_positions_costs_and_a_benchmark(
    index: MarketIndex,
) -> None:
    state = evaluate_book(index, _spec(DATES[250]))
    assert state["status"] == "RUNNING" and state["sessions"] == 49
    assert state["start_session"] == DATES[250] and state["last_session"] == DATES[299]
    # Decided at the start session's close, filled at the very next open.
    assert [t["date"] for t in state["trades"]] == [DATES[251]]
    assert state["trades"][0]["side"] == "BUY" and state["trades"][0]["fee"] > 0
    assert [p["symbol"] for p in state["positions"]] == ["AAA"]
    assert state["charges"] > 0 and state["slippage"] > 0
    assert state["cash"] + state["positions"][0]["market_value"] == pytest.approx(state["equity"])
    assert len(state["curve"]) == 50 and state["curve"][0][1] == 100_000.0
    assert state["curve"][0][2] == 100_000.0  # the benchmark starts from the same money
    assert state["excess"] == pytest.approx(state["return"] - state["benchmark_return"])
    assert state["queued"] == []  # buy and hold has nothing more to do


def test_replaying_with_less_future_gives_the_same_past(index: MarketIndex) -> None:
    """The book only ever uses prices up to each close: stopping the replay earlier changes nothing
    that already happened. This is what makes a replay equal to following it live."""
    full = evaluate_book(
        index, _spec(DATES[200], template_id="trend", params={"fast": 5, "slow": 20})
    )
    cut = evaluate_book(
        index,
        _spec(
            DATES[200], template_id="trend", params={"fast": 5, "slow": 20}, stop_session=DATES[260]
        ),
    )
    shared = dict(cut["session_equity"])
    assert shared and all(full["session_equity"][d] == e for d, e in shared.items())
    assert [t for t in full["trades"] if t["date"] <= DATES[260]] == cut["trades"]


def test_a_stopped_book_is_frozen_at_its_stop_session(index: MarketIndex) -> None:
    state = evaluate_book(index, _spec(DATES[250], stop_session=DATES[270]))
    assert state["status"] == "STOPPED"
    assert state["last_session"] == DATES[270] and state["sessions"] == 20


def test_a_stock_with_a_demerger_inside_the_window_needs_attention(index: MarketIndex) -> None:
    # DDD is held from DATES[136] and demerges on 2020-09-15, inside the window.
    state = evaluate_book(index, _spec(DATES[135], symbols=("DDD",)))
    assert state["status"] == "ATTENTION"
    assert any("DDD had a demerger" in note for note in state["attention"])


def test_a_universe_book_follows_the_rule_without_a_stock_list(index: MarketIndex) -> None:
    state = evaluate_book(
        index,
        _spec(
            DATES[200],
            template_id="momentum",
            params={"top_n": 3, "lookback": 63, "skip": 0, "rebalance": 21},
            scope="universe",
            symbols=(),
            universe="liquid",
        ),
    )
    assert state["scope"]["kind"] == "universe" and state["scope"]["used"] >= 1
    assert state["status"] in ("RUNNING", "ATTENTION")


def test_bad_specs_are_refused_in_plain_words(index: MarketIndex) -> None:
    with pytest.raises(LabError, match="not in the market data"):
        evaluate_book(index, _spec(DATES[250], symbols=("NOPE",)))
    with pytest.raises(LabError, match="Unknown strategy"):
        evaluate_book(index, _spec(DATES[250], template_id="nonsense"))
    with pytest.raises(LabError, match="only defined from"):
        evaluate_book(index, _spec("2020-03-02"))
    with pytest.raises(LabError, match="ends before this book"):
        evaluate_book(index, _spec("2031-01-01"))
