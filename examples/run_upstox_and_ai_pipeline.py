"""Example: End-to-End Pipeline with Upstox Market Data, Machine Learning, and AI Multi-Agent Consensus."""

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
from quant_system.data.upstox import UpstoxClient
from quant_system.risk.governor import PreTradeRiskGovernor, RiskLimits
from quant_system.strategies.ai_enhanced_ml import AIEnhancedMLEquityStrategy


def main() -> None:
    print("=" * 75)
    print("[PIPELINE] QuantOS: Upstox Live/Historical Data + ML + Multi-Agent AI Advisory")
    print("=" * 75)

    # 1. Initialize Upstox Client
    upstox_client = UpstoxClient()
    instruments = {
        "INFY": "NSE_EQ|INE009A01021",
        "TCS": "NSE_EQ|INE467B01029",
        "RELIANCE": "NSE_EQ|INE002A01018",
        "HDFCBANK": "NSE_EQ|INE040A01034",
        "ICICIBANK": "NSE_EQ|INE090A01021",
    }

    start_dt = date(2025, 1, 1)
    dataset = {}

    if upstox_client.is_authenticated:
        print("[UPSTOX] Connected with active credentials. Fetching market candles...")
        for sym, inst_key in instruments.items():
            series = upstox_client.fetch_historical_bars(
                instrument_key=inst_key,
                symbol=sym,
                interval="day",
            )
            if len(series.bars) >= 50:
                dataset[sym] = series.bars
                print(f"  -> {sym}: Loaded {len(series.bars)} real candles from Upstox")
            else:
                print(f"  -> {sym}: Falling back to synthetic baseline (insufficient live bars)")

    # Fallback to calibrated simulation if Upstox credentials are not yet set
    if not dataset:
        print("[DATA] Using calibrated market simulation for universe:", list(instruments.keys()))
        for idx, sym in enumerate(instruments.keys()):
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

    # 2. Instantiate AI-Enhanced ML Strategy
    strategy = AIEnhancedMLEquityStrategy(
        name="AIEnhanced_ML_NIFTY5",
        params={
            "train_window": 60,
            "top_n": 2,
            "confidence_threshold": 0.52,
            "l2_penalty": 1.0,
            "require_ai_confirmation": True,
        },
    )

    # 3. Configure Pre-Trade Risk Governor
    risk_limits = RiskLimits(
        max_position_weight=0.35,
        max_daily_drawdown_pct=0.04,
        max_total_drawdown_pct=0.15,
        min_cash_buffer_pct=0.05,
    )
    governor = PreTradeRiskGovernor(limits=risk_limits)

    # 4. Run Backtest Engine with Real Indian Friction
    engine = BacktestEngine(
        strategy=strategy,
        initial_cash=Decimal("1000000.00"),  # Rs. 10 Lakhs
        risk_governor=governor,
        slippage_bps=5.0,
    )

    print("\nRunning event-driven simulation with ML models & AI multi-agent consensus...")
    result = engine.run(dataset)

    # 5. Generate Performance Tearsheet
    stats = PerformanceMetrics.calculate(result.equity_curve, result.fills)
    tearsheet = TearsheetGenerator.generate_markdown(result, stats, strategy_name=strategy.name)

    print("\n" + tearsheet)
    print("\n[SUCCESS] Pipeline executed successfully.")


if __name__ == "__main__":
    main()
