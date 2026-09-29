"""Strategy Lab: parity with BacktestEngine, no look-ahead, dated costs, verdicts, refusals."""

from __future__ import annotations

import re
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import numpy as np
import pytest

from quant_system.backtest.costs import IndianMarketCostModel
from quant_system.backtest.engine import BacktestEngine
from quant_system.core.domain import PriceBar, Side, Signal
from quant_system.lab import (
    COSTS_COVERED_FROM,
    BrokerCharges,
    LabError,
    LabRequest,
    RetailCostModel,
    run_lab,
)
from quant_system.lab.simulator import SimConfig, simulate
from quant_system.lab.stats import (
    EVIDENCE_GATE,
    WHOLE_LIST,
    Performance,
    excess_probability,
    verdict,
)
from quant_system.lab.strategies import (
    Breakout,
    BuyAndHold,
    LabStrategy,
    MomentumRotation,
    Panel,
    Pullback,
    Targets,
    TrendFollowing,
)
from quant_system.lab.templates import get_template
from quant_system.market import MarketIndex, build_market_index
from quant_system.strategies.base import BaseStrategy, MarketContext
from tests.market_fixtures import build_standard_store

# ------------------------------------------------------------------ parity with BacktestEngine

# One position at a time: BacktestEngine's governor refuses a second buy while another position is
# held (PORTFOLIO_VALUATION_UNAVAILABLE: the engine supplies a quote only for the ordered symbol).
SCHEDULE: dict[int, tuple[str, Side | None]] = {
    5: ("AAA", Side.BUY),
    20: ("AAA", None),
    25: ("BBB", Side.BUY),
    40: ("BBB", None),
}


def _price_rows(n: int, start: float, drift: float, wobble: float) -> list[tuple[Decimal, Decimal]]:
    rows = []
    for i in range(n):
        close = start * (1 + drift) ** i * (1 + wobble * np.sin(i / 3))
        rows.append((Decimal(f"{close * 0.997:.2f}"), Decimal(f"{close:.2f}")))
    return rows


def _price_bars(n: int = 60) -> dict[str, list[PriceBar]]:
    start = datetime(2024, 1, 1, 15, 30, tzinfo=UTC)
    out: dict[str, list[PriceBar]] = {}
    for symbol, base, drift in (("AAA", 150.0, 0.004), ("BBB", 820.0, -0.002)):
        bars = []
        for i, (o, c) in enumerate(_price_rows(n, base, drift, 0.01)):
            bars.append(
                PriceBar(
                    symbol=symbol,
                    timestamp=start + timedelta(days=i),
                    open=o,
                    high=max(o, c),
                    low=min(o, c),
                    close=c,
                    volume=1000,
                )
            )
        out[symbol] = bars
    return out


class _ScheduledEngineStrategy(BaseStrategy):
    def __init__(self) -> None:
        super().__init__(name="scheduled")
        self.step = -1

    def generate_signals(self, ctx: MarketContext) -> list[Signal]:
        self.step += 1
        if self.step not in SCHEDULE:
            return []
        symbol, side = SCHEDULE[self.step]
        return [
            Signal(
                symbol=symbol,
                side=side,
                strength=1.0,
                timestamp=ctx.current_time,
                strategy_name=self.name,
                target_weight=0.1,
            )
        ]


class _ScheduledLabStrategy(LabStrategy):
    def prepare(self, panel: Panel) -> None:
        self.symbols = panel.symbols

    def decide(self, t: int, held: frozenset[str]) -> Targets | None:
        if t not in SCHEDULE:
            return None
        symbol, side = SCHEDULE[t]
        wanted = set(held) | {symbol} if side == Side.BUY else set(held) - {symbol}
        return dict.fromkeys(wanted, 0.1)


def _engine_fee(side: Side, quantity: int, price: Decimal, _day: date) -> Decimal:
    return IndianMarketCostModel.calculate_equity_delivery(
        side=side, quantity=quantity, price=price, slippage_bps=0.0
    ).total_fee


def test_simulator_reproduces_backtest_engine_fills_and_equity_exactly() -> None:
    bars = _price_bars()
    engine_result = BacktestEngine(
        _ScheduledEngineStrategy(), initial_cash=Decimal("1000000.00"), slippage_bps=5.0
    ).run(bars)

    dates = [b.timestamp.date().isoformat() for b in bars["AAA"]]
    panel = Panel(
        dates=dates,
        symbols=["AAA", "BBB"],
        open={s: np.array([float(b.open) for b in bars[s]]) for s in bars},
        close={s: np.array([float(b.close) for b in bars[s]]) for s in bars},
    )
    config = SimConfig(
        capital=Decimal("1000000.00"), slippage_bps=Decimal("5"), cash_buffer=Decimal("0")
    )
    lab_result = simulate(panel, _ScheduledLabStrategy(0), 0, _engine_fee, config)

    engine_fills = [
        (f.timestamp.date().isoformat(), f.symbol, f.side.value, f.quantity, f.price, f.fee)
        for f in engine_result.fills
    ]
    lab_fills = [(f.date, f.symbol, f.side, f.quantity, f.price, f.fee) for f in lab_result.fills]
    assert len(engine_fills) == 4
    assert lab_fills == engine_fills
    assert lab_result.equity[-1] == engine_result.final_equity
    assert [s.total_equity for s in engine_result.equity_curve] == lab_result.equity


# ------------------------------------------------------------------------ fills and costs


def _single_panel(opens: list[float], closes: list[float]) -> Panel:
    dates = [(date(2024, 1, 1) + timedelta(days=i)).isoformat() for i in range(len(opens))]
    return Panel(dates, ["AAA"], {"AAA": np.array(opens)}, {"AAA": np.array(closes)})


def _flat_fee(side: Side, quantity: int, price: Decimal, day: date) -> Decimal:
    return Decimal("10.00")


def test_decision_at_close_fills_at_next_open_with_slippage() -> None:
    panel = _single_panel([100.0, 100.5, 103.0], [101.0, 102.5, 104.0])
    config = SimConfig(
        capital=Decimal("100000"), slippage_bps=Decimal("10"), cash_buffer=Decimal("0")
    )
    result = simulate(panel, BuyAndHold(0), 0, _flat_fee, config)
    fill = result.fills[0]
    assert fill.date == panel.dates[1]  # decided at day 0's close, filled at day 1's open
    assert fill.price == Decimal("100.60")  # 100.5 plus 10 bps, rounded to the paisa
    assert fill.quantity == 990  # int(100000 / 101.0), sized at the decision close
    assert fill.slippage == Decimal("99.00")


def test_a_buy_that_no_longer_fits_the_cash_is_shrunk_not_dropped() -> None:
    panel = _single_panel([100.0, 150.0, 150.0], [100.0, 150.0, 150.0])
    config = SimConfig(
        capital=Decimal("10000"), slippage_bps=Decimal("0"), cash_buffer=Decimal("0")
    )
    result = simulate(panel, BuyAndHold(0), 0, _flat_fee, config)
    assert result.fills[0].quantity == 66  # (10000 - 10) // 150
    assert result.skipped == []


def test_charges_follow_the_rule_in_force_on_the_trade_date() -> None:
    model = RetailCostModel()
    before = model.charges(Side.BUY, 100, Decimal("1000"), date(2024, 9, 30))
    after = model.charges(Side.BUY, 100, Decimal("1000"), date(2024, 10, 1))
    rule = {c.label: c.rule_id for c in before.lines}["Exchange transaction charge"]
    assert rule == "EXCH-EQ-DEL-20170401"
    assert {c.label: c.rule_id for c in after.lines}[
        "Exchange transaction charge"
    ] == "EXCH-EQ-DEL-20241001"
    assert after.total < before.total


def test_trades_before_uniform_stamp_duty_cannot_be_priced() -> None:
    assert COSTS_COVERED_FROM == date(2020, 7, 1)
    with pytest.raises(ValueError, match="STAMP_DUTY"):
        RetailCostModel().charges(Side.BUY, 1, Decimal("100"), date(2020, 6, 30))


def test_broker_charges_carry_gst() -> None:
    broker = BrokerCharges(delivery_per_order=Decimal("20"), dp_charge_per_sell=Decimal("15"))
    lines = {
        c.label: c.amount
        for c in RetailCostModel(broker)
        .charges(Side.SELL, 10, Decimal("500"), date(2025, 1, 2))
        .lines
    }
    assert lines["Brokerage (your broker)"] == Decimal("20.00")
    assert lines["Depository (DP) charge (your broker)"] == Decimal("15.00")
    assert lines["GST on broker charges"] == Decimal("6.30")
    assert "Stamp duty" not in lines  # buy side only


def test_invalid_broker_charges_are_refused() -> None:
    with pytest.raises(ValueError):
        BrokerCharges(delivery_per_order=Decimal("-1"))


# ------------------------------------------------------------------------- no look-ahead


def _random_panel(seed: int, n: int = 400, symbols: int = 5) -> Panel:
    rng = np.random.default_rng(seed)
    names = [f"S{i}" for i in range(symbols)]
    closes = {s: 100 * np.cumprod(1 + rng.normal(0.0005, 0.02, n)) for s in names}
    dates = [(date(2020, 1, 1) + timedelta(days=i)).isoformat() for i in range(n)]
    return Panel(dates, names, {s: c * 0.999 for s, c in closes.items()}, closes)


STRATEGIES: list[Callable[[], LabStrategy]] = [
    lambda: TrendFollowing(0, 20, 50),
    lambda: Breakout(0, 60, 20),
    lambda: Pullback(0, 14, 30, 55, 20, True),
    lambda: MomentumRotation(0, 120, 10, 2, 21, True),
]


@pytest.mark.parametrize("factory", STRATEGIES)
def test_decisions_up_to_t_do_not_change_when_the_future_changes(
    factory: Callable[[], LabStrategy],
) -> None:
    cut = 300
    original = _random_panel(7)
    altered_close = {s: c.copy() for s, c in original.close.items()}
    for series in altered_close.values():
        series[cut + 1 :] *= np.linspace(0.3, 3.0, series.size - cut - 1)
    altered = Panel(original.dates, original.symbols, original.open, altered_close)
    a, b = factory(), factory()
    a.prepare(original)
    b.prepare(altered)
    held: frozenset[str] = frozenset()
    for t in range(cut + 1):
        assert a.decide(t, held) == b.decide(t, held), f"decision at {t} used future prices"


# ------------------------------------------------------------------------------ verdicts


def _perf(total_return: float, round_trips: int = 50) -> Performance:
    return Performance(
        1e6,
        1e6 * (1 + total_return),
        total_return,
        None,
        None,
        None,
        -0.1,
        1.0,
        100,
        round_trips,
        0.5,
        10.0,
        1000.0,
        100.0,
    )


@pytest.mark.parametrize(
    ("strategy", "probability", "sessions", "level"),
    [
        (0.10, 0.99, 1000, "LOST"),
        (0.30, 0.99, 100, "TOO_SHORT"),
        (0.30, 0.40, 1000, "NO_EVIDENCE"),
        (0.30, None, 1000, "NO_EVIDENCE"),
        (0.30, 0.80, 1000, "PROMISING"),
        (0.30, EVIDENCE_GATE, 1000, "EDGE"),
    ],
)
def test_verdict_levels(
    strategy: float, probability: float | None, sessions: int, level: str
) -> None:
    result = verdict(_perf(strategy), _perf(0.20), probability, 3, sessions, counts_trades=True)
    assert result.level == level


def test_few_trades_are_too_little_to_judge_but_buy_and_hold_is_not_penalised_for_it() -> None:
    few = _perf(0.30, round_trips=5)
    assert verdict(few, _perf(0.2), 0.99, 1, 1000, counts_trades=True).level == "TOO_SHORT"
    assert verdict(few, _perf(0.2), 0.99, 1, 1000, counts_trades=False).level == "EDGE"


def test_a_biased_universe_can_never_reach_edge() -> None:
    result = verdict(
        _perf(0.9), _perf(0.2), 0.999, 1, 1000, True, against=WHOLE_LIST, cap_reason="Biased list."
    )
    assert result.level == "PROMISING"
    assert "Biased list." in result.body and "owning every stock in the list equally" in result.body


def test_verdict_text_never_promises_profit() -> None:
    banned = re.compile(r"profitable|guarantee|\bsure\b|risk-free", re.IGNORECASE)
    for strategy, probability, sessions in [
        (0.1, 0.9, 1000),
        (0.3, 0.1, 1000),
        (0.3, 0.8, 1000),
        (0.3, 0.99, 1000),
        (0.3, 0.99, 10),
    ]:
        result = verdict(_perf(strategy), _perf(0.2), probability, 4, sessions, True)
        assert not banned.search(result.title + result.body)


def test_more_trials_lower_the_probability() -> None:
    rng = np.random.default_rng(3)
    bench = [Decimal("1000")]
    strat = [Decimal("1000")]
    for _ in range(750):
        r = rng.normal(0.0004, 0.01)
        bench.append(bench[-1] * Decimal(repr(1 + r)))
        strat.append(strat[-1] * Decimal(repr(1 + r + rng.normal(0.0006, 0.004))))
    one = excess_probability(strat, bench, 1)
    many = excess_probability(strat, bench, 100)
    assert one is not None and many is not None
    assert many < one


def test_identical_returns_have_no_probability() -> None:
    same = [Decimal(v) for v in ("100", "101", "102", "101")]
    assert excess_probability(same, same, 1) is None


# --------------------------------------------------------------------------- run_lab


@pytest.fixture()
def index(tmp_path: Path) -> MarketIndex:
    folder = tmp_path / "data"
    build_standard_store(folder)
    build_market_index(folder, tmp_path / "index")
    return MarketIndex(tmp_path / "index")


def test_run_lab_buy_and_hold_returns_a_complete_result(index: MarketIndex) -> None:
    out = run_lab(index, LabRequest("buy_hold", {}, "stocks", ("aaa",)), prior_trials=2)
    assert out["period"]["start"] >= COSTS_COVERED_FROM.isoformat()
    assert out["verdict"]["trials"] == 3
    assert len(out["equity"]) == out["period"]["sessions"] + 1
    assert out["equity"][0][1] == out["equity"][0][2] == 1_000_000.0
    assert out["strategy"]["fills"] == 1 and out["comparison"] is None
    assert any("exclude dividends" in text for text in out["assumptions"])


def test_run_lab_universe_is_judged_against_the_whole_list(index: MarketIndex) -> None:
    out = run_lab(
        index,
        LabRequest(
            "momentum", {"top_n": 3, "lookback": 63, "skip": 0}, "universe", universe="liquid"
        ),
    )
    assert out["comparison"]["label"] == "Whole list, equal weight"
    assert out["verdict"]["level"] != "EDGE"
    assert all(row[3] is not None for row in out["equity"])
    assert any("Survivorship" in text for text in out["assumptions"])


def test_run_lab_refuses_a_test_across_a_demerger(index: MarketIndex) -> None:
    with pytest.raises(LabError, match="demerger on 2020-09-15"):
        run_lab(index, LabRequest("buy_hold", {}, "stocks", ("DDD",)))
    out = run_lab(index, LabRequest("buy_hold", {}, "stocks", ("DDD",), start="2020-09-16"))
    assert out["period"]["start"] >= "2020-09-16"


@pytest.mark.parametrize(
    ("request_", "message"),
    [
        (LabRequest("trend", {"fast": 50, "slow": 20}, "stocks", ("AAA",)), "shorter"),
        (LabRequest("trend", {"fast": 1}, "stocks", ("AAA",)), "between 5 and 100"),
        (LabRequest("trend", {"bogus": 1}, "stocks", ("AAA",)), "Unknown settings"),
        (LabRequest("nope", {}, "stocks", ("AAA",)), "Unknown strategy"),
        (LabRequest("buy_hold", {}, "stocks", ("ZZZ",)), "not in the market data"),
        (LabRequest("buy_hold", {}, "stocks", ()), "between 1 and 20"),
        (LabRequest("buy_hold", {}, "universe", universe="liquid"), "cannot be run"),
        (LabRequest("momentum", {}, "universe", universe="moon"), "Liquid 423"),
        (LabRequest("buy_hold", {}, "stocks", ("AAA",), end="2020-07-10"), "too short"),
        (LabRequest("buy_hold", {}, "stocks", ("AAA",), capital=Decimal("5")), "Capital"),
        (LabRequest("buy_hold", {}, "stocks", ("AAA",), start="yesterday"), "not a valid date"),
    ],
)
def test_run_lab_refuses_bad_requests_with_a_readable_message(
    index: MarketIndex, request_: LabRequest, message: str
) -> None:
    with pytest.raises(LabError, match=message):
        run_lab(index, request_)


def test_every_template_runs_on_the_fixture(index: MarketIndex) -> None:
    for template_id in ("buy_hold", "trend", "breakout", "pullback"):
        params = {"slow": 60, "fast": 10} if template_id == "trend" else {}
        if template_id == "breakout":
            params = {"entry_lookback": 40, "exit_lookback": 10}
        out = run_lab(index, LabRequest(template_id, params, "stocks", ("AAA", "BBB")))
        assert out["template"]["id"] == template_id
        assert get_template(template_id).name == out["template"]["name"]
