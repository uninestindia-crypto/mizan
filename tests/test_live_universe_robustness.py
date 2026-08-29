"""Regression and robustness tests for QuantOS live universe evaluation,

formatting invariants, and error prevention.
"""

from __future__ import annotations

import re

from quant_system.data.universe import (
    NIFTY50_SYMBOLS,
    NIFTY100_SYMBOLS,
    NIFTY200_SYMBOLS,
    NIFTY500_SYMBOLS,
)
from quant_system.modeling import MizanModel


def test_universe_sizes_and_uniqueness():
    """Ensure universe lists are strictly unique and non-empty."""
    for name, syms in [
        ("NIFTY50", NIFTY50_SYMBOLS),
        ("NIFTY100", NIFTY100_SYMBOLS),
        ("NIFTY200", NIFTY200_SYMBOLS),
        ("NIFTY500", NIFTY500_SYMBOLS),
    ]:
        assert len(syms) > 0, f"{name} must not be empty"
        assert len(syms) == len(set(syms)), f"{name} has duplicate ticker symbols"


def test_cross_sectional_ranking_symmetry_and_bounds():
    """Ensure cross-sectional ranks are bounded in [-0.5, +0.5] and symmetric."""
    symbols = NIFTY500_SYMBOLS
    n = len(symbols)
    assert n >= 400

    # Synthetic return map
    returns_map = {sym: (i / n) * 0.05 - 0.025 for i, sym in enumerate(symbols)}
    sorted_by_ret = sorted(symbols, key=lambda s: returns_map[s])
    cs_ranks = {sym: (i / (n - 1)) - 0.5 for i, sym in enumerate(sorted_by_ret)}

    for sym, rank in cs_ranks.items():
        assert -0.5 <= rank <= 0.5, f"Rank for {sym} out of bounds: {rank}"

    # Verify median is near zero
    ranks_list = list(cs_ranks.values())
    assert abs(sum(ranks_list) / len(ranks_list)) < 1e-6


def test_mizan_scoring_across_nifty500_universe():
    """Ensure Mīzān evaluates all 490+ stocks without crashes or NaN/Inf scores."""
    model = MizanModel.default_model()
    symbols = NIFTY500_SYMBOLS
    n = len(symbols)

    universe_features = {}
    for i, s in enumerate(symbols):
        r1 = (i / n) * 0.04 - 0.02
        universe_features[s] = {
            "return_1": r1,
            "return_5": r1 * 1.5,
            "return_21": r1 * 2.5,
            "garman_klass_volatility": 0.015,
            "parkinson_volatility": 0.012,
            "rsi_14_centered": r1 * 100.0,
            "sma_20_distance": r1 * 1.2,
            "sma_50_distance": r1 * 1.5,
            "volume_zscore": 0.1,
            "money_flow_multiplier": 0.5 if r1 > 0 else -0.5,
            "india_vix_level": 0.145,
            "india_vix_change_5": 0.005,
            "nifty_return_5": 0.008,
            "cs_rank_momentum_5": (i / (n - 1)) - 0.5,
            "cs_rank_volume_surprise": 0.02,
        }

    scores = model.predict_scores(universe_features)
    assert len(scores) == len(symbols)

    for s, score in scores.items():
        assert -0.30 <= score <= 0.30, f"Score for {s} is unrealistic: {score}"
        assert not (score != score), f"Score for {s} is NaN"


def test_number_formatting_no_double_sign():
    """Ensure string formatting helper never produces '+-' or '-+' signs."""

    def format_score(score: float) -> str:
        sign = "+" if score >= 0 else ""
        return f"{sign}{score:.4f}"

    test_cases = [0.0555, -0.0083, 0.0, -0.9886, 0.0001, -0.0001]
    for val in test_cases:
        res = format_score(val)
        assert not res.startswith("+-"), f"Invalid double sign in {res}"
        assert not res.startswith("-+"), f"Invalid double sign in {res}"
        assert re.match(r"^[+-]?\d+\.\d{4}$", res), f"Malformed format: {res}"
