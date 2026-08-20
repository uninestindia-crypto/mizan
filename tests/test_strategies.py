from datetime import date, datetime, time
from decimal import Decimal

from quant_system.core.domain import Side
from quant_system.data.loader import SyntheticDataGenerator
from quant_system.strategies.base import MarketContext
from quant_system.strategies.equity_momentum import EquityDualMomentumStrategy
from quant_system.strategies.options_spreads import DirectionalSpreadStrategy
from quant_system.strategies.options_straddle import IntradayStraddleDecayStrategy
from quant_system.strategies.registry import StrategyRegistry


def test_strategy_registry() -> None:
    strats = StrategyRegistry.list_strategies()
    assert "EquityDualMomentum" in strats
    assert "IntradayATMStraddle" in strats
    assert "DirectionalVerticalSpreads" in strats

    inst = StrategyRegistry.create("EquityDualMomentum")
    assert inst.name == "EquityDualMomentum"


def test_equity_momentum_strategy_signals() -> None:
    strat = EquityDualMomentumStrategy(params={"lookback_fast": 5, "lookback_slow": 10, "top_n": 1})
    start_dt = date(2025, 1, 1)
    bars = SyntheticDataGenerator.generate_equity_bars(
        symbol="INFY",
        start_date=start_dt,
        days=20,
        initial_price=1000.0,
        drift=0.01,  # Strong positive drift
        volatility=0.001,
    )

    ctx = MarketContext(
        current_time=bars.bars[-1].timestamp,
        current_bars={"INFY": bars.bars[-1]},
        historical_bars={"INFY": bars.bars},
        current_positions={},
        available_cash=Decimal("500000.00"),
        extra_data={},
    )

    signals = strat.generate_signals(ctx)
    assert len(signals) >= 1
    assert signals[0].side == Side.BUY
    assert signals[0].symbol == "INFY"


def test_intraday_straddle_signals() -> None:
    strat = IntradayStraddleDecayStrategy()
    sim_date = date(2025, 1, 1)
    chain = SyntheticDataGenerator.generate_option_chain(
        underlying="NIFTY",
        spot_price=Decimal("24500.00"),
        timestamp=datetime.combine(sim_date, time(9, 20)),
        expiry=date(2025, 1, 8),
    )

    ctx = MarketContext(
        current_time=datetime.combine(sim_date, time(9, 20)),
        current_bars={},
        historical_bars={},
        current_positions={},
        available_cash=Decimal("500000.00"),
        extra_data={"option_chain": chain},
    )

    signals = strat.generate_signals(ctx)
    assert len(signals) == 2  # One Short Call, One Short Put
    assert all(s.side == Side.SELL for s in signals)
    assert signals[0].metadata["leg"] in ("CALL", "PUT")
    assert signals[1].metadata["leg"] in ("CALL", "PUT")


def test_directional_spread_signals() -> None:
    strat = DirectionalSpreadStrategy()
    sim_date = date(2025, 1, 1)
    chain = SyntheticDataGenerator.generate_option_chain(
        underlying="NIFTY",
        spot_price=Decimal("24500.00"),
        timestamp=datetime.combine(sim_date, time(9, 30)),
        expiry=date(2025, 1, 8),
    )

    # Bullish scenario
    ctx = MarketContext(
        current_time=datetime.combine(sim_date, time(9, 30)),
        current_bars={},
        historical_bars={},
        current_positions={},
        available_cash=Decimal("500000.00"),
        extra_data={"option_chain": chain, "directional_bias": "BULLISH"},
    )

    signals = strat.generate_signals(ctx)
    assert len(signals) == 2
    # Buy ATM Call, Sell OTM Call
    buy_sigs = [s for s in signals if s.side == Side.BUY]
    sell_sigs = [s for s in signals if s.side == Side.SELL]
    assert len(buy_sigs) == 1
    assert len(sell_sigs) == 1
    assert buy_sigs[0].metadata["leg"] == "LONG_CALL"
    assert sell_sigs[0].metadata["leg"] == "SHORT_CALL"
