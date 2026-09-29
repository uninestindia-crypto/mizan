"""Strategy templates offered in the lab: plain-language descriptions and bounded parameters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

ParamKind = Literal["int", "bool"]
Scope = Literal["stocks", "universe"]


@dataclass(frozen=True, slots=True)
class ParamSpec:
    name: str
    label: str
    kind: ParamKind
    default: int | bool
    help: str
    minimum: int = 0
    maximum: int = 0

    def validate(self, value: Any) -> int | bool:
        if self.kind == "bool":
            if not isinstance(value, bool):
                raise ValueError(f"{self.label} must be on or off")
            return value
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"{self.label} must be a whole number")
        if not self.minimum <= value <= self.maximum:
            raise ValueError(f"{self.label} must be between {self.minimum} and {self.maximum}")
        return value

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "label": self.label,
            "kind": self.kind,
            "default": self.default,
            "min": self.minimum,
            "max": self.maximum,
            "help": self.help,
        }


@dataclass(frozen=True, slots=True)
class Template:
    id: str
    name: str
    summary: str
    how_it_works: str
    fails_when: str
    holding_period: str
    scopes: tuple[Scope, ...]
    params: tuple[ParamSpec, ...]

    def resolve(self, raw: dict[str, Any]) -> dict[str, int | bool]:
        unknown = set(raw) - {p.name for p in self.params}
        if unknown:
            raise ValueError(f"Unknown settings for {self.name}: {', '.join(sorted(unknown))}")
        values = {p.name: p.validate(raw.get(p.name, p.default)) for p in self.params}
        if self.id == "trend" and not values["fast"] < values["slow"]:
            raise ValueError("The fast average must be shorter than the slow average")
        if self.id == "pullback" and not values["entry_below"] < values["exit_above"]:
            raise ValueError("The RSI entry level must be below the exit level")
        return values

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "summary": self.summary,
            "how_it_works": self.how_it_works,
            "fails_when": self.fails_when,
            "holding_period": self.holding_period,
            "scopes": list(self.scopes),
            "params": [p.as_dict() for p in self.params],
        }


TEMPLATES: tuple[Template, ...] = (
    Template(
        id="buy_hold",
        name="Buy and hold",
        summary="Buy once and keep. The yardstick every other idea has to beat.",
        how_it_works=(
            "Invests the money equally across the chosen stocks on the first day and never sells."
        ),
        fails_when="The stocks chosen fall and stay down; there is no exit rule.",
        holding_period="Years",
        scopes=("stocks",),
        params=(),
    ),
    Template(
        id="trend",
        name="Trend following",
        summary="Hold a stock only while its shorter average is above its longer average.",
        how_it_works=(
            "Buys when the fast moving average of closing prices rises above the slow one, and "
            "sells when it drops back below."
        ),
        fails_when=(
            "Prices chop sideways: the averages cross back and forth and every crossing costs "
            "charges and slippage."
        ),
        holding_period="Weeks to months",
        scopes=("stocks",),
        params=(
            ParamSpec(
                "fast", "Fast average (sessions)", "int", 50, "Shorter moving average.", 5, 100
            ),
            ParamSpec(
                "slow", "Slow average (sessions)", "int", 200, "Longer moving average.", 20, 300
            ),
        ),
    ),
    Template(
        id="breakout",
        name="52-week breakout",
        summary="Buy a stock when it closes at a new high; sell when it breaks its recent low.",
        how_it_works=(
            "Buys when the close is above the highest close of the entry window, and sells when the "
            "close falls below the lowest close of the exit window."
        ),
        fails_when="Breakouts reverse quickly (false breakouts), which is common in weak markets.",
        holding_period="Weeks to months",
        scopes=("stocks",),
        params=(
            ParamSpec(
                "entry_lookback", "Entry window (sessions)", "int", 252, "New-high window.", 20, 252
            ),
            ParamSpec(
                "exit_lookback", "Exit window (sessions)", "int", 50, "New-low window.", 10, 100
            ),
        ),
    ),
    Template(
        id="momentum",
        name="Momentum rotation",
        summary="Each month, hold the stocks that rose the most over the past year.",
        how_it_works=(
            "On every rebalance day, ranks the stocks by their return over the lookback window "
            "(skipping the most recent sessions), holds the top N in equal amounts, and sells the "
            "ones that dropped out."
        ),
        fails_when=(
            "Leadership changes abruptly (momentum crashes), and in sideways markets where "
            "monthly turnover costs eat the gains."
        ),
        holding_period="Months",
        scopes=("universe", "stocks"),
        params=(
            ParamSpec(
                "lookback",
                "Lookback (sessions)",
                "int",
                252,
                "Return window used to rank.",
                63,
                252,
            ),
            ParamSpec(
                "skip", "Skip recent (sessions)", "int", 21, "Ignore the latest sessions.", 0, 21
            ),
            ParamSpec("top_n", "Stocks held", "int", 10, "How many to hold at once.", 3, 30),
            ParamSpec(
                "rebalance", "Rebalance every (sessions)", "int", 21, "21 is about monthly.", 5, 63
            ),
            ParamSpec(
                "trend_filter",
                "Only above 200-day average",
                "bool",
                False,
                "Skip stocks trading below their 200-day average.",
            ),
        ),
    ),
    Template(
        id="pullback",
        name="Pullback (RSI)",
        summary="Buy a dip in a rising stock and sell into the bounce.",
        how_it_works=(
            "Buys when the RSI falls below the entry level (optionally only while the stock is above "
            "its 200-day average) and sells when RSI rises above the exit level or after the "
            "maximum holding period."
        ),
        fails_when="A dip keeps falling: the rule has no stop-loss beyond the time limit.",
        holding_period="Days to weeks",
        scopes=("stocks",),
        params=(
            ParamSpec(
                "rsi_period", "RSI period (sessions)", "int", 14, "Length of the RSI.", 2, 30
            ),
            ParamSpec("entry_below", "Buy when RSI below", "int", 30, "Oversold level.", 5, 45),
            ParamSpec("exit_above", "Sell when RSI above", "int", 55, "Recovery level.", 40, 80),
            ParamSpec("max_hold", "Maximum hold (sessions)", "int", 20, "Time exit.", 5, 60),
            ParamSpec(
                "trend_filter",
                "Only above 200-day average",
                "bool",
                True,
                "Only buy dips in stocks above their 200-day average.",
            ),
        ),
    ),
)

_BY_ID = {template.id: template for template in TEMPLATES}


def get_template(template_id: str) -> Template:
    try:
        return _BY_ID[template_id]
    except KeyError as err:
        raise ValueError(f"Unknown strategy template: {template_id}") from err
