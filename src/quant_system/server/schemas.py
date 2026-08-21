"""Typed Pydantic schemas for the QuantOS REST API."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from quant_system.data.provenance import RuntimeDataSource, describe


class SyntheticSourcedResponse(BaseModel):
    """Base for results computed from generated bars rather than acquired market data.

    The defaults are deliberately the honest ones for every endpoint that exists today. A future
    endpoint backed by real acquisition must override them explicitly, so the failure mode of
    forgetting is understating realness rather than overstating it.
    """

    data_source: str = Field(default=str(RuntimeDataSource.SYNTHETIC))
    data_source_disclosure: str = Field(default=describe(RuntimeDataSource.SYNTHETIC))


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    request_id: str
    timestamp: str


class ErrorEnvelope(BaseModel):
    error: ErrorDetail


class CSRFTokenResponse(BaseModel):
    csrf_token: str
    expires_at: str
    message: str = "CSRF token issued successfully."


class OperationStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    LOST = "LOST"


class OperationType(StrEnum):
    BACKTEST = "BACKTEST"
    TRAINING = "TRAINING"
    DATA_SYNC = "DATA_SYNC"
    MONTE_CARLO = "MONTE_CARLO"
    PORTFOLIO_OPTIMIZE = "PORTFOLIO_OPTIMIZE"
    CUSTOM = "CUSTOM"


class OperationCreateResponse(BaseModel):
    operation_id: str
    type: OperationType
    status: OperationStatus
    location: str
    message: str
    created_at: str


class OperationResponse(BaseModel):
    operation_id: str
    type: OperationType
    status: OperationStatus
    progress: float = Field(ge=0.0, le=1.0)
    stage: str
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None
    last_heartbeat_at: str | None = None
    result: dict[str, Any] | None = None
    error: dict[str, Any] | None = None
    cancellation_requested: bool = False
    idempotency_key: str | None = None


class OperationCancelResponse(BaseModel):
    operation_id: str
    status: OperationStatus
    message: str


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
        default_factory=lambda: ["INFY", "TCS", "RELIANCE", "HDFCBANK", "ICICIBANK"],
        max_length=5,
    )
    days: int = Field(120, ge=10, le=3650)
    initial_cash: float = Field(1000000.0, ge=10000.0)
    slippage_bps: float = Field(5.0, ge=0.0, le=100.0)
    params: dict[str, Any] = Field(default_factory=dict)


class TrainingRunRequest(BaseModel):
    candidate_id: str = "cand_ridge_v1"
    symbols: list[str] = Field(
        default_factory=lambda: ["INFY", "TCS", "RELIANCE", "HDFCBANK", "ICICIBANK"],
        max_length=5,
    )
    l2_penalty: float = Field(1.0, gt=0.0)
    days: int = Field(252, ge=20, le=3650)
    seed: int = 42


class CustomOperationRequest(BaseModel):
    action: str = "compute"
    duration: float = Field(1.0, ge=0.0, le=300.0)
    message: str = "Custom operation"
    data: dict[str, Any] = Field(default_factory=dict)


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


class BacktestRunResponse(SyntheticSourcedResponse):
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
    market_data_source: str
    market_data_credentials_configured: bool
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
    horizon_days: int = Field(252, ge=20, le=3650)
    initial_capital: float = Field(1000000.0, ge=10000.0)


class MonteCarloResponse(SyntheticSourcedResponse):
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
        default_factory=lambda: ["INFY", "TCS", "RELIANCE", "HDFCBANK", "ICICIBANK"],
        max_length=5,
    )
    days: int = Field(252, ge=30, le=3650)
    risk_free_rate: float = Field(0.07, ge=0.0, le=0.30)


class FrontierPointDTO(BaseModel):
    expected_return: float
    volatility: float
    sharpe_ratio: float
    weights: dict[str, float]


class PortfolioOptimizeResponse(SyntheticSourcedResponse):
    symbols: list[str]
    max_sharpe_point: FrontierPointDTO
    min_variance_point: FrontierPointDTO
    risk_parity_weights: dict[str, float]
    frontier_curve: list[FrontierPointDTO]


# =============================================================================
# Slice 11: 7 Core User Journey DTOs
# =============================================================================


class JourneyMetaDTO(BaseModel):
    id: str
    title: str
    nav_label: str
    description: str
    icon: str
    route_path: str
    badge: str
    data_test: str
    status: str = "ONLINE"


class JourneyListResponse(BaseModel):
    journeys: list[JourneyMetaDTO]
    total_count: int


# Journey 1: Data Ingestion & Manifests
class ManifestItemDTO(BaseModel):
    manifest_id: str
    symbol: str
    start_date: str
    end_date: str
    bar_count: int
    checksum_sha256: str
    provenance: str
    status: str
    zero_lookahead_verified: bool = True
    created_at: str


class ManifestListResponse(BaseModel):
    manifests: list[ManifestItemDTO]
    total_count: int


class DataIngestRequest(BaseModel):
    symbol: str = "INFY"
    start_date: str = "2020-01-01"
    end_date: str = "2025-01-01"
    source: str = "SYNTHETIC"


class DataIngestResponse(BaseModel):
    manifest: ManifestItemDTO
    message: str
    success: bool = True


# Journey 2: Feature Matrix & Labels
class FeatureDefinitionDTO(BaseModel):
    name: str
    formula: str
    category: str
    lookback_bars: int


class FeatureRowDTO(BaseModel):
    timestamp: str
    symbol: str
    features: dict[str, float]
    label_net_return: float | None = None
    label_matured: bool = True
    embargoed: bool = False


class FeatureMatrixResponse(SyntheticSourcedResponse):
    symbol: str
    features_meta: list[FeatureDefinitionDTO]
    rows: list[FeatureRowDTO]
    total_rows: int
    purged_overlap_count: int
    embargo_bars: int


class FeatureExploreRequest(BaseModel):
    symbol: str = "INFY"
    horizon_days: int = Field(5, ge=1, le=60)
    label_friction_bps: float = Field(5.0, ge=0.0, le=50.0)


# Journey 3: Governed Ridge Training
class RidgeBaselineDTO(BaseModel):
    name: str
    annualized_return: float
    sharpe_ratio: float
    sortino_ratio: float
    max_drawdown_pct: float
    accuracy_pct: float
    profit_factor: float


class RidgeCoefficientDTO(BaseModel):
    feature_name: str
    coefficient: float
    interpretation: str


class GovernedRidgeTrainRequest(BaseModel):
    candidate_id: str = "cand_ridge_v1"
    l2_penalty: float = Field(1.0, gt=0.0)
    score_threshold: float = 0.0
    symbols: list[str] = Field(default_factory=lambda: ["INFY", "TCS", "RELIANCE"])


class GovernedRidgeTrainResponse(SyntheticSourcedResponse):
    trial_id: str
    multiplicity_ordinal: int
    total_attempts: int
    verdict: str
    deflated_sharpe: float
    candidate_metrics: RidgeBaselineDTO
    baselines: list[RidgeBaselineDTO]
    coefficients: list[RidgeCoefficientDTO]
    evidence_hash: str


# Journey 4: Single-use Holdout & Stress Testing
class HoldoutGateDTO(BaseModel):
    gate_name: str
    required_threshold: str
    observed_value: str
    status: str  # PASS / FAIL


class StressScenarioDTO(BaseModel):
    scenario_name: str
    shock_description: str
    simulated_drawdown_pct: float
    recovery_days: int
    survival_status: str


class HoldoutEvaluateRequest(BaseModel):
    candidate_id: str = "cand_ridge_v1_opt"
    unlock_token: str = "HOLD_TOKEN_ONE_TIME"
    confirm_single_use: bool = True


class HoldoutEvaluateResponse(SyntheticSourcedResponse):
    candidate_id: str
    holdout_lock_status: str
    verdict: str
    gates: list[HoldoutGateDTO]
    stress_scenarios: list[StressScenarioDTO]
    model_card_markdown: str


# Journey 5: Ledger Accounting
class LedgerReconciliationDTO(BaseModel):
    is_reconciled: bool = True
    total_credits: float
    total_debits: float
    variance: float = 0.0
    journal_entries_count: int


# Journey 6: Shadow Monitor
class ShadowQuoteDTO(BaseModel):
    timestamp: str
    symbol: str
    bid: float
    ask: float
    ltp: float
    volume: int
    latency_ms: float


class ShadowDecisionDTO(BaseModel):
    decision_time: str
    symbol: str
    signal: str
    target_instrument: str
    attributed_fill_price: float | None = None
    matured_pnl: float | None = None


class ShadowMonitorStatusResponse(BaseModel):
    mode: str = "RECORDED_REPLAY"
    is_running: bool = True
    quotes_processed: int
    shadow_decisions_count: int
    broker_orders_submitted: int = 0  # Strictly 0
    average_latency_ms: float
    stream_health: str = "HEALTHY"
    recent_quotes: list[ShadowQuoteDTO]
    recent_decisions: list[ShadowDecisionDTO]


class ShadowControlRequest(BaseModel):
    action: str = Field("start", pattern="^(start|pause|stop)$")
    speed_multiplier: int = Field(5, ge=1, le=50)


class ShadowControlResponse(BaseModel):
    status: str
    message: str


# Journey 7: Paper Pilot
class PaperOrderDTO(BaseModel):
    order_id: str
    symbol: str
    side: str
    requested_qty: int
    filled_qty: int
    limit_price: float
    fill_price: float | None = None
    status: str
    idempotency_token: str


class PaperPositionDTO(BaseModel):
    symbol: str
    quantity: int
    average_entry: float
    current_ltp: float
    unrealized_pnl: float
    portfolio_weight_pct: float


class PaperPilotCampaignResponse(SyntheticSourcedResponse):
    campaign_id: str
    status: str = "ACTIVE"
    allocated_capital: float
    current_equity: float
    unrealized_pnl: float
    realized_pnl: float
    drawdown_buffer_pct: float
    circuit_breaker_triggered: bool = False
    active_positions: list[PaperPositionDTO]
    order_ladder: list[PaperOrderDTO]


class PaperOrderSubmitRequest(BaseModel):
    campaign_id: str = "CAMP_ALPHA_2026"
    symbol: str = "INFY"
    side: str = Field("BUY", pattern="^(BUY|SELL)$")
    quantity: int = Field(100, ge=1)
    limit_price: float = Field(1840.0, gt=0.0)


class PaperOrderSubmitResponse(SyntheticSourcedResponse):
    order: PaperOrderDTO
    message: str
