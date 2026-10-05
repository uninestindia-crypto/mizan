from dataclasses import dataclass, field


@dataclass
class ConstituentModel:
    ticker: str
    symbol: str
    weight: float
    company_name: str | None = None
    sector: str | None = None
    current_price: float = 0.0


@dataclass
class BasketModel:
    id: str
    name: str
    thesis: str
    category: str
    expected_cagr: float
    expected_sharpe: float
    annualized_volatility: float
    max_drawdown: float
    beta: float
    dividend_yield: float
    weighted_purification_ratio: float
    constituents: list[ConstituentModel] = field(default_factory=list)
