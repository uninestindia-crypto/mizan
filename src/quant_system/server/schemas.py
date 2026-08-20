"""Typed Pydantic schemas for the QuantOS REST API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class VersionInfo(BaseModel):
    version: str = "1.0.0"
    name: str = "QuantOS"
    description: str = "Institutional Quantitative Trading & Backtesting System"
    status: str = "ONLINE"


class StrategyInfo(BaseModel):
    name: str
    description: str
    default_params: dict[str, Any]


class RiskLimitsDTO(BaseModel):
    max_position_weight: float = Field(0.25, ge=0.01, le=1.0)
    max_daily_drawdown_pct: float = Field(0.03, ge=0.001, le=0.50)
    max_total_drawdown_pct: float = Field(0.10, ge=0.01, le=0.90)
    max_portfolio_leverage: float = Field(1.0, ge=0.1, le=10.0)
    min_cash_buffer_pct: float = Field(0.05, ge=0.0, le=0.50)
    max_allowed_spread_pct: float = Field(0.015, ge=0.0001, le=0.20)
    allow_naked_short: bool = False


class BacktestRunRequest(BaseModel):
    strategy_name: str = "EquityDualMomentum"
    symbols: list[str] = Field(
        default_factory=lambda: ["INFY", "TCS", "RELIANCE", "HDFCBANK", "ICICIBANK"]
    )
    days: int = Field(120, ge=10, le=1000)
    initial_cash: float = Field(1000000.0, ge=10000.0)
    slippage_bps: float = Field(5.0, ge=0.0, le=100.0)
    params: dict[str, Any] = Field(default_factory=dict)


class SnapshotDTO(BaseModel):
    timestamp: str
    cash: float
    total_market_value: float
    total_equity: float
    realized_pnl: float
    unrealized_pnl: float


class FillDTO(BaseModel):
    fill_id: str
    order_id: str
    symbol: str
    side: str
    quantity: int
    price: float
    fee: float
    timestamp: str


class QuantStatsDTO(BaseModel):
    total_return_pct: float
    cagr_pct: float
    annualized_volatility: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    max_drawdown_pct: float
    max_drawdown_duration_bars: int
    win_rate: float
    profit_factor: float
    total_trades: int
    avg_trade_pnl: float


class BacktestRunResponse(BaseModel):
    initial_cash: float
    final_equity: float
    total_return_pct: float
    total_trades: int
    total_friction_paid: float
    stats: QuantStatsDTO
    equity_curve: list[SnapshotDTO]
    fills: list[FillDTO]
    tearsheet_markdown: str


class OptionStraddleRequest(BaseModel):
    spot_price: float = Field(24500.0, gt=0.0)
    volatility: float = Field(0.18, gt=0.0, le=2.0)
    days_to_expiry: int = Field(7, ge=1, le=90)
    risk_free_rate: float = Field(0.07, ge=0.0, le=0.30)
    quantity: int = Field(25, ge=1)


class OptionGreeksDTO(BaseModel):
    strike: float
    option_type: str
    price: float
    delta: float
    gamma: float
    theta: float
    vega: float
    rho: float


class OptionStraddleResponse(BaseModel):
    underlying: str = "NIFTY"
    spot_price: float
    atm_strike: float
    call_greeks: OptionGreeksDTO
    put_greeks: OptionGreeksDTO
    net_delta: float
    daily_theta_income: float
    total_premium_collected: float
    total_estimated_friction: float


class DiagnosticsReport(BaseModel):
    status: str
    version: str
    python_version: str
    platform: str
    memory_usage_mb: float
    ledger_integrity_verified: bool
    installed_strategies_count: int
    checks_passed: int
    total_checks: int


class MonteCarloRequest(BaseModel):
    strategy_name: str = "EquityDualMomentum"
    num_simulations: int = Field(5000, ge=500, le=50000)
    horizon_days: int = Field(252, ge=20, le=1000)
    initial_capital: float = Field(1000000.0, ge=10000.0)


class MonteCarloResponse(BaseModel):
    num_simulations: int
    horizon_days: int
    initial_capital: float
    expected_final_median: float
    percentile_5th: list[float]
    percentile_25th: list[float]
    percentile_50th: list[float]
    percentile_75th: list[float]
    percentile_95th: list[float]
    var_95_pct: float
    var_99_pct: float
    cvar_95_pct: float
    cvar_99_pct: float
    prob_profit_pct: float
    prob_drawdown_gt_10pct: float
    prob_drawdown_gt_20pct: float
    max_simulated_drawdown_pct: float


class PortfolioOptimizeRequest(BaseModel):
    symbols: list[str] = Field(
        default_factory=lambda: ["INFY", "TCS", "RELIANCE", "HDFCBANK", "ICICIBANK"]
    )
    days: int = Field(252, ge=30, le=1000)
    risk_free_rate: float = Field(0.07, ge=0.0, le=0.30)


class FrontierPointDTO(BaseModel):
    expected_return: float
    volatility: float
    sharpe_ratio: float
    weights: dict[str, float]


class PortfolioOptimizeResponse(BaseModel):
    symbols: list[str]
    max_sharpe_point: FrontierPointDTO
    min_variance_point: FrontierPointDTO
    risk_parity_weights: dict[str, float]
    frontier_curve: list[FrontierPointDTO]
