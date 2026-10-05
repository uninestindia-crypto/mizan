"""Drive the real ``run_paper_session`` end to end, so its *call sites* are guarded, not only its helpers.

Red Team round 7 extracted the runner's decisions into named functions with tests, then showed that
13 of 18 string-preserving mutants of the *wiring* still survived: the exit loop, the entry loop, the
kill-switch refusal, the compare-and-swap at the save, the drawdown anchor. Each of those could be
disabled outright with the whole suite green, because nothing ran a session far enough to submit or
refuse an order. These tests do. The feed, the model's cross-section and the clock are stubbed; the
governor, the paper engine, the ledger, the portfolio file and the reconciliation are real.
"""

from __future__ import annotations

import importlib.util
import logging
import os
import sys
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import ModuleType
from typing import Any
from unittest import mock

import pytest

from quant_system.execution.paper_portfolio import PortfolioHolding

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "run_paper_pilot_session.py"
SESSION_DATE = date(2026, 9, 2)
OPEN = Decimal("1000.00")


def _runner() -> ModuleType:
    spec = importlib.util.spec_from_file_location("_rps_wiring", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    # The script loads `.env` at import; keep that out of the rest of the suite.
    with mock.patch.dict(os.environ, os.environ.copy(), clear=True):
        sys.modules[spec.name] = module
        try:
            spec.loader.exec_module(module)
        finally:
            sys.modules.pop(spec.name, None)
    return module


class Harness:
    """A session with a fake feed, run for real."""

    def __init__(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self.runner = _runner()
        self.monkeypatch = monkeypatch
        self.runs = tmp_path / "paper_runs"
        self.runs.mkdir()
        self.state_path = self.runs / "portfolio_state.json"
        r = self.runner
        monkeypatch.setattr(r, "PORTFOLIO_STATE_PATH", self.state_path)
        monkeypatch.setattr(r, "PROJECT_ROOT", tmp_path)  # the evidence backup lands in tmp
        monkeypatch.setattr(r, "assert_upstox_usable", lambda token: None)
        monkeypatch.setenv("UPSTOX_ACCESS_TOKEN", "test-only-not-a-real-token")
        self.clock = datetime(2026, 9, 2, 9, 15, tzinfo=r._IST)
        monkeypatch.setattr(r, "now_ist", lambda: self.clock)

    # ---- the world the session sees
    def feed(self, prices: dict[str, str]) -> None:
        quotes = {s: {"price": Decimal(p), "depth": 100_000} for s, p in prices.items()}
        self.quotes = quotes
        self.monkeypatch.setattr(
            self.runner,
            "fetch_quotes_with_retry",
            lambda universe, access_token=None, **kw: dict(quotes),
        )
        self.monkeypatch.setattr(
            self.runner,
            "fetch_upstox_live_quotes",
            lambda universe, access_token=None: dict(quotes),
        )

    def cross_section(self, order: list[str]) -> None:
        """Make ``order`` the model's ranking, best first.

        Every feature of the name ranked k-th is moved k tenths of a standard deviation from the
        model's own mean, in whichever direction the real scorer says is better. The scorer is asked
        rather than assumed, so the ranking the session sees is the one the model really gives.
        """
        r = self.runner
        model = r.load_mizan_for_execution(
            r.ExecutionSurface.RESEARCH_PAPER, r.PAPER_OBSERVATION_EXEMPTION
        )
        names = list(model.preprocessor.feature_names)
        means = [float(v) for v in model.preprocessor.means]
        scales = [float(v) for v in model.preprocessor.scales]

        def build(direction: float) -> dict[str, dict[str, float]]:
            return {
                symbol: {
                    n: means[i] + direction * scales[i] * (k + 1) * 0.1 for i, n in enumerate(names)
                }
                for k, symbol in enumerate(order)
            }

        features = build(1.0)
        scores = model.predict_scores(features)
        if scores[order[0]] < scores[order[-1]]:
            features = build(-1.0)
            scores = model.predict_scores(features)
        assert sorted(scores, key=lambda x: -scores[x]) == order, "ranking not controlled"
        coverage = r.CrossSectionCoverage(
            requested=tuple(order),
            scored=tuple(order),
            skipped_short_history=(),
            skipped_not_computable=(),
        )
        self.monkeypatch.setattr(
            r, "load_mizan_cross_section", lambda universe, as_of: (features, coverage)
        )
        self.ranking = order

    def state(self, **kwargs: Any) -> Any:
        state = self.runner.PaperPortfolioState(**kwargs)
        self.runner.save_portfolio(self.state_path, state)
        return state

    # ---- run
    def run(self, universe: list[str], *, realtime: bool = False) -> dict[str, Any]:
        self.monkeypatch.setattr(self.runner.time, "sleep", lambda s: self._advance())
        return self.runner.run_paper_session(
            session_date=SESSION_DATE,
            output_dir=self.runs,
            universe=universe,
            upstox_token="test-only",
            initial_cash=Decimal("1000000.00"),
            realtime=realtime,
            interval_seconds=0.0,
            force_new_portfolio=True,
        )

    def _advance(self) -> None:
        self.clock += timedelta(minutes=15)

    def saved(self) -> Any:
        return self.runner.load_portfolio(self.state_path)


@pytest.fixture()
def harness(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Harness:
    return Harness(tmp_path, monkeypatch)


# Twenty-five names: the top fifth is five picks at about 19% each, inside the 30% weight cap. With
# five names the one pick would be sized at 95% of the book and the governor would rightly refuse it.
NAMES = [f"S{i:02d}" for i in range(1, 26)]
LAST = NAMES[-1]
PRICES = dict.fromkeys(NAMES, "1000.00")


def _first_pick(h: Harness) -> str:
    return h.ranking[0]


# ------------------------------------------------------------------ the order loops (M4, M5)


def test_a_rebalance_session_buys_the_selection(harness: Harness) -> None:
    """M5: with the entry loop disabled the pilot never buys anything."""
    harness.feed(PRICES)
    harness.cross_section(NAMES)
    result = harness.run(NAMES)
    assert result["order_statistics"]["orders_filled"] >= 1
    held = harness.saved().holdings
    assert _first_pick(harness) in held and held[_first_pick(harness)].quantity > 0


def test_a_rebalance_session_sells_what_is_no_longer_selected(harness: Harness) -> None:
    """M4: with the exit loop disabled the pilot never sells anything on a rebalance."""
    harness.feed(PRICES)
    harness.cross_section(NAMES)
    dropped = NAMES[-1]  # ranked last, so not in the top fraction
    harness.state(
        cash=Decimal("900000.00"),
        holdings={
            dropped: PortfolioHolding(
                symbol=dropped, quantity=100, average_cost=OPEN, opened_on=date(2026, 8, 18)
            )
        },
        sessions_held=10,
        sessions_completed=10,
        peak_equity=Decimal("1000000.00"),
    )
    harness.run(NAMES)
    assert dropped not in harness.saved().holdings


def test_a_hold_session_trades_nothing(harness: Harness) -> None:
    """The same loops, gated on `rebalancing`, must stay quiet between rebalances."""
    harness.feed(PRICES)
    harness.cross_section(NAMES)
    harness.state(
        cash=Decimal("900000.00"),
        holdings={
            LAST: PortfolioHolding(
                symbol=LAST, quantity=100, average_cost=OPEN, opened_on=date(2026, 8, 31)
            )
        },
        sessions_held=2,
        sessions_completed=2,
        peak_equity=Decimal("1000000.00"),
    )
    result = harness.run(NAMES)
    assert result["order_statistics"]["orders_submitted"] == 0
    assert set(harness.saved().holdings) == {LAST}


# ------------------------------------------------------------------ the kill switch (M6)


def test_a_halted_book_refuses_to_trade_next_session(harness: Harness) -> None:
    harness.feed(PRICES)
    harness.cross_section(NAMES)
    harness.state(
        cash=Decimal("500000.00"),
        risk_halted=True,
        halted_on=date(2026, 9, 1),
        halt_reason="TRAILING_DRAWDOWN_KILL_SWITCH",
    )
    with pytest.raises(SystemExit) as refusal:
        harness.run(NAMES)
    assert refusal.value.code == 8


# ---------------------------------------------------- the compare-and-swap (M1) and abort (M7)


def test_a_concurrent_write_during_the_session_is_not_overwritten(harness: Harness) -> None:
    """M1: the expected hash must be the one read at load, not re-read just before the save."""
    harness.feed(PRICES)
    harness.cross_section(NAMES)
    r = harness.runner
    concurrent = r.PaperPortfolioState(cash=Decimal("950000.00"), sessions_completed=7)
    real_load = r.load_portfolio

    def load_then_let_another_session_write(path: Path) -> Any:
        loaded = real_load(path)
        r.save_portfolio(path, concurrent)  # the other session finishes while this one runs
        return loaded

    harness.monkeypatch.setattr(r, "load_portfolio", load_then_let_another_session_write)
    result = harness.run(NAMES)
    on_disk = real_load(harness.state_path)
    assert on_disk.sessions_completed == 7 and on_disk.cash == Decimal("950000.00")
    assert (
        result["aborted"] is True
        and "changed since this session loaded it" in result["abort_reason"]
    )


def test_a_session_that_raised_does_not_spend_a_held_session(harness: Harness) -> None:
    """M7: an aborted session keeps its book but is not counted as one of the model's sessions."""
    harness.feed(PRICES)
    harness.cross_section(NAMES)
    r = harness.runner
    real = r.OrderBookSnapshot.from_levels
    calls = {"n": 0}

    def explode_on_the_second_pass(**kwargs: Any) -> Any:
        calls["n"] += 1
        if calls["n"] > len(NAMES):
            raise RuntimeError("feed handler fell over")
        return real(**kwargs)

    harness.monkeypatch.setattr(r.OrderBookSnapshot, "from_levels", explode_on_the_second_pass)
    result = harness.run(NAMES)
    assert result["aborted"] is True
    assert harness.saved().sessions_completed == 0


# --------------------------------------------------------------- the drawdown anchor (M2, M17)


def test_a_live_session_anchors_and_persists_the_daily_baseline(harness: Harness) -> None:
    """M17 and M2: the daily drawdown baseline is taken from the first live mark and carried over."""
    harness.feed(PRICES)
    harness.cross_section(NAMES)
    harness.run(NAMES, realtime=True)
    saved = harness.saved()
    assert saved.daily_anchor_on == SESSION_DATE
    assert saved.daily_anchor_equity > 0


# ----------------------------------------------------------- what the operator is told (M14)


def test_the_operator_is_told_which_carried_names_are_unquoted(
    harness: Harness, caplog: pytest.LogCaptureFixture
) -> None:
    harness.feed(dict.fromkeys(NAMES[:-1], "1000.00"))  # the last name is not quoted
    harness.cross_section(NAMES[:-1])
    harness.state(
        cash=Decimal("900000.00"),
        holdings={
            LAST: PortfolioHolding(
                symbol=LAST, quantity=100, average_cost=OPEN, opened_on=date(2026, 8, 31)
            )
        },
        sessions_held=2,
        sessions_completed=2,
        peak_equity=Decimal("1000000.00"),
    )
    caplog.set_level(logging.WARNING, logger=harness.runner.logger.name)
    harness.run(NAMES[:-1])
    assert "No opening quote for 1 carried name(s)" in caplog.text and LAST in caplog.text
