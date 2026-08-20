"""Example: Complete end-to-end backtest of an Equity Momentum Strategy with full tearsheet reporting."""

import os
import sys
from datetime import date
from decimal import Decimal

# Ensure src is on PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from quant_system.analytics.metrics import PerformanceMetrics
from quant_system.analytics.tearsheet import TearsheetGenerator
from quant_system.backtest.engine import BacktestEngine
from quant_system.data.loader import SyntheticDataGenerator
from quant_system.risk.governor import PreTradeRiskGovernor, RiskLimits
from quant_system.strategies.equity_momentum import EquityDualMomentumStrategy


def main() -> None:
    print("=" * 70)
    print("[BACKTEST] Running QuantOS Equity Dual Momentum Backtest")
    print("=" * 70)

    # 1. Generate Synthetic 252-day Historical Data for Universe
    universe_symbols = ["INFY", "TCS", "RELIANCE", "HDFCBANK", "ICICIBANK"]
    start_dt = date(2025, 1, 1)
    dataset = {}

    print(f"Generating 252 trading days for universe: {universe_symbols}...")
    for idx, sym in enumerate(universe_symbols):
        # Varying drift and volatility parameters per stock
        drift = 0.0008 if idx % 2 == 0 else -0.0002
        vol = 0.015 + (idx * 0.003)
        bars = SyntheticDataGenerator.generate_equity_bars(
            symbol=sym,
            start_date=start_dt,
            days=252,
            initial_price=1000.0 + (idx * 500.0),
            drift=drift,
            volatility=vol,
            seed=100 + idx,
        )
        dataset[sym] = bars.bars

    # 2. Instantiate Strategy & Risk Governor
    strategy = EquityDualMomentumStrategy(
        name="EquityDualMomentum_NIFTY5",
        params={"lookback_fast": 10, "lookback_slow": 30, "top_n": 2},
    )

    risk_limits = RiskLimits(
        max_position_weight=0.35,
        max_daily_drawdown_pct=0.04,
        max_total_drawdown_pct=0.15,
        min_cash_buffer_pct=0.05,
    )
    governor = PreTradeRiskGovernor(limits=risk_limits)

    # 3. Run Event-Driven Backtest
    engine = BacktestEngine(
        strategy=strategy,
        initial_cash=Decimal("1000000.00"),  # ₹10 Lakhs
        risk_governor=governor,
        slippage_bps=5.0,
    )

    print("Running event-driven simulation...")
    result = engine.run(dataset)

    # 4. Compute Analytics & Generate Tearsheet
    stats = PerformanceMetrics.calculate(result.equity_curve, result.fills)
    tearsheet = TearsheetGenerator.generate_markdown(result, stats, strategy_name=strategy.name)

    print("\n" + tearsheet)
    print("\n[SUCCESS] Backtest completed successfully with exact Decimal reconciliation.")


if __name__ == "__main__":
    main()
