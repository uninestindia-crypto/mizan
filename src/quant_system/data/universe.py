"""Point-in-time universe construction, liquidity screening, and survivorship-bias filtering."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class UniverseMember:
    symbol: str
    effective_from: date
    effective_to: date | None = None
    market_cap_tier: str = "LARGE"
    is_fno_enabled: bool = True


@dataclass
class Universe:
    """Maintains point-in-time eligible asset universes (e.g. NIFTY 50, F&O list)."""

    name: str
    members: list[UniverseMember] = field(default_factory=list)

    def get_eligible_symbols(self, query_date: date) -> list[str]:
        """Returns only symbols that were legitimately active and in the index on the query date."""
        eligible = []
        for m in self.members:
            if m.effective_from <= query_date:
                if m.effective_to is None or query_date <= m.effective_to:
                    eligible.append(m.symbol)
        return eligible


class UniverseFilter:
    """Filters candidate symbols based on quantitative liquidity and volatility criteria."""

    @staticmethod
    def filter_by_min_turnover(
        symbols: Sequence[str],
        daily_turnovers: dict[str, Decimal],
        min_turnover_inr: Decimal,
    ) -> list[str]:
        return [s for s in symbols if daily_turnovers.get(s, Decimal("0")) >= min_turnover_inr]
