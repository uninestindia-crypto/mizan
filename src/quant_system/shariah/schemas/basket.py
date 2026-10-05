from pydantic import BaseModel, Field


class BasketConstituent(BaseModel):
    ticker: str
    symbol: str
    company_name: str | None = None
    sector: str | None = None
    weight: float = Field(..., ge=0.0, le=1.0, description="Target portfolio weight (0.0 to 1.0)")
    current_price: float | None = None
    market_cap: float | None = None


class TearSheetMetrics(BaseModel):
    cagr: float
    expected_cagr: float
    annualized_volatility: float
    sharpe_ratio: float
    expected_sharpe: float
    max_drawdown: float
    risk_free_rate: float = 0.0675
    beta: float = 1.0
    dividend_yield: float = 0.02
    weighted_purification_ratio: float = 0.007


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
    expected_cagr: float
    expected_sharpe: float
    cagr: float
    sharpe_ratio: float
    annualized_volatility: float
    max_drawdown: float
    dividend_yield: float
    weighted_purification_ratio: float
    minimum_investment: float
    latest_valuation: float
    constituents: list[BasketConstituent]


class BasketDetail(BaseModel):
    id: str
    name: str
    thesis: str
    category: str
    constituent_count: int
    expected_cagr: float
    expected_sharpe: float
    cagr: float
    sharpe_ratio: float
    annualized_volatility: float
    max_drawdown: float
    dividend_yield: float
    weighted_purification_ratio: float
    minimum_investment: float
    latest_valuation: float
    tear_sheet: TearSheetMetrics
    sector_allocations: list[SectorAllocation]
    rebalance_logs: list[RebalanceLog]
    constituents: list[BasketConstituent]


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
