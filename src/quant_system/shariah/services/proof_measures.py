"""The figures behind each test, with the lower and upper reading the filing allows, ready for the ratio engine."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from quant_system.shariah.services.proof_types import FigureIn, ProofInputs

__all__ = ["Measure", "Measures", "Part", "company_dict", "measures_for"]

CRORE = Decimal(10_000_000)
Row = dict[str, Any]


@dataclass(frozen=True, slots=True)
class Part:
    """One line that counts toward a figure."""

    key: str
    label: str
    xbrl_tag: str | None
    value_inr: Decimal | None
    value_cr: Decimal
    role: str  # "numerator", "denominator" or "derived"

    def as_dict(self, counted_in: str) -> dict[str, Any]:
        return {
            "label": self.label,
            "xbrl_tag": self.xbrl_tag,
            "value_inr": None if self.value_inr is None else format(self.value_inr, "f"),
            "value_cr": float(self.value_cr),
            "role": self.role,
            "counted_in": counted_in,
        }


def _total(parts: tuple[Part, ...]) -> Decimal:
    return sum((p.value_cr for p in parts), Decimal(0))


@dataclass(frozen=True, slots=True)
class Measure:
    """A numerator with the lines behind its lower reading and its upper reading (the same when the figure is exact)."""

    key: str
    low: tuple[Part, ...]
    high: tuple[Part, ...]

    @property
    def low_cr(self) -> Decimal:
        return _total(self.low)

    @property
    def high_cr(self) -> Decimal:
        return _total(self.high)

    def lines(self) -> list[dict[str, Any]]:
        """Every line used by either reading, each saying which reading counts it."""
        low_keys, high_keys = {p.key for p in self.low}, {p.key for p in self.high}
        out: list[dict[str, Any]] = []
        for part in {p.key: p for p in (*self.low, *self.high)}.values():
            both = part.key in low_keys and part.key in high_keys
            counted = "both" if both else ("lower_only" if part.key in low_keys else "upper_only")
            out.append(part.as_dict(counted))
        return out


@dataclass(frozen=True, slots=True)
class Measures:
    numerators: dict[str, Measure]
    assets: tuple[Part, ...]
    revenue: tuple[Part, ...]
    market_value: Part | None

    @property
    def assets_cr(self) -> Decimal:
        return _total(self.assets)

    @property
    def revenue_cr(self) -> Decimal:
        return _total(self.revenue)


def _from_filing(figure: FigureIn, role: str = "numerator") -> Part:
    return Part(
        figure.key, figure.label, figure.xbrl_tag, figure.value_inr, figure.value_inr / CRORE, role
    )


def _pick(
    figures: dict[str, FigureIn] | Any, *keys: str, role: str = "numerator"
) -> tuple[Part, ...]:
    return tuple(_from_filing(figures[k], role) for k in keys if k in figures)


def _impermissible(figures: Any) -> Measure:
    low = _pick(figures, "interest_income_adjustment")
    high = _pick(figures, "other_income")
    if _total(low) > _total(high):
        high = low
    return Measure("impermissible", low, high)


def _filing_measures(inputs: ProofInputs) -> Measures:
    f = inputs.figures
    exact = {
        "debt": _pick(f, "borrowings_noncurrent", "borrowings_current"),
        "receivables": _pick(f, "trade_receivables_current", "trade_receivables_noncurrent"),
    }
    cash_low = _pick(f, "cash_and_equivalents", "other_bank_balances")
    cash_high = (*cash_low, *_pick(f, "current_investments", "noncurrent_investments"))
    numerators = {k: Measure(k, v, v) for k, v in exact.items()}
    numerators["cash"] = Measure("cash", cash_low, cash_high)
    numerators["impermissible"] = _impermissible(f)
    return Measures(
        numerators,
        _pick(f, "total_assets", role="denominator"),
        _pick(f, "revenue_from_operations", "other_income", role="denominator"),
        _market_value_part(inputs),
    )


def _market_value_part(inputs: ProofInputs) -> Part | None:
    value = inputs.market_value
    if value is None:
        return None
    return Part("market_value", value.label, None, None, value.average_cr, "derived")


_SAMPLE_LINES = {
    "debt": ("total_debt", "Total interest-bearing debt (sample)"),
    "cash": ("total_cash_and_investments", "Cash, bank and debt securities (sample)"),
    "receivables": ("total_receivables", "Trade receivables (sample)"),
    "impermissible": ("total_impermissible_income", "Interest and prohibited income (sample)"),
}


def _sample_part(row: Row, column: str, label: str, role: str) -> tuple[Part, ...]:
    value = Decimal(str(float(row.get(column) or 0.0)))
    return (Part(column, label, None, None, value, role),)


def _sample_measures(row: dict[str, Any]) -> Measures:
    numerators = {}
    for key, (column, label) in _SAMPLE_LINES.items():
        parts = _sample_part(row, column, label, "numerator")
        numerators[key] = Measure(key, parts, parts)
    mcap = _sample_part(
        row, "avg_36m_market_cap", "36-month average market value (sample)", "derived"
    )
    return Measures(
        numerators,
        _sample_part(row, "total_assets", "Total assets (sample)", "denominator"),
        _sample_part(row, "total_revenue", "Total revenue (sample)", "denominator"),
        mcap[0],
    )


def measures_for(inputs: ProofInputs) -> Measures | None:
    """The figures to screen on: the filing when there is one, else the hand-entered sample, else nothing."""
    if inputs.filing is not None and inputs.figures:
        return _filing_measures(inputs)
    if inputs.sample is not None:
        return _sample_measures(inputs.sample)
    return None


def company_dict(measures: Measures, reading: str) -> dict[str, Any]:
    """The row the ratio engine takes, in crore, for the lower or the upper reading."""

    def pick(key: str) -> float:
        measure = measures.numerators[key]
        return float(measure.low_cr if reading == "low" else measure.high_cr)

    market = measures.market_value.value_cr if measures.market_value else Decimal(0)
    return {
        "sector_compliant": True,
        "total_debt": pick("debt"),
        "total_cash_and_investments": pick("cash"),
        "total_receivables": pick("receivables"),
        "total_impermissible_income": pick("impermissible"),
        "total_assets": float(measures.assets_cr),
        "total_revenue": float(measures.revenue_cr),
        "avg_36m_market_cap": float(market),
    }
