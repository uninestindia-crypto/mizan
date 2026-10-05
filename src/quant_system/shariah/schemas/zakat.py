"""Pydantic schemas for the Equity Zakat Calculation Engine (R6)."""

from enum import StrEnum

from pydantic import BaseModel, Field


class ZakatMethod(StrEnum):
    ACTIVE = "active"
    LONG_TERM = "long_term"


class ZakatCalendar(StrEnum):
    LUNAR = "lunar"
    SOLAR = "solar"


class ZakatHoldingItem(BaseModel):
    ticker: str = Field(..., description="Equity ticker (e.g. TCS.NS or TCS)")
    shares: int = Field(..., gt=0, description="Number of shares held")
    znwa_per_share: float | None = Field(
        default=None,
        description="Zakatable Net Working Assets per share (INR). If omitted, looked up from database.",
    )
    current_price: float | None = Field(
        default=None,
        description="Current price per share (INR). If omitted, looked up from database.",
    )


class ZakatHoldingBreakdown(BaseModel):
    ticker: str
    symbol: str | None = None
    company_name: str | None = None
    shares: int
    current_price: float | None = None
    market_value: float | None = None
    znwa_per_share: float
    zakatable_amount: float
    method_applied: str


class ZakatCalculateRequest(BaseModel):
    method: str = Field(
        default="active",
        description="'active' (100% NLV) or 'long_term' (ZNWA per share)",
    )
    portfolio_value: float | None = Field(
        default=0.0,
        ge=0.0,
        description="Total portfolio market value in INR (used for active method or computed from holdings)",
    )
    cash_balance: float = Field(
        default=0.0,
        ge=0.0,
        description="Uninvested cash / bank balance in INR",
    )
    holdings: list[ZakatHoldingItem] | None = Field(
        default_factory=list,
        description="List of portfolio stock holdings",
    )
    calendar: str = Field(
        default="lunar",
        description="'lunar' (2.500%) or 'solar' (2.577%)",
    )
    custom_nisab_inr: float | None = Field(
        default=None,
        description="Optional custom Nisab threshold (defaults to Silver Nisab ₹53,550.00)",
    )


class ZakatCalculateResponse(BaseModel):
    method: str
    calendar: str
    rate: float
    rate_pct: float
    zakatable_base: float
    portfolio_value: float
    cash_balance: float
    nisab_threshold: float
    is_obligatory: bool
    zakat_due: float
    breakdown: list[ZakatHoldingBreakdown] = Field(default_factory=list)
    exemption_reason: str | None = None
    method_notes: str
