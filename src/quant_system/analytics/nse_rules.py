"""Effective-dated Indian Exchange Rule Engine for NSE Equities, Futures, and Options.

Enforces point-in-time statutory and exchange fee schedules (STT, GST, SEBI turnover,
Exchange turnover, Stamp duty, Brokerage) with strict selection by trade date.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum

from quant_system.core.domain import Side

_PAISA = Decimal("0.01")


class MarketSegment(StrEnum):
    """Trading segments with distinct tax and fee treatments on NSE."""

    EQUITY_DELIVERY = "EQUITY_DELIVERY"
    EQUITY_INTRADAY = "EQUITY_INTRADAY"
    EQUITY_FUTURES = "EQUITY_FUTURES"
    EQUITY_OPTIONS = "EQUITY_OPTIONS"


class FeeComponent(StrEnum):
    """Statutory, regulatory, exchange, and brokerage fee components."""

    STT = "STT"
    EXCHANGE_TURNOVER = "EXCHANGE_TURNOVER"
    SEBI_TURNOVER = "SEBI_TURNOVER"
    STAMP_DUTY = "STAMP_DUTY"
    GST = "GST"
    BROKERAGE = "BROKERAGE"


class SideBasis(StrEnum):
    """Applicable order sides for a fee component."""

    BUY = "BUY"
    SELL = "SELL"
    BOTH = "BOTH"
    NONE = "NONE"


class RateBasis(StrEnum):
    """Method of computing the fee base."""

    TURNOVER = "TURNOVER"  # price * quantity
    PREMIUM_TURNOVER = "PREMIUM_TURNOVER"  # option premium * quantity
    STATUTORY_CHARGES = "STATUTORY_CHARGES"  # GST base = (Brokerage + Exchange + SEBI)
    FLAT_PER_ORDER = "FLAT_PER_ORDER"  # Flat rupee fee per order execution
    PERCENTAGE_WITH_CAP = "PERCENTAGE_WITH_CAP"  # percentage of turnover capped at max rupee


class RoundingMethod(StrEnum):
    """Statutory and accounting rounding rules."""

    ROUND_HALF_UP_PAISA = "ROUND_HALF_UP_PAISA"  # Standard paisa rounding (0.01)
    ROUND_HALF_UP_RUPEE = "ROUND_HALF_UP_RUPEE"  # Statutory STT contract rounding (1.00)


@dataclass(frozen=True, slots=True)
class DatedExchangeRule:
    """Immutable, effective-dated rule for an exchange or statutory fee component."""

    rule_id: str
    component: FeeComponent
    source_ref: str
    publication_date: date
    effective_from: date
    effective_to: date | None
    venue: str
    segment: MarketSegment
    side_basis: SideBasis
    rate: Decimal
    rate_basis: RateBasis
    cap: Decimal | None = None
    minimum: Decimal | None = None
    rounding_unit: Decimal = _PAISA
    rounding_method: RoundingMethod = RoundingMethod.ROUND_HALF_UP_PAISA
    description: str = ""
    rule_hash: str = ""

    def __post_init__(self) -> None:
        if self.effective_to is not None and self.effective_from > self.effective_to:
            raise ValueError(
                f"Rule {self.rule_id}: effective_from ({self.effective_from}) "
                f"cannot be after effective_to ({self.effective_to})"
            )
        if self.rate < Decimal("0"):
            raise ValueError(f"Rule {self.rule_id}: rate cannot be negative ({self.rate})")

        computed_hash = self._compute_hash()
        if self.rule_hash and self.rule_hash != computed_hash:
            raise ValueError(
                f"Rule {self.rule_id}: provided hash {self.rule_hash} != computed {computed_hash}"
            )
        object.__setattr__(self, "rule_hash", computed_hash)

    def _compute_hash(self) -> str:
        payload = {
            "rule_id": self.rule_id,
            "component": self.component.value,
            "source_ref": self.source_ref,
            "publication_date": self.publication_date.isoformat(),
            "effective_from": self.effective_from.isoformat(),
            "effective_to": self.effective_to.isoformat() if self.effective_to else None,
            "venue": self.venue,
            "segment": self.segment.value,
            "side_basis": self.side_basis.value,
            "rate": str(self.rate),
            "rate_basis": self.rate_basis.value,
            "cap": str(self.cap) if self.cap is not None else None,
            "minimum": str(self.minimum) if self.minimum is not None else None,
            "rounding_unit": str(self.rounding_unit),
            "rounding_method": self.rounding_method.value,
        }
        canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    def is_effective(self, trade_date: date) -> bool:
        """Determines if this rule version is legally in force on the given trade date."""
        if trade_date < self.effective_from:
            return False
        if self.effective_to is not None and trade_date > self.effective_to:
            return False
        return True


@dataclass(frozen=True, slots=True)
class CostBreakdown:
    """Itemized friction breakdown for an executed trade with complete rule attribution."""

    trade_date: date
    segment: MarketSegment
    side: Side
    quantity: int
    price: Decimal
    turnover: Decimal
    brokerage: Decimal
    stt: Decimal
    exchange_turnover: Decimal
    sebi_charges: Decimal
    stamp_duty: Decimal
    gst: Decimal
    slippage: Decimal
    total_statutory_charges: Decimal
    total_fee: Decimal
    total_friction: Decimal
    applied_rule_ids: Mapping[str, str]
    applied_rule_hashes: Mapping[str, str]
    calculation_hash: str

    @property
    def total_cost(self) -> Decimal:
        """Alias for total_friction."""
        return self.total_friction


# ---------------------------------------------------------------------------
# Canonical Master Catalog of Effective-Dated NSE Exchange & Statutory Rules
# ---------------------------------------------------------------------------

_CANONICAL_RULES: list[DatedExchangeRule] = [
    # ------------------ 1. STT (Securities Transaction Tax) ------------------
    # Cash Delivery: 0.1% on BUY and SELL (Finance (No. 2) Act 2004)
    DatedExchangeRule(
        rule_id="STT-EQ-DEL-20041001",
        component=FeeComponent.STT,
        source_ref="Finance (No. 2) Act, 2004, Chapter VII, Item 1",
        publication_date=date(2004, 9, 10),
        effective_from=date(2004, 10, 1),
        effective_to=None,
        venue="NSE",
        segment=MarketSegment.EQUITY_DELIVERY,
        side_basis=SideBasis.BOTH,
        rate=Decimal("0.00100"),  # 0.1%
        rate_basis=RateBasis.TURNOVER,
        rounding_unit=_PAISA,
        rounding_method=RoundingMethod.ROUND_HALF_UP_PAISA,
        description="STT 0.1% on both buy and sell delivery turnover",
    ),
    # Cash Intraday: 0.025% on SELL only (Finance (No. 2) Act 2004)
    DatedExchangeRule(
        rule_id="STT-EQ-INT-20041001",
        component=FeeComponent.STT,
        source_ref="Finance (No. 2) Act, 2004, Chapter VII, Item 2",
        publication_date=date(2004, 9, 10),
        effective_from=date(2004, 10, 1),
        effective_to=None,
        venue="NSE",
        segment=MarketSegment.EQUITY_INTRADAY,
        side_basis=SideBasis.SELL,
        rate=Decimal("0.00025"),  # 0.025%
        rate_basis=RateBasis.TURNOVER,
        rounding_unit=_PAISA,
        rounding_method=RoundingMethod.ROUND_HALF_UP_PAISA,
        description="STT 0.025% on intraday sell turnover",
    ),
    # Futures: 0.0125% on SELL (Finance Act 2016 to 2024-09-30)
    DatedExchangeRule(
        rule_id="STT-FUT-20160601",
        component=FeeComponent.STT,
        source_ref="Finance Act, 2016, Section 236",
        publication_date=date(2016, 5, 14),
        effective_from=date(2016, 6, 1),
        effective_to=date(2024, 9, 30),
        venue="NSE",
        segment=MarketSegment.EQUITY_FUTURES,
        side_basis=SideBasis.SELL,
        rate=Decimal("0.000125"),  # 0.0125%
        rate_basis=RateBasis.TURNOVER,
        rounding_unit=_PAISA,
        rounding_method=RoundingMethod.ROUND_HALF_UP_PAISA,
        description="STT 0.0125% on equity & index futures sell turnover",
    ),
    # Futures: 0.0200% on SELL (Finance (No. 2) Act 2024, effective 2024-10-01)
    DatedExchangeRule(
        rule_id="STT-FUT-20241001",
        component=FeeComponent.STT,
        source_ref="Finance (No. 2) Act, 2024, Section 169 (STT Rate Revision)",
        publication_date=date(2024, 8, 16),
        effective_from=date(2024, 10, 1),
        effective_to=None,
        venue="NSE",
        segment=MarketSegment.EQUITY_FUTURES,
        side_basis=SideBasis.SELL,
        rate=Decimal("0.000200"),  # 0.02%
        rate_basis=RateBasis.TURNOVER,
        rounding_unit=_PAISA,
        rounding_method=RoundingMethod.ROUND_HALF_UP_PAISA,
        description="STT revised to 0.02% on equity & index futures sell turnover",
    ),
    # Options: 0.05% on SELL premium (2019 to 2023-03-31)
    DatedExchangeRule(
        rule_id="STT-OPT-20190901",
        component=FeeComponent.STT,
        source_ref="Finance (No. 2) Act, 2019, Section 188",
        publication_date=date(2019, 8, 1),
        effective_from=date(2019, 9, 1),
        effective_to=date(2023, 3, 31),
        venue="NSE",
        segment=MarketSegment.EQUITY_OPTIONS,
        side_basis=SideBasis.SELL,
        rate=Decimal("0.000500"),  # 0.05%
        rate_basis=RateBasis.PREMIUM_TURNOVER,
        rounding_unit=_PAISA,
        rounding_method=RoundingMethod.ROUND_HALF_UP_PAISA,
        description="STT 0.05% on option sell premium turnover",
    ),
    # Options: 0.0625% on SELL premium (Finance Act 2023, effective 2023-04-01 to 2024-09-30)
    DatedExchangeRule(
        rule_id="STT-OPT-20230401",
        component=FeeComponent.STT,
        source_ref="Finance Act, 2023, Section 136",
        publication_date=date(2023, 3, 31),
        effective_from=date(2023, 4, 1),
        effective_to=date(2024, 9, 30),
        venue="NSE",
        segment=MarketSegment.EQUITY_OPTIONS,
        side_basis=SideBasis.SELL,
        rate=Decimal("0.000625"),  # 0.0625%
        rate_basis=RateBasis.PREMIUM_TURNOVER,
        rounding_unit=_PAISA,
        rounding_method=RoundingMethod.ROUND_HALF_UP_PAISA,
        description="STT 0.0625% on option sell premium turnover",
    ),
    # Options: 0.1000% on SELL premium (Finance (No. 2) Act 2024, effective 2024-10-01)
    DatedExchangeRule(
        rule_id="STT-OPT-20241001",
        component=FeeComponent.STT,
        source_ref="Finance (No. 2) Act, 2024, Section 169 (STT Options Rate Revision)",
        publication_date=date(2024, 8, 16),
        effective_from=date(2024, 10, 1),
        effective_to=None,
        venue="NSE",
        segment=MarketSegment.EQUITY_OPTIONS,
        side_basis=SideBasis.SELL,
        rate=Decimal("0.001000"),  # 0.10%
        rate_basis=RateBasis.PREMIUM_TURNOVER,
        rounding_unit=_PAISA,
        rounding_method=RoundingMethod.ROUND_HALF_UP_PAISA,
        description="STT revised to 0.10% on option sell premium turnover",
    ),
    # ------------------ 2. Stamp Duty (Indian Stamp Act, Uniform Rates) ------------------
    # Cash Delivery: 0.015% on BUY (Effective 2020-07-01)
    DatedExchangeRule(
        rule_id="SD-EQ-DEL-20200701",
        component=FeeComponent.STAMP_DUTY,
        source_ref="Indian Stamp Act, 1899 amended via Finance Act 2019, Notification S.O. 1226(E)",
        publication_date=date(2020, 3, 30),
        effective_from=date(2020, 7, 1),
        effective_to=None,
        venue="NSE",
        segment=MarketSegment.EQUITY_DELIVERY,
        side_basis=SideBasis.BUY,
        rate=Decimal("0.000150"),  # 0.015%
        rate_basis=RateBasis.TURNOVER,
        rounding_unit=_PAISA,
        rounding_method=RoundingMethod.ROUND_HALF_UP_PAISA,
        description="Stamp duty 0.015% on delivery buy turnover",
    ),
    # Cash Intraday: 0.003% on BUY (Effective 2020-07-01)
    DatedExchangeRule(
        rule_id="SD-EQ-INT-20200701",
        component=FeeComponent.STAMP_DUTY,
        source_ref="Indian Stamp Act, 1899 amended via Finance Act 2019, Notification S.O. 1226(E)",
        publication_date=date(2020, 3, 30),
        effective_from=date(2020, 7, 1),
        effective_to=None,
        venue="NSE",
        segment=MarketSegment.EQUITY_INTRADAY,
        side_basis=SideBasis.BUY,
        rate=Decimal("0.000030"),  # 0.003%
        rate_basis=RateBasis.TURNOVER,
        rounding_unit=_PAISA,
        rounding_method=RoundingMethod.ROUND_HALF_UP_PAISA,
        description="Stamp duty 0.003% on intraday buy turnover",
    ),
    # Futures: 0.002% on BUY (Effective 2020-07-01)
    DatedExchangeRule(
        rule_id="SD-FUT-20200701",
        component=FeeComponent.STAMP_DUTY,
        source_ref="Indian Stamp Act, 1899 amended via Finance Act 2019, Notification S.O. 1226(E)",
        publication_date=date(2020, 3, 30),
        effective_from=date(2020, 7, 1),
        effective_to=None,
        venue="NSE",
        segment=MarketSegment.EQUITY_FUTURES,
        side_basis=SideBasis.BUY,
        rate=Decimal("0.000020"),  # 0.002%
        rate_basis=RateBasis.TURNOVER,
        rounding_unit=_PAISA,
        rounding_method=RoundingMethod.ROUND_HALF_UP_PAISA,
        description="Stamp duty 0.002% on futures buy turnover",
    ),
    # Options: 0.003% on BUY premium (Effective 2020-07-01)
    DatedExchangeRule(
        rule_id="SD-OPT-20200701",
        component=FeeComponent.STAMP_DUTY,
        source_ref="Indian Stamp Act, 1899 amended via Finance Act 2019, Notification S.O. 1226(E)",
        publication_date=date(2020, 3, 30),
        effective_from=date(2020, 7, 1),
        effective_to=None,
        venue="NSE",
        segment=MarketSegment.EQUITY_OPTIONS,
        side_basis=SideBasis.BUY,
        rate=Decimal("0.000030"),  # 0.003%
        rate_basis=RateBasis.PREMIUM_TURNOVER,
        rounding_unit=_PAISA,
        rounding_method=RoundingMethod.ROUND_HALF_UP_PAISA,
        description="Stamp duty 0.003% on option buy premium turnover",
    ),
    # ------------------ 3. SEBI Turnover Charges ------------------
    # Prior to 2021-06-01: ₹15 per crore (0.00015%)
    DatedExchangeRule(
        rule_id="SEBI-FEE-20140401",
        component=FeeComponent.SEBI_TURNOVER,
        source_ref="SEBI (Regulatory Fee on Stock Exchanges) Regulations",
        publication_date=date(2014, 4, 1),
        effective_from=date(2014, 4, 1),
        effective_to=date(2021, 5, 31),
        venue="NSE",
        segment=MarketSegment.EQUITY_DELIVERY,
        side_basis=SideBasis.BOTH,
        rate=Decimal("0.0000015"),  # ₹15 per crore
        rate_basis=RateBasis.TURNOVER,
        rounding_unit=_PAISA,
        rounding_method=RoundingMethod.ROUND_HALF_UP_PAISA,
        description="SEBI turnover fee ₹15 per crore",
    ),
    DatedExchangeRule(
        rule_id="SEBI-FEE-20210601-DEL",
        component=FeeComponent.SEBI_TURNOVER,
        source_ref="SEBI Circular SEBI/HO/MRD/MRD-PoD-1/P/CIR/2021/571",
        publication_date=date(2021, 5, 28),
        effective_from=date(2021, 6, 1),
        effective_to=None,
        venue="NSE",
        segment=MarketSegment.EQUITY_DELIVERY,
        side_basis=SideBasis.BOTH,
        rate=Decimal("0.0000010"),  # ₹10 per crore
        rate_basis=RateBasis.TURNOVER,
        rounding_unit=_PAISA,
        rounding_method=RoundingMethod.ROUND_HALF_UP_PAISA,
        description="SEBI turnover fee reduced to ₹10 per crore",
    ),
    DatedExchangeRule(
        rule_id="SEBI-FEE-20210601-INT",
        component=FeeComponent.SEBI_TURNOVER,
        source_ref="SEBI Circular SEBI/HO/MRD/MRD-PoD-1/P/CIR/2021/571",
        publication_date=date(2021, 5, 28),
        effective_from=date(2021, 6, 1),
        effective_to=None,
        venue="NSE",
        segment=MarketSegment.EQUITY_INTRADAY,
        side_basis=SideBasis.BOTH,
        rate=Decimal("0.0000010"),  # ₹10 per crore
        rate_basis=RateBasis.TURNOVER,
        rounding_unit=_PAISA,
        rounding_method=RoundingMethod.ROUND_HALF_UP_PAISA,
        description="SEBI turnover fee ₹10 per crore on intraday",
    ),
    DatedExchangeRule(
        rule_id="SEBI-FEE-20210601-FUT",
        component=FeeComponent.SEBI_TURNOVER,
        source_ref="SEBI Circular SEBI/HO/MRD/MRD-PoD-1/P/CIR/2021/571",
        publication_date=date(2021, 5, 28),
        effective_from=date(2021, 6, 1),
        effective_to=None,
        venue="NSE",
        segment=MarketSegment.EQUITY_FUTURES,
        side_basis=SideBasis.BOTH,
        rate=Decimal("0.0000010"),  # ₹10 per crore
        rate_basis=RateBasis.TURNOVER,
        rounding_unit=_PAISA,
        rounding_method=RoundingMethod.ROUND_HALF_UP_PAISA,
        description="SEBI turnover fee ₹10 per crore on futures turnover",
    ),
    DatedExchangeRule(
        rule_id="SEBI-FEE-20210601-OPT",
        component=FeeComponent.SEBI_TURNOVER,
        source_ref="SEBI Circular SEBI/HO/MRD/MRD-PoD-1/P/CIR/2021/571",
        publication_date=date(2021, 5, 28),
        effective_from=date(2021, 6, 1),
        effective_to=None,
        venue="NSE",
        segment=MarketSegment.EQUITY_OPTIONS,
        side_basis=SideBasis.BOTH,
        rate=Decimal("0.0000010"),  # ₹10 per crore on premium
        rate_basis=RateBasis.PREMIUM_TURNOVER,
        rounding_unit=_PAISA,
        rounding_method=RoundingMethod.ROUND_HALF_UP_PAISA,
        description="SEBI turnover fee ₹10 per crore on option premium",
    ),
    # ------------------ 4. NSE Exchange Turnover Charges ------------------
    # Cash Delivery: 0.00345% prior to 2024-10-01, 0.00297% effective 2024-10-01
    DatedExchangeRule(
        rule_id="EXCH-EQ-DEL-20170401",
        component=FeeComponent.EXCHANGE_TURNOVER,
        source_ref="NSE Circular NSE/CMTR/34212",
        publication_date=date(2017, 3, 31),
        effective_from=date(2017, 4, 1),
        effective_to=date(2024, 9, 30),
        venue="NSE",
        segment=MarketSegment.EQUITY_DELIVERY,
        side_basis=SideBasis.BOTH,
        rate=Decimal("0.0000345"),  # 0.00345%
        rate_basis=RateBasis.TURNOVER,
        rounding_unit=_PAISA,
        rounding_method=RoundingMethod.ROUND_HALF_UP_PAISA,
        description="NSE Cash delivery turnover charge 0.00345%",
    ),
    DatedExchangeRule(
        rule_id="EXCH-EQ-DEL-20241001",
        component=FeeComponent.EXCHANGE_TURNOVER,
        source_ref="NSE Circular NSE/INVG/63567 (Uniform Exchange Charge Structure)",
        publication_date=date(2024, 9, 23),
        effective_from=date(2024, 10, 1),
        effective_to=None,
        venue="NSE",
        segment=MarketSegment.EQUITY_DELIVERY,
        side_basis=SideBasis.BOTH,
        rate=Decimal("0.0000297"),  # 0.00297% (₹2.97 per lakh)
        rate_basis=RateBasis.TURNOVER,
        rounding_unit=_PAISA,
        rounding_method=RoundingMethod.ROUND_HALF_UP_PAISA,
        description="NSE Cash delivery revised uniform charge 0.00297%",
    ),
    # Cash Intraday: 0.00345% prior to 2024-10-01, 0.00297% effective 2024-10-01
    DatedExchangeRule(
        rule_id="EXCH-EQ-INT-20170401",
        component=FeeComponent.EXCHANGE_TURNOVER,
        source_ref="NSE Circular NSE/CMTR/34212",
        publication_date=date(2017, 3, 31),
        effective_from=date(2017, 4, 1),
        effective_to=date(2024, 9, 30),
        venue="NSE",
        segment=MarketSegment.EQUITY_INTRADAY,
        side_basis=SideBasis.BOTH,
        rate=Decimal("0.0000345"),
        rate_basis=RateBasis.TURNOVER,
        rounding_unit=_PAISA,
        rounding_method=RoundingMethod.ROUND_HALF_UP_PAISA,
        description="NSE Cash intraday turnover charge 0.00345%",
    ),
    DatedExchangeRule(
        rule_id="EXCH-EQ-INT-20241001",
        component=FeeComponent.EXCHANGE_TURNOVER,
        source_ref="NSE Circular NSE/INVG/63567",
        publication_date=date(2024, 9, 23),
        effective_from=date(2024, 10, 1),
        effective_to=None,
        venue="NSE",
        segment=MarketSegment.EQUITY_INTRADAY,
        side_basis=SideBasis.BOTH,
        rate=Decimal("0.0000297"),
        rate_basis=RateBasis.TURNOVER,
        rounding_unit=_PAISA,
        rounding_method=RoundingMethod.ROUND_HALF_UP_PAISA,
        description="NSE Cash intraday revised uniform charge 0.00297%",
    ),
    # Equity Futures: 0.0019% prior to 2024-10-01, 0.00173% effective 2024-10-01
    DatedExchangeRule(
        rule_id="EXCH-FUT-20170401",
        component=FeeComponent.EXCHANGE_TURNOVER,
        source_ref="NSE Circular NSE/FAOP/34213",
        publication_date=date(2017, 3, 31),
        effective_from=date(2017, 4, 1),
        effective_to=date(2024, 9, 30),
        venue="NSE",
        segment=MarketSegment.EQUITY_FUTURES,
        side_basis=SideBasis.BOTH,
        rate=Decimal("0.0000190"),  # 0.0019%
        rate_basis=RateBasis.TURNOVER,
        rounding_unit=_PAISA,
        rounding_method=RoundingMethod.ROUND_HALF_UP_PAISA,
        description="NSE Futures turnover charge 0.0019%",
    ),
    DatedExchangeRule(
        rule_id="EXCH-FUT-20241001",
        component=FeeComponent.EXCHANGE_TURNOVER,
        source_ref="NSE Circular NSE/INVG/63567",
        publication_date=date(2024, 9, 23),
        effective_from=date(2024, 10, 1),
        effective_to=None,
        venue="NSE",
        segment=MarketSegment.EQUITY_FUTURES,
        side_basis=SideBasis.BOTH,
        rate=Decimal("0.0000173"),  # 0.00173% (₹1.73 per lakh)
        rate_basis=RateBasis.TURNOVER,
        rounding_unit=_PAISA,
        rounding_method=RoundingMethod.ROUND_HALF_UP_PAISA,
        description="NSE Futures revised uniform charge 0.00173%",
    ),
    # Equity Options: 0.050% on premium prior to 2024-10-01, 0.03503% effective 2024-10-01
    DatedExchangeRule(
        rule_id="EXCH-OPT-20170401",
        component=FeeComponent.EXCHANGE_TURNOVER,
        source_ref="NSE Circular NSE/FAOP/34213",
        publication_date=date(2017, 3, 31),
        effective_from=date(2017, 4, 1),
        effective_to=date(2024, 9, 30),
        venue="NSE",
        segment=MarketSegment.EQUITY_OPTIONS,
        side_basis=SideBasis.BOTH,
        rate=Decimal("0.0005000"),  # 0.05% on premium
        rate_basis=RateBasis.PREMIUM_TURNOVER,
        rounding_unit=_PAISA,
        rounding_method=RoundingMethod.ROUND_HALF_UP_PAISA,
        description="NSE Options turnover charge 0.05% on premium",
    ),
    DatedExchangeRule(
        rule_id="EXCH-OPT-20241001",
        component=FeeComponent.EXCHANGE_TURNOVER,
        source_ref="NSE Circular NSE/INVG/63567",
        publication_date=date(2024, 9, 23),
        effective_from=date(2024, 10, 1),
        effective_to=None,
        venue="NSE",
        segment=MarketSegment.EQUITY_OPTIONS,
        side_basis=SideBasis.BOTH,
        rate=Decimal("0.0003503"),  # 0.03503% on premium (₹35.03 per lakh premium)
        rate_basis=RateBasis.PREMIUM_TURNOVER,
        rounding_unit=_PAISA,
        rounding_method=RoundingMethod.ROUND_HALF_UP_PAISA,
        description="NSE Options revised uniform charge 0.03503% on premium",
    ),
    # ------------------ 5. GST (Goods & Services Tax) ------------------
    # 18% on (Brokerage + Exchange Turnover + SEBI Charges) across all segments
    DatedExchangeRule(
        rule_id="GST-FIN-20170701-DEL",
        component=FeeComponent.GST,
        source_ref="Central Goods and Services Tax Act, 2017 / Notification No. 11/2017-Central Tax (Rate)",
        publication_date=date(2017, 6, 28),
        effective_from=date(2017, 7, 1),
        effective_to=None,
        venue="NSE",
        segment=MarketSegment.EQUITY_DELIVERY,
        side_basis=SideBasis.BOTH,
        rate=Decimal("0.18"),  # 18%
        rate_basis=RateBasis.STATUTORY_CHARGES,
        rounding_unit=_PAISA,
        rounding_method=RoundingMethod.ROUND_HALF_UP_PAISA,
        description="GST 18% on (Brokerage + Exchange + SEBI)",
    ),
    DatedExchangeRule(
        rule_id="GST-FIN-20170701-INT",
        component=FeeComponent.GST,
        source_ref="Central Goods and Services Tax Act, 2017",
        publication_date=date(2017, 6, 28),
        effective_from=date(2017, 7, 1),
        effective_to=None,
        venue="NSE",
        segment=MarketSegment.EQUITY_INTRADAY,
        side_basis=SideBasis.BOTH,
        rate=Decimal("0.18"),
        rate_basis=RateBasis.STATUTORY_CHARGES,
        rounding_unit=_PAISA,
        rounding_method=RoundingMethod.ROUND_HALF_UP_PAISA,
        description="GST 18% on (Brokerage + Exchange + SEBI) Intraday",
    ),
    DatedExchangeRule(
        rule_id="GST-FIN-20170701-FUT",
        component=FeeComponent.GST,
        source_ref="Central Goods and Services Tax Act, 2017",
        publication_date=date(2017, 6, 28),
        effective_from=date(2017, 7, 1),
        effective_to=None,
        venue="NSE",
        segment=MarketSegment.EQUITY_FUTURES,
        side_basis=SideBasis.BOTH,
        rate=Decimal("0.18"),
        rate_basis=RateBasis.STATUTORY_CHARGES,
        rounding_unit=_PAISA,
        rounding_method=RoundingMethod.ROUND_HALF_UP_PAISA,
        description="GST 18% on (Brokerage + Exchange + SEBI) Futures",
    ),
    DatedExchangeRule(
        rule_id="GST-FIN-20170701-OPT",
        component=FeeComponent.GST,
        source_ref="Central Goods and Services Tax Act, 2017",
        publication_date=date(2017, 6, 28),
        effective_from=date(2017, 7, 1),
        effective_to=None,
        venue="NSE",
        segment=MarketSegment.EQUITY_OPTIONS,
        side_basis=SideBasis.BOTH,
        rate=Decimal("0.18"),
        rate_basis=RateBasis.STATUTORY_CHARGES,
        rounding_unit=_PAISA,
        rounding_method=RoundingMethod.ROUND_HALF_UP_PAISA,
        description="GST 18% on (Brokerage + Exchange + SEBI) Options",
    ),
    # ------------------ 6. Standard Discount Brokerage Models ------------------
    # Delivery: Zero brokerage standard
    DatedExchangeRule(
        rule_id="BRK-DISCOUNT-DEL-ZERO",
        component=FeeComponent.BROKERAGE,
        source_ref="Standard Discount Brokerage Tariff Schedule",
        publication_date=date(2015, 1, 1),
        effective_from=date(2015, 1, 1),
        effective_to=None,
        venue="NSE",
        segment=MarketSegment.EQUITY_DELIVERY,
        side_basis=SideBasis.BOTH,
        rate=Decimal("0.00"),
        rate_basis=RateBasis.FLAT_PER_ORDER,
        rounding_unit=_PAISA,
        rounding_method=RoundingMethod.ROUND_HALF_UP_PAISA,
        description="Zero brokerage for equity delivery",
    ),
    # Intraday: Flat ₹20 or 0.05% whichever is lower
    DatedExchangeRule(
        rule_id="BRK-DISCOUNT-INT-FLAT20",
        component=FeeComponent.BROKERAGE,
        source_ref="Standard Discount Brokerage Tariff Schedule",
        publication_date=date(2015, 1, 1),
        effective_from=date(2015, 1, 1),
        effective_to=None,
        venue="NSE",
        segment=MarketSegment.EQUITY_INTRADAY,
        side_basis=SideBasis.BOTH,
        rate=Decimal("0.0005"),  # 0.05%
        rate_basis=RateBasis.PERCENTAGE_WITH_CAP,
        cap=Decimal("20.00"),
        rounding_unit=_PAISA,
        rounding_method=RoundingMethod.ROUND_HALF_UP_PAISA,
        description="Intraday brokerage 0.05% capped at ₹20 per executed order",
    ),
    # Futures: Flat ₹20 or 0.05% capped at ₹20
    DatedExchangeRule(
        rule_id="BRK-DISCOUNT-FUT-FLAT20",
        component=FeeComponent.BROKERAGE,
        source_ref="Standard Discount Brokerage Tariff Schedule",
        publication_date=date(2015, 1, 1),
        effective_from=date(2015, 1, 1),
        effective_to=None,
        venue="NSE",
        segment=MarketSegment.EQUITY_FUTURES,
        side_basis=SideBasis.BOTH,
        rate=Decimal("0.0005"),
        rate_basis=RateBasis.PERCENTAGE_WITH_CAP,
        cap=Decimal("20.00"),
        rounding_unit=_PAISA,
        rounding_method=RoundingMethod.ROUND_HALF_UP_PAISA,
        description="Futures brokerage 0.05% capped at ₹20 per executed order",
    ),
    # Options: Flat ₹20 per executed order
    DatedExchangeRule(
        rule_id="BRK-DISCOUNT-OPT-FLAT20",
        component=FeeComponent.BROKERAGE,
        source_ref="Standard Discount Brokerage Tariff Schedule",
        publication_date=date(2015, 1, 1),
        effective_from=date(2015, 1, 1),
        effective_to=None,
        venue="NSE",
        segment=MarketSegment.EQUITY_OPTIONS,
        side_basis=SideBasis.BOTH,
        rate=Decimal("20.00"),
        rate_basis=RateBasis.FLAT_PER_ORDER,
        rounding_unit=_PAISA,
        rounding_method=RoundingMethod.ROUND_HALF_UP_PAISA,
        description="Options brokerage flat ₹20 per executed order",
    ),
]


class NSERuleEngine:
    """Authority-producing dated cost calculator selecting exact Indian regulatory rules by trade date."""

    def __init__(self, rules: list[DatedExchangeRule] | None = None) -> None:
        self._rules: list[DatedExchangeRule] = []
        catalog = rules if rules is not None else _CANONICAL_RULES
        for r in catalog:
            self.register_rule(r)
        self.validate_catalog()

    @property
    def rules(self) -> list[DatedExchangeRule]:
        return list(self._rules)

    def register_rule(self, rule: DatedExchangeRule) -> None:
        """Registers a dated exchange rule."""
        if not isinstance(rule, DatedExchangeRule):
            raise TypeError(f"Expected DatedExchangeRule, got {type(rule)}")
        self._rules.append(rule)

    def validate_catalog(self) -> None:
        """Verifies that no overlapping active date ranges exist for the same component and segment."""
        by_key: dict[tuple[FeeComponent, MarketSegment], list[DatedExchangeRule]] = {}
        for r in self._rules:
            key = (r.component, r.segment)
            by_key.setdefault(key, []).append(r)

        for (comp, seg), rule_list in by_key.items():
            sorted_rules = sorted(rule_list, key=lambda x: x.effective_from)
            for i in range(len(sorted_rules) - 1):
                cur = sorted_rules[i]
                nxt = sorted_rules[i + 1]
                if cur.effective_to is None or cur.effective_to >= nxt.effective_from:
                    raise ValueError(
                        f"Catalog overlap/ambiguity detected for {comp.value} in {seg.value}: "
                        f"{cur.rule_id} [{cur.effective_from} to {cur.effective_to}] overlaps with "
                        f"{nxt.rule_id} starting {nxt.effective_from}"
                    )

    def get_rule(
        self,
        component: FeeComponent,
        segment: MarketSegment,
        trade_date: date,
    ) -> DatedExchangeRule:
        """Retrieves the exact statutory rule in force on trade_date."""
        for r in self._rules:
            if r.component == component and r.segment == segment and r.is_effective(trade_date):
                return r
        raise ValueError(
            f"No effective rule found for component={component.value}, "
            f"segment={segment.value} on trade_date={trade_date.isoformat()}"
        )

    def get_all_rules_for_date(
        self,
        segment: MarketSegment,
        trade_date: date,
    ) -> list[DatedExchangeRule]:
        """Returns all effective rules for a market segment on a given trade date."""
        return [r for r in self._rules if r.segment == segment and r.is_effective(trade_date)]

    def calculate_costs(
        self,
        segment: MarketSegment,
        side: Side,
        quantity: int,
        price: Decimal,
        trade_date: date,
        custom_brokerage_rule: DatedExchangeRule | None = None,
        slippage_bps: Decimal = Decimal("0"),
    ) -> CostBreakdown:
        """Calculates exact Decimal itemized regulatory friction strictly using dated rules."""
        if quantity <= 0:
            raise ValueError(f"Quantity must be positive, got {quantity}")
        if price <= Decimal("0"):
            raise ValueError(f"Price must be strictly positive, got {price}")
        if not isinstance(price, Decimal) or not isinstance(slippage_bps, Decimal):
            raise TypeError("Price and slippage_bps must be exact Decimal instances")

        turnover = (price * Decimal(quantity)).quantize(_PAISA)

        # 1. Fetch effective rules
        stt_rule = self.get_rule(FeeComponent.STT, segment, trade_date)
        exch_rule = self.get_rule(FeeComponent.EXCHANGE_TURNOVER, segment, trade_date)
        sebi_rule = self.get_rule(FeeComponent.SEBI_TURNOVER, segment, trade_date)
        sd_rule = self.get_rule(FeeComponent.STAMP_DUTY, segment, trade_date)
        gst_rule = self.get_rule(FeeComponent.GST, segment, trade_date)
        brk_rule = custom_brokerage_rule or self.get_rule(
            FeeComponent.BROKERAGE, segment, trade_date
        )

        applied_rules = {
            "STT": stt_rule.rule_id,
            "EXCHANGE_TURNOVER": exch_rule.rule_id,
            "SEBI_TURNOVER": sebi_rule.rule_id,
            "STAMP_DUTY": sd_rule.rule_id,
            "GST": gst_rule.rule_id,
            "BROKERAGE": brk_rule.rule_id,
        }
        applied_hashes = {
            "STT": stt_rule.rule_hash,
            "EXCHANGE_TURNOVER": exch_rule.rule_hash,
            "SEBI_TURNOVER": sebi_rule.rule_hash,
            "STAMP_DUTY": sd_rule.rule_hash,
            "GST": gst_rule.rule_hash,
            "BROKERAGE": brk_rule.rule_hash,
        }

        # 2. Compute Brokerage
        brokerage = Decimal("0.00")
        if brk_rule.rate_basis == RateBasis.FLAT_PER_ORDER:
            brokerage = brk_rule.rate.quantize(_PAISA)
        elif brk_rule.rate_basis == RateBasis.PERCENTAGE_WITH_CAP:
            raw_brk = turnover * brk_rule.rate
            if brk_rule.cap is not None:
                raw_brk = min(raw_brk, brk_rule.cap)
            brokerage = raw_brk.quantize(_PAISA, rounding=ROUND_HALF_UP)
        elif brk_rule.rate_basis == RateBasis.TURNOVER:
            brokerage = (turnover * brk_rule.rate).quantize(_PAISA, rounding=ROUND_HALF_UP)

        # 3. Compute STT
        stt = Decimal("0.00")
        stt_applies = (
            (stt_rule.side_basis == SideBasis.BOTH)
            or (stt_rule.side_basis == SideBasis.BUY and side == Side.BUY)
            or (stt_rule.side_basis == SideBasis.SELL and side == Side.SELL)
        )
        if stt_applies:
            raw_stt = turnover * stt_rule.rate
            stt = raw_stt.quantize(_PAISA, rounding=ROUND_HALF_UP)

        # 4. Compute Exchange Turnover Charges
        raw_exch = turnover * exch_rule.rate
        exchange_turnover = raw_exch.quantize(_PAISA, rounding=ROUND_HALF_UP)

        # 5. Compute SEBI Charges
        raw_sebi = turnover * sebi_rule.rate
        sebi_charges = raw_sebi.quantize(_PAISA, rounding=ROUND_HALF_UP)

        # 6. Compute Stamp Duty (applicable on BUY side)
        stamp_duty = Decimal("0.00")
        sd_applies = (
            (sd_rule.side_basis == SideBasis.BOTH)
            or (sd_rule.side_basis == SideBasis.BUY and side == Side.BUY)
            or (sd_rule.side_basis == SideBasis.SELL and side == Side.SELL)
        )
        if sd_applies:
            raw_sd = turnover * sd_rule.rate
            stamp_duty = raw_sd.quantize(_PAISA, rounding=ROUND_HALF_UP)

        # 7. Compute GST (18% on Brokerage + Exchange + SEBI)
        gst_base = brokerage + exchange_turnover + sebi_charges
        raw_gst = gst_base * gst_rule.rate
        gst = raw_gst.quantize(_PAISA, rounding=ROUND_HALF_UP)

        # 8. Compute Slippage
        slippage = Decimal("0.00")
        if slippage_bps > Decimal("0"):
            raw_slip = turnover * (slippage_bps / Decimal("10000.00"))
            slippage = raw_slip.quantize(_PAISA, rounding=ROUND_HALF_UP)

        # 9. Totals
        total_statutory = stt + exchange_turnover + sebi_charges + stamp_duty + gst
        total_fee = brokerage + total_statutory
        total_friction = total_fee + slippage

        # 10. Canonical Calculation Hash
        calc_payload = {
            "trade_date": trade_date.isoformat(),
            "segment": segment.value,
            "side": side.value,
            "quantity": quantity,
            "price": str(price),
            "turnover": str(turnover),
            "brokerage": str(brokerage),
            "stt": str(stt),
            "exchange_turnover": str(exchange_turnover),
            "sebi_charges": str(sebi_charges),
            "stamp_duty": str(stamp_duty),
            "gst": str(gst),
            "slippage": str(slippage),
            "total_statutory_charges": str(total_statutory),
            "total_fee": str(total_fee),
            "total_friction": str(total_friction),
            "applied_rule_ids": applied_rules,
        }
        calc_hash = hashlib.sha256(
            json.dumps(calc_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()

        return CostBreakdown(
            trade_date=trade_date,
            segment=segment,
            side=side,
            quantity=quantity,
            price=price,
            turnover=turnover,
            brokerage=brokerage,
            stt=stt,
            exchange_turnover=exchange_turnover,
            sebi_charges=sebi_charges,
            stamp_duty=stamp_duty,
            gst=gst,
            slippage=slippage,
            total_statutory_charges=total_statutory,
            total_fee=total_fee,
            total_friction=total_friction,
            applied_rule_ids=applied_rules,
            applied_rule_hashes=applied_hashes,
            calculation_hash=calc_hash,
        )
