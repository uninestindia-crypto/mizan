"""Inputs for the proof builder: the real TCS figures (six months to 30 Sep 2024, consolidated) and small variants."""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from typing import Any

from quant_system.shariah.services.activity_check import (
    ActivityResult,
    ActivityStatus,
    check_activity,
)
from quant_system.shariah.services.proof_types import (
    FigureIn,
    FilingIn,
    MarketValueIn,
    ProofInputs,
)

CRORE = Decimal(10_000_000)

#: key -> (label, xbrl tag, value in rupees). Real figures from the filing; see the fixture README.
TCS_FIGURES: dict[str, tuple[str, str, int]] = {
    "total_assets": ("Total assets", "Assets", 1_611_240_000_000),
    "borrowings_noncurrent": ("Borrowings, non-current", "BorrowingsNoncurrent", 0),
    "borrowings_current": ("Borrowings, current", "BorrowingsCurrent", 0),
    "cash_and_equivalents": ("Cash and cash equivalents", "CashAndCashEquivalents", 81_550_000_000),
    "other_bank_balances": (
        "Other bank balances",
        "BankBalanceOtherThanCashAndCashEquivalents",
        85_780_000_000,
    ),
    "current_investments": ("Investments, current", "CurrentInvestments", 357_920_000_000),
    "noncurrent_investments": ("Investments, non-current", "NoncurrentInvestments", 2_890_000_000),
    "trade_receivables_current": (
        "Trade receivables, current",
        "TradeReceivablesCurrent",
        577_100_000_000,
    ),
    "trade_receivables_noncurrent": (
        "Trade receivables, non-current",
        "TradeReceivablesNoncurrent",
        1_480_000_000,
    ),
    "revenue_from_operations": (
        "Revenue from operations",
        "RevenueFromOperations",
        1_268_720_000_000,
    ),
    "other_income": ("Other income", "OtherIncome", 16_910_000_000),
    "interest_income_adjustment": (
        "Interest income (cash-flow adjustment)",
        "AdjustmentsForInterestIncome",
        15_860_000_000,
    ),
}


def figures(**rupees: int | None) -> dict[str, FigureIn]:
    """The TCS figures, with any key overridden by a rupee value, or removed when given None."""
    chosen = {
        k: (label, tag, rupees.get(k, value)) for k, (label, tag, value) in TCS_FIGURES.items()
    }
    return {
        key: FigureIn(key, label, tag, Decimal(value))
        for key, (label, tag, value) in chosen.items()
        if value is not None
    }


def clean_figures() -> dict[str, FigureIn]:
    """TCS with receivables and investments low enough that both standards pass."""
    return figures(trade_receivables_current=10_000_000_000, current_investments=100_000_000_000)


def filing() -> FilingIn:
    return FilingIn(
        source_url="https://nsearchives.nseindia.com/corporate/xbrl/INDAS_112733_1265368_10102024065944.xml",
        detail_url="https://nsearchives.nseindia.com/archives/financial_results/example.html",
        period_end="2024-09-30",
        period_label="Six months ended 30 Sep 2024",
        filed_on="2024-10-10",
        consolidated=True,
        audited=False,
        sha256="ab" * 32,
        tie_out=(
            {
                "name": "Assets add up",
                "ok": True,
                "detail": "Current plus non-current equals total assets.",
            },
        ),
        tie_out_ok=True,
    )


def market_value(crore: int = 1_300_000) -> MarketValueIn:
    return MarketValueIn(
        Decimal(crore), 3_620_000_000, "Average close from 1 Oct 2021 to 30 Sep 2024"
    )


def activity(
    group: str | None = "Information Technology", segments: tuple[str, ...] = ()
) -> ActivityResult:
    return check_activity("Tata Consultancy Services Limited", group, segments, None)


def tcs(**overrides: Any) -> ProofInputs:
    base = ProofInputs(
        symbol="TCS",
        company_name="Tata Consultancy Services Limited",
        activity=activity(),
        data_status="VERIFIED_FILING",
        screened_at="2026-10-07T06:00:00Z",
        filing=filing(),
        figures=figures(),
        market_value=market_value(),
    )
    return replace(base, **overrides)


def failing_activity() -> ActivityResult:
    return check_activity("United Breweries Limited", "Fast Moving Consumer Goods", (), None)


def unconfirmed_activity() -> ActivityResult:
    result = check_activity("Example Foods", "Fast Moving Consumer Goods", (), None)
    assert result.status is ActivityStatus.NOT_CONFIRMED
    return result
