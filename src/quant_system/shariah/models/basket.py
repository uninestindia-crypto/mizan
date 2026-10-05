from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class ConstituentModel:
    ticker: str
    symbol: str
    weight: float
    company_name: Optional[str] = None
    sector: Optional[str] = None
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
    constituents: List[ConstituentModel] = field(default_factory=list)
