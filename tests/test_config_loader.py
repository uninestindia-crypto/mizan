"""Tests for safe YAML configuration loading and validation."""

from pathlib import Path

import pytest

from quant_system.config.loader import ConfigLoader
from quant_system.risk.checks import RiskLimits


def test_load_risk_limits_yaml() -> None:
    config_path = Path(__file__).parent.parent / "configs" / "risk_limits.yaml"
    limits = ConfigLoader.load_risk_limits(config_path)

    assert isinstance(limits, RiskLimits)
    assert limits.max_position_weight == 0.25
    assert limits.max_daily_drawdown_pct == 0.03
    assert limits.max_total_drawdown_pct == 0.10
    assert limits.min_cash_buffer_pct == 0.05
    assert limits.max_allowed_spread_pct == 0.015
    assert limits.allow_naked_short is False


def test_load_strategies_yaml() -> None:
    config_path = Path(__file__).parent.parent / "configs" / "strategies.yaml"
    strats = ConfigLoader.load_strategies_config(config_path)

    assert "equity_momentum" in strats
    assert strats["equity_momentum"]["enabled"] is True
    assert "options_straddle" in strats
    assert strats["options_straddle"]["underlying"] == "NIFTY"


def test_config_loader_missing_file() -> None:
    with pytest.raises(FileNotFoundError):
        ConfigLoader.load_yaml("non_existent_config_file.yaml")
