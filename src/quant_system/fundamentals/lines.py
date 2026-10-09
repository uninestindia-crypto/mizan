"""The lines of a results filing that are read, by plain key, with the XBRL tag each one comes from."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final


@dataclass(frozen=True)
class Spec:
    key: str
    tags: tuple[str, ...]  # in order of preference; the first one filed is used
    label: str


_REGULATORY: Final = (
    "NetMovementInRegulatoryDeferralAccountBalances"
    "RelatedToProfitOrLossAndTheRelatedDeferredTaxMovement"
)
_ASSOCIATES: Final = "ShareOfProfitLossOfAssociatesAndJointVenturesAccountedForUsingEquityMethod"
_EPS_TOTAL: Final = "BasicEarningsLossPerShareFromContinuingAndDiscontinuedOperations"
_EPS_CONTINUING: Final = "BasicEarningsLossPerShareFromContinuingOperations"

QUARTER_SPECS: Final = (
    Spec("revenue_from_operations", ("RevenueFromOperations",), "Revenue from operations"),
    Spec("other_income", ("OtherIncome",), "Other income"),
    Spec("total_income", ("Income",), "Total income"),
    Spec("expenses", ("Expenses",), "Total expenses"),
    Spec("finance_costs", ("FinanceCosts",), "Finance costs"),
    Spec("depreciation", ("DepreciationDepletionAndAmortisationExpense",), "Depreciation"),
    Spec("exceptional_items", ("ExceptionalItemsBeforeTax",), "Exceptional items before tax"),
    Spec("profit_before_tax", ("ProfitBeforeTax",), "Profit before tax"),
    Spec("tax_expense", ("TaxExpense",), "Tax expense"),
    Spec(
        "discontinued_after_tax",
        ("ProfitLossFromDiscontinuedOperationsAfterTax",),
        "Profit from discontinued operations",
    ),
    Spec("associates_share", (_ASSOCIATES,), "Share of profit of associates"),
    Spec("regulatory_movement", (_REGULATORY,), "Regulatory deferral movement"),
    Spec("profit_for_period", ("ProfitLossForPeriod",), "Profit for the period"),
    Spec(
        "owners_profit",
        ("ProfitOrLossAttributableToOwnersOfParent",),
        "Profit for the owners of the company",
    ),
    Spec(
        "minority_profit",
        ("ProfitOrLossAttributableToNonControllingInterests",),
        "Profit for minority shareholders",
    ),
    Spec("paid_up_capital", ("PaidUpValueOfEquityShareCapital",), "Paid-up equity capital"),
    Spec("face_value", ("FaceValueOfEquityShareCapital",), "Face value per share"),
    Spec("eps", (_EPS_TOTAL, _EPS_CONTINUING), "Earnings per share (basic)"),
)

BALANCE_SPECS: Final = (
    Spec("total_assets", ("Assets",), "Total assets"),
    Spec("current_assets", ("CurrentAssets",), "Current assets"),
    Spec("noncurrent_assets", ("NoncurrentAssets",), "Non-current assets"),
    Spec("equity_total", ("Equity",), "Total equity"),
    Spec(
        "equity_owners",
        ("EquityAttributableToOwnersOfParent",),
        "Equity of the owners of the company",
    ),
    Spec("minority_interest", ("NonControllingInterest",), "Minority interest"),
    Spec("liabilities", ("Liabilities",), "Total liabilities"),
    Spec("equity_and_liabilities", ("EquityAndLiabilities",), "Equity and liabilities"),
    Spec("borrowings_current", ("BorrowingsCurrent",), "Borrowings, current"),
    Spec("borrowings_noncurrent", ("BorrowingsNoncurrent",), "Borrowings, non-current"),
    Spec("cash_and_equivalents", ("CashAndCashEquivalents",), "Cash and cash equivalents"),
)

LABELS: Final = {spec.key: spec.label for spec in (*QUARTER_SPECS, *BALANCE_SPECS)}
