"""Shared fakes for the Copilot tests: a tiny market index, a Shariah sample, and a ready-made tool context."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from quant_system.copilot.tools import ToolContext
from quant_system.market.index import SymbolNotFoundError

SAMPLE_ROW: dict[str, Any] = {
    "ticker": "AAA.NS",
    "symbol": "AAA",
    "company_name": "Alpha Ltd",
    "sector": "Information Technology",
    "industry": "Software",
    "business_summary": "software services",
    "sector_compliant": 1,
    "sector_failure_reason": None,
    "total_assets": 1000.0,
    "total_debt": 50.0,
    "total_cash_and_investments": 100.0,
    "total_receivables": 120.0,
    "avg_36m_market_cap": 4000.0,
    "total_impermissible_income": 1.0,
    "total_revenue": 500.0,
    "purification_ratio": 0.002,
    "pe_ratio": 24.5,
    "pb_ratio": 6.1,
    "dividend_yield": 0.021,
    "market_cap": 4200.0,
    "reporting_period": "Q4 FY24 Audited Consolidated",
    "filing_date": "2024-04-12",
    "source_document": "BSE/NSE Annual Audited Report",
}


@dataclass
class FakeSeries:
    symbol: str
    dates: list[str]
    close: np.ndarray


class FakeIndex:
    def __init__(self) -> None:
        self._dates = [f"2026-09-{day:02d}" for day in range(1, 29)]

    def search(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        rows = [
            {"symbol": "AAA", "name": "ALPHA LTD", "is_etf": 0, "last_date": "2026-09-28"},
            {"symbol": "BBB", "name": "BETA LTD", "is_etf": 0, "last_date": "2026-09-28"},
        ]
        return [r for r in rows if query.upper() in r["symbol"] or query.upper() in r["name"]][
            :limit
        ]

    def resolve(self, symbol: str) -> str:
        return symbol.strip().upper()

    def symbol_info(self, symbol: str) -> dict[str, Any]:
        if symbol.upper() not in {"AAA", "BBB"}:
            raise SymbolNotFoundError(symbol)
        return {
            "symbol": symbol.upper(),
            "name": "ALPHA LTD" if symbol.upper() == "AAA" else "BETA LTD",
            "isin": "INE0AAA",
            "instrument_key": "NSE_EQ|INE0AAA",
            "universes": ["liquid"],
            "snapshot": {"turnover_cr": 12.5},
        }

    def stock_stats(self, symbol: str) -> dict[str, Any]:
        return {
            "ret_1m": 0.052,
            "ret_6m": 0.11,
            "ret_1y": 0.2,
            "ret_3y": 0.5,
            "ret_5y": 0.9,
            "vol_1y": 0.25,
            "max_drawdown_1y": -0.14,
            "max_drawdown_all": -0.3,
            "beta_1y": 0.9,
        }

    def bars(self, symbol: str, start: str | None = None, end: str | None = None) -> FakeSeries:
        return FakeSeries(symbol, self._dates, np.linspace(100.0, 128.0, len(self._dates)))


class FakeShariah:
    def company(self, symbol: str) -> dict[str, Any] | None:
        return dict(SAMPLE_ROW) if symbol.upper() == "AAA" else None

    def company_count(self) -> int:
        return 39


def make_context(**overrides: Any) -> ToolContext:
    base: dict[str, Any] = {"index": FakeIndex(), "shariah": FakeShariah()}
    base.update(overrides)
    return ToolContext(**base)
