from dataclasses import dataclass, field


@dataclass
class ConstituentModel:
    ticker: str
    symbol: str
    weight: float
    company_name: str | None = None
    sector: str | None = None
    current_price: float | None = None


@dataclass
class BasketModel:
    """A basket as defined: its name, thesis and holdings. It carries no return or risk figures."""

    id: str
    name: str
    thesis: str
    category: str
    constituents: list[ConstituentModel] = field(default_factory=list)
