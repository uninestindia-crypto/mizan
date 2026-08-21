"""QuantOS Automated Daily Pipeline.

Executes end-to-end daily data processing, point-in-time feature generation,
model training/inference, event-driven backtesting, risk governor checks,
and performance reporting with immutable evidence capture.

This pipeline runs on generated data. It does not call the governed Upstox acquisition path, so
every figure it reports describes a deterministic random walk. Live acquisition is Slice 9 scope.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

# Ensure src is on sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from quant_system.analytics.metrics import PerformanceMetrics  # noqa: E402
from quant_system.analytics.tearsheet import TearsheetGenerator  # noqa: E402
from quant_system.backtest.engine import BacktestEngine  # noqa: E402
from quant_system.data.loader import SyntheticDataGenerator  # noqa: E402
from quant_system.data.provenance import RuntimeDataSource, describe  # noqa: E402
from quant_system.risk.checks import RiskLimits  # noqa: E402
from quant_system.risk.governor import PreTradeRiskGovernor  # noqa: E402
from quant_system.strategies.equity_momentum import EquityDualMomentumStrategy  # noqa: E402
from quant_system.strategies.ml_equity import MLEquityStrategy  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("quant_system.daily_pipeline")


@dataclass(frozen=True)
class DailyPipelineSummary:
    """Summary record of a daily automated pipeline run."""

    execution_date: str
    timestamp_utc: str
    data_source: str
    data_source_disclosure: str
    universe: list[str]
    days_evaluated: int
    strategies_run: list[str]
    ml_cagr_pct: float
    ml_sharpe_ratio: float
    ml_max_drawdown_pct: float
    momentum_cagr_pct: float
    momentum_sharpe_ratio: float
    momentum_max_drawdown_pct: float
    status: str
    evidence_path: str


def run_daily_pipeline(
    target_date: date | None = None,
    universe: list[str] | None = None,
    history_days: int = 252,
    output_dir: Path | None = None,
) -> DailyPipelineSummary:
    """Run the complete daily quantitative pipeline.

    Args:
        target_date: The reference date for the daily execution (defaults to today).
        universe: List of equity symbols to evaluate (defaults to NIFTY core).
        history_days: Number of historical trading days to include (default 252).
        output_dir: Path where reports and evidence artifacts are stored.

    Returns:
        DailyPipelineSummary containing execution metrics and outcome.
    """
    if target_date is None:
        target_date = datetime.now(UTC).date()
    if universe is None:
        universe = ["INFY", "TCS", "RELIANCE", "HDFCBANK", "ICICIBANK"]
    if output_dir is None:
        output_dir = PROJECT_ROOT / "logs" / "daily_runs"

    output_dir.mkdir(parents=True, exist_ok=True)
    run_timestamp = datetime.now(UTC)
    date_str = target_date.isoformat()

    logger.info("=" * 70)
    logger.info("QuantOS Automated Daily Pipeline — %s", date_str)
    logger.info("Universe: %s | Historical Days: %d", universe, history_days)
    logger.info("=" * 70)

    # 1. Generate Point-in-Time Data for Universe
    # No provider call happens here. Naming the source is mandatory: an operator reading these
    # logs must never conclude that real NSE prices were ingested.
    logger.warning(
        "Phase 1: Generating %s bars. %s",
        RuntimeDataSource.SYNTHETIC,
        describe(RuntimeDataSource.SYNTHETIC),
    )
    dataset = {}
    for idx, symbol in enumerate(universe):
        drift = 0.0008 if idx % 2 == 0 else -0.0002
        volatility = 0.015 + (idx * 0.003)
        bars_container = SyntheticDataGenerator.generate_equity_bars(
            symbol=symbol,
            start_date=date(2025, 1, 1),
            days=history_days,
            initial_price=1000.0 + (idx * 500.0),
            drift=drift,
            volatility=volatility,
            seed=42 + idx,
        )
        dataset[symbol] = bars_container.bars

    logger.info(
        "Generated %d %s bars per symbol across %d symbols.",
        history_days,
        RuntimeDataSource.SYNTHETIC,
        len(universe),
    )

    # 2. Risk Governor Setup
    risk_limits = RiskLimits(
        max_position_weight=0.35,
        max_daily_drawdown_pct=0.04,
        max_total_drawdown_pct=0.15,
        min_cash_buffer_pct=0.05,
    )
    governor = PreTradeRiskGovernor(limits=risk_limits)

    # 3. Strategy 1: ML Rolling Ridge Model
    logger.info("Phase 2: Training & evaluating ML-Driven Rolling Ridge Model...")
    ml_strategy = MLEquityStrategy(
        name="MLEquity_RollingRidge_Daily",
        params={
            "train_window": 60,
            "top_n": 2,
            "confidence_threshold": 0.52,
            "l2_penalty": 1.0,
        },
    )
    ml_engine = BacktestEngine(
        strategy=ml_strategy,
        initial_cash=Decimal("1000000.00"),
        risk_governor=governor,
        slippage_bps=5.0,
    )
    ml_result = ml_engine.run(dataset)
    ml_metrics = PerformanceMetrics.calculate(ml_result.equity_curve, ml_result.fills)

    logger.info(
        "ML Strategy Results: CAGR=%.2f%%, Sharpe=%.2f, MaxDD=%.2f%%, Trades=%d",
        ml_metrics.cagr_pct * 100,
        ml_metrics.sharpe_ratio,
        ml_metrics.max_drawdown_pct * 100,
        ml_metrics.total_trades,
    )

    # 4. Strategy 2: Dual Momentum Baseline
    logger.info("Phase 3: Evaluating Momentum Baseline Strategy...")
    momentum_strategy = EquityDualMomentumStrategy(
        name="EquityDualMomentum_Daily",
        params={"lookback_fast": 10, "lookback_slow": 30, "top_n": 2},
    )
    mom_engine = BacktestEngine(
        strategy=momentum_strategy,
        initial_cash=Decimal("1000000.00"),
        risk_governor=governor,
        slippage_bps=5.0,
    )
    mom_result = mom_engine.run(dataset)
    mom_metrics = PerformanceMetrics.calculate(mom_result.equity_curve, mom_result.fills)

    logger.info(
        "Momentum Strategy Results: CAGR=%.2f%%, Sharpe=%.2f, MaxDD=%.2f%%, Trades=%d",
        mom_metrics.cagr_pct * 100,
        mom_metrics.sharpe_ratio,
        mom_metrics.max_drawdown_pct * 100,
        mom_metrics.total_trades,
    )

    # 5. Generate and Persist Tearsheets & Evidence
    logger.info("Phase 4: Generating daily tearsheets and immutable evidence logs...")
    ml_tearsheet = TearsheetGenerator.generate_markdown(
        ml_result, ml_metrics, strategy_name=ml_strategy.name
    )
    mom_tearsheet = TearsheetGenerator.generate_markdown(
        mom_result, mom_metrics, strategy_name=momentum_strategy.name
    )

    daily_report_path = output_dir / f"daily_report_{date_str}.md"
    with open(daily_report_path, "w", encoding="utf-8") as f:
        f.write(f"# QuantOS Daily Automated Report — {date_str}\n\n")
        f.write(f"> **DATA SOURCE: {RuntimeDataSource.SYNTHETIC}.** ")
        f.write(describe(RuntimeDataSource.SYNTHETIC) + "\n\n")
        f.write(f"Generated at: {run_timestamp.isoformat()}\n\n")
        f.write(f"Universe: {', '.join(universe)}\n\n")
        f.write("## 1. Machine Learning Strategy Tearsheet\n\n")
        f.write(ml_tearsheet)
        f.write("\n\n---\n\n")
        f.write("## 2. Momentum Baseline Strategy Tearsheet\n\n")
        f.write(mom_tearsheet)

    summary = DailyPipelineSummary(
        execution_date=date_str,
        timestamp_utc=run_timestamp.isoformat(),
        data_source=str(RuntimeDataSource.SYNTHETIC),
        data_source_disclosure=describe(RuntimeDataSource.SYNTHETIC),
        universe=universe,
        days_evaluated=history_days,
        strategies_run=[ml_strategy.name, momentum_strategy.name],
        ml_cagr_pct=round(ml_metrics.cagr_pct * 100, 2),
        ml_sharpe_ratio=round(ml_metrics.sharpe_ratio, 2),
        ml_max_drawdown_pct=round(ml_metrics.max_drawdown_pct * 100, 2),
        momentum_cagr_pct=round(mom_metrics.cagr_pct * 100, 2),
        momentum_sharpe_ratio=round(mom_metrics.sharpe_ratio, 2),
        momentum_max_drawdown_pct=round(mom_metrics.max_drawdown_pct * 100, 2),
        status="SUCCESS",
        evidence_path=str(daily_report_path),
    )

    json_path = output_dir / f"daily_summary_{date_str}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(asdict(summary), f, indent=2)

    logger.info("Daily report saved: %s", daily_report_path)
    logger.info("Daily summary JSON: %s", json_path)
    logger.info("=" * 70)
    logger.info(
        "QuantOS Daily Pipeline completed successfully on %s data.",
        RuntimeDataSource.SYNTHETIC,
    )
    logger.info("=" * 70)

    return summary


def main() -> int:
    """CLI entrypoint for daily pipeline execution."""
    parser = argparse.ArgumentParser(description="QuantOS Automated Daily Pipeline Runner")
    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Target date in YYYY-MM-DD format (defaults to current UTC date)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=252,
        help="Number of historical days to evaluate (default 252)",
    )
    parser.add_argument(
        "--universe",
        type=str,
        nargs="+",
        default=None,
        help="Universe symbols (e.g. INFY TCS RELIANCE)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help="Directory to save reports and evidence",
    )

    args = parser.parse_args()

    target_date = None
    if args.date:
        try:
            target_date = date.fromisoformat(args.date)
        except ValueError:
            logger.error("Invalid date format '%s'. Expected YYYY-MM-DD.", args.date)
            return 1

    out_path = Path(args.output_dir) if args.output_dir else None

    try:
        summary = run_daily_pipeline(
            target_date=target_date,
            universe=args.universe,
            history_days=args.days,
            output_dir=out_path,
        )
        print(f"\n[PIPELINE SUCCESS] Daily run complete for {summary.execution_date}.")
        print(f"Report: {summary.evidence_path}")
        return 0
    except Exception as e:
        logger.exception("Daily pipeline failed with uncaught exception: %s", e)
        return 2


if __name__ == "__main__":
    sys.exit(main())
