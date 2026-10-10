from enum import StrEnum

from pydantic import BaseModel, Field

from .company import ComplianceStatus, DataStatus

PERFORMANCE_NOT_COMPUTED = (
    "QuantOS has not back-tested this basket, so no return or risk figure is shown."
)
NO_REBALANCES_RECORDED = "No rebalances have been recorded yet."


class PriceStatus(StrEnum):
    """Where a share price came from. A price that nobody measured is never shown."""

    SAMPLE = "SAMPLE"
    NOT_AVAILABLE = "NOT_AVAILABLE"


class PerformanceStatus(BaseModel):
    """Says in words why a basket shows no return or risk figure."""

    status: str = "NOT_COMPUTED"
    message: str = PERFORMANCE_NOT_COMPUTED


class BasketConstituent(BaseModel):
    ticker: str
    symbol: str
    company_name: str | None = None
    sector: str | None = None
    weight: float = Field(..., ge=0.0, le=1.0, description="Target portfolio weight (0.0 to 1.0)")
    current_price: float | None = None
    market_cap: float | None = None
    price_status: PriceStatus = PriceStatus.NOT_AVAILABLE
    aaoifi_status: ComplianceStatus | None = Field(
        default=None,
        description="Screening result for this stock; empty when it is not in the sample",
    )
    tasis_status: ComplianceStatus | None = None
    data_status: DataStatus | None = Field(
        default=None,
        description="How far the figures behind the screening result have been checked",
    )


class TearSheetMetrics(BaseModel):
    """Return and risk figures. None of them is computed yet, so every one is empty."""

    cagr: float | None = None
    expected_cagr: float | None = None
    annualized_volatility: float | None = None
    sharpe_ratio: float | None = None
    expected_sharpe: float | None = None
    max_drawdown: float | None = None
    risk_free_rate: float | None = None
    beta: float | None = None
    dividend_yield: float | None = None
    weighted_purification_ratio: float | None = None
    performance: PerformanceStatus = Field(default_factory=PerformanceStatus)


class RebalanceLog(BaseModel):
    date: str
    action: str
    notes: str
    changes: list[str] | None = None


class SectorAllocation(BaseModel):
    sector: str
    weight: float
    weight_pct: float


class BasketSummary(BaseModel):
    id: str
    name: str
    thesis: str
    category: str
    constituent_count: int
    expected_cagr: float | None = None
    expected_sharpe: float | None = None
    cagr: float | None = None
    sharpe_ratio: float | None = None
    annualized_volatility: float | None = None
    max_drawdown: float | None = None
    dividend_yield: float | None = Field(
        default=None, description="Weighted from the screening rows; empty if any stock is missing"
    )
    weighted_purification_ratio: float | None = None
    minimum_investment: float | None = Field(
        default=None,
        description="One share of each stock at its sample price; empty if any price is missing",
    )
    latest_valuation: float | None = None
    performance: PerformanceStatus = Field(default_factory=PerformanceStatus)
    constituents: list[BasketConstituent]


class BasketDetail(BasketSummary):
    tear_sheet: TearSheetMetrics
    sector_allocations: list[SectorAllocation]
    rebalance_logs: list[RebalanceLog] = Field(
        default_factory=list, description="Older name of rebalance_history; always empty"
    )
    rebalance_history: list[RebalanceLog] = Field(default_factory=list)
    history_status: str = "NONE_RECORDED"
    history_message: str = NO_REBALANCES_RECORDED


class BasketExportRequest(BaseModel):
    broker: str = Field(
        default="zerodha", description="Indian broker format: zerodha, upstox, groww, or angelone"
    )
    capital: float = Field(default=50000.0, gt=0.0, description="Target investment capital in INR")
    order_type: str = Field(default="MARKET", description="Order execution type: MARKET or LIMIT")


class BrokerOrder(BaseModel):
    symbol: str
    ticker: str
    shares: int
    price: float
    allocation_amount: float
    weight: float
    order_type: str
    product: str
    order_line: str


class BasketExportResponse(BaseModel):
    basket_id: str
    basket_name: str
    broker: str
    target_capital: float
    total_allocated_capital: float
    residual_cash: float
    order_count: int
    orders: list[BrokerOrder]
    csv_content: str
    clipboard_payload: str
    warnings: list[str]
