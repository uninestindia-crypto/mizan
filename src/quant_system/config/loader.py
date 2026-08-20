"""Safe, typed YAML configuration loader for risk limits and strategy parameters."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from quant_system.risk.checks import RiskLimits


class ConfigLoader:
    """Safely loads, validates, and constructs system configuration objects from YAML."""

    @staticmethod
    def load_yaml(file_path: str | Path) -> dict[str, Any]:
        """Loads and parses a YAML file safely using yaml.safe_load."""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {file_path}")

        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if data is None:
            return {}
        if not isinstance(data, dict):
            raise ValueError(
                f"YAML configuration root must be a mapping, got {type(data).__name__}"
            )
        return data

    @classmethod
    def load_risk_limits(cls, file_path: str | Path) -> RiskLimits:
        """Loads and parses pre-trade risk limits from a YAML file."""
        raw_config = cls.load_yaml(file_path)
        global_limits = raw_config.get("global_limits", {})
        options_limits = raw_config.get("options_limits", {})
        slippage_and_spread = raw_config.get("slippage_and_spread", {})

        return RiskLimits(
            max_position_weight=float(global_limits.get("max_position_weight", 0.25)),
            max_daily_drawdown_pct=float(global_limits.get("max_daily_drawdown_pct", 0.03)),
            max_total_drawdown_pct=float(global_limits.get("max_total_drawdown_pct", 0.10)),
            max_portfolio_leverage=float(global_limits.get("max_portfolio_leverage", 1.0)),
            min_cash_buffer_pct=float(global_limits.get("min_cash_buffer_pct", 0.05)),
            max_allowed_spread_pct=float(slippage_and_spread.get("max_allowed_spread_pct", 0.02)),
            allow_naked_short=bool(options_limits.get("allow_naked_short_options", False)),
        )

    @classmethod
    def load_strategies_config(cls, file_path: str | Path) -> dict[str, Any]:
        """Loads strategy configurations from a YAML file."""
        return cls.load_yaml(file_path)
