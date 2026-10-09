"""Unit tests for the custom in-house Quant-SLM neural model."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

# Add scripts directory
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from quant_system.research.qlib import (  # noqa: E402
    QuantSLM,
    QuantSLMConfig,
    QuantSLMPrediction,
    run_live_slm_pipeline,
)


def test_quant_slm_initialization_and_forward() -> None:
    config = QuantSLMConfig(input_dim=80, d_model=32, d_ff=64)
    model = QuantSLM(config=config)

    batch_size = 16
    X = np.random.randn(batch_size, 80)
    alpha, p_up, vol = model.forward(X)

    assert alpha.shape == (batch_size,)
    assert p_up.shape == (batch_size,)
    assert vol.shape == (batch_size,)

    # Probability bounds
    assert np.all(p_up >= 0.0) and np.all(p_up <= 1.0)
    # Volatility positivity
    assert np.all(vol > 0.0)


def test_quant_slm_training_step_reduces_loss() -> None:
    config = QuantSLMConfig(input_dim=20, d_model=16, d_ff=32, learning_rate=0.01)
    model = QuantSLM(config=config)

    np.random.seed(42)
    X = np.random.randn(32, 20)
    y = np.random.randn(32) * 0.05

    initial_loss = model.train_step(X, y)
    for _ in range(5):
        later_loss = model.train_step(X, y)

    assert later_loss < initial_loss


def test_quant_slm_weight_save_and_load(tmp_path: Path) -> None:
    config = QuantSLMConfig(input_dim=10, d_model=8, d_ff=16)
    model = QuantSLM(config=config)

    save_path = tmp_path / "model_test.json"
    model.save_weights(save_path)
    assert save_path.exists()

    model2 = QuantSLM(config=config)
    model2.load_weights(save_path)

    # Weights must match exactly
    for k in model.weights:
        np.testing.assert_allclose(model.weights[k], model2.weights[k], rtol=1e-6)


def test_quant_slm_predict_universe() -> None:
    config = QuantSLMConfig(input_dim=10, d_model=8, d_ff=16)
    model = QuantSLM(config=config)

    symbols = ["TCS", "INFY", "RELIANCE"]
    X = np.random.randn(3, 10)
    preds = model.predict_universe(symbols, X)

    assert len(preds) == 3
    for p in preds:
        assert isinstance(p, QuantSLMPrediction)
        assert p.action in ("BUY", "SELL", "HOLD")
        assert 0.0 <= p.direction_prob <= 1.0


def test_live_slm_pipeline_runs_fast_and_safe() -> None:
    result = run_live_slm_pipeline(
        universe=["TCS", "INFY"],
        epochs=3,
        portfolio_capital=100000.0,
    )
    assert "train_time_seconds" in result
    assert result["train_time_seconds"] < 10.0
    assert result["inference_ms"] < 100.0
    assert len(result["predictions"]) == 2


def test_quant_slm_api_status_and_signals() -> None:
    from quant_system.server.v2.router import quant_slm_signals, quant_slm_status

    status = quant_slm_status()
    assert status["model_name"] == "Mizan Quant-SLM (Neural Attention Alpha Engine)"
    assert status["input_dimension"] == 80
    assert "pillars" in status
    assert len(status["pillars"]) == 4

    signals = quant_slm_signals()
    assert "model_name" in signals
    assert "predictions" in signals


def test_quant_slm_copilot_tool() -> None:
    from quant_system.copilot.registry import ToolContext
    from quant_system.copilot.tools_user import quant_slm_signals

    ctx = ToolContext()
    res = quant_slm_signals(ctx, {"symbols": ["RELIANCE", "TCS"]})
    assert res.ok is True
    assert "model" in res.data or "status" in res.data


def test_deflated_sharpe_ratio_computation() -> None:
    from scripts.run_slm_walk_forward_backtest import compute_deflated_sharpe_ratio

    # Positive SR with 10 trials
    dsr = compute_deflated_sharpe_ratio(
        sharpe=1.8,
        num_trials=10,
        skew=-0.2,
        kurtosis=3.5,
        num_observations=250,
    )
    assert 0.0 <= dsr <= 1.0

    # Low SR should yield near-zero confidence
    dsr_low = compute_deflated_sharpe_ratio(
        sharpe=-1.0,
        num_trials=10,
        skew=0.0,
        kurtosis=3.0,
        num_observations=250,
    )
    assert dsr_low < 0.1


def test_schedule_market_hours_iteration() -> None:
    from scripts.schedule_market_hours_slm import run_scheduled_iteration

    # Force execution even if offline
    ok = run_scheduled_iteration(universe=["TCS"], epochs=1, force=True)
    assert ok is True
