#!/usr/bin/env python3
"""Run the Custom In-House Quant-SLM on Live Market Data (Paper Trading).

CLI entrypoint and wrapper for the core pipeline in `quant_system.research.qlib.pipeline`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from quant_system.research.qlib.pipeline import (  # noqa: E402
    CONVENTIONAL_FINANCIALS,
    build_synthetic_bars,
    compute_indian_statutory_friction,
    get_default_cache_store,
    run_live_slm_pipeline,
)

DEFAULT_CACHE_STORE = get_default_cache_store()

__all__ = [
    "CONVENTIONAL_FINANCIALS",
    "DEFAULT_CACHE_STORE",
    "build_synthetic_bars",
    "compute_indian_statutory_friction",
    "get_default_cache_store",
    "main",
    "run_live_slm_pipeline",
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run Live In-House Quant-SLM Paper Trader.")
    parser.add_argument(
        "--universe",
        nargs="+",
        default=["RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK"],
        help="Universe symbols, or 'NIFTY50' / 'ALL' for the full 50-stock index.",
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=25,
        help="Training epochs from scratch.",
    )
    parser.add_argument(
        "--capital",
        type=float,
        default=1000000.0,
        help="Portfolio capital in INR (default: 10,00,000 INR).",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable market-cache loading and use synthetic bars.",
    )
    parser.add_argument(
        "--sample-step",
        type=int,
        default=8,
        help="Historical sampling step across bars for feature extraction.",
    )
    args = parser.parse_args()

    run_live_slm_pipeline(
        universe=args.universe,
        epochs=args.epochs,
        portfolio_capital=args.capital,
        use_cache=not args.no_cache,
        sample_step=args.sample_step,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
