"""Realistic Indian market transaction cost model (STT, GST, Exchange Turnover, Stamp Duty, Slippage)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from quant_system.core.domain import Side

_PAISA = Decimal("0.01")


@dataclass(frozen=True, slots=True)
class TransactionCostBreakdown:
    brokerage: Decimal
    stt: Decimal  # Securities Transaction Tax
    exchange_turnover: Decimal
    sebi_charges: Decimal
    stamp_duty: Decimal
    gst: Decimal  # 18% on (Brokerage + Exchange Turnover + SEBI)
    slippage: Decimal

    @property
    def total_fee(self) -> Decimal:
        return (
            self.brokerage
            + self.stt
            + self.exchange_turnover
            + self.sebi_charges
            + self.stamp_duty
            + self.gst
        )

    @property
    def total_friction(self) -> Decimal:
        return self.total_fee + self.slippage


class IndianMarketCostModel:
    """Computes exact regulatory, brokerage, and slippage friction for Indian Equities and Derivatives."""

    @classmethod
    def calculate_equity_delivery(
        cls,
        side: Side,
        quantity: int,
        price: Decimal,
        slippage_bps: float = 5.0,
    ) -> TransactionCostBreakdown:
        turnover = price * Decimal(quantity)

        # Zero brokerage model for delivery (standard discount broker) or flat ₹20
        brokerage = Decimal("0.00")

        # STT: 0.1% on both Buy and Sell for equity delivery
        stt = (turnover * Decimal("0.001")).quantize(_PAISA)

        # Exchange Turnover (NSE): 0.00345%
        exchange_turnover = (turnover * Decimal("0.0000345")).quantize(_PAISA)

        # SEBI Charges: ₹10 per crore (0.0001%)
        sebi = (turnover * Decimal("0.000001")).quantize(_PAISA)

        # Stamp Duty: 0.015% on BUY side only
        stamp_duty = (
            (turnover * Decimal("0.00015")).quantize(_PAISA)
            if side == Side.BUY
            else Decimal("0.00")
        )

        # GST: 18% on (Brokerage + Exchange Turnover + SEBI)
        gst = ((brokerage + exchange_turnover + sebi) * Decimal("0.18")).quantize(_PAISA)

        # Slippage in cash value
        slippage = (turnover * Decimal(str(slippage_bps / 10000.0))).quantize(_PAISA)

        return TransactionCostBreakdown(
            brokerage=brokerage,
            stt=stt,
            exchange_turnover=exchange_turnover,
            sebi_charges=sebi,
            stamp_duty=stamp_duty,
            gst=gst,
            slippage=slippage,
        )

    @classmethod
    def calculate_options_friction(
        cls,
        side: Side,
        quantity: int,
        premium: Decimal,
        strike: Decimal,
        slippage_bps: float = 20.0,
    ) -> TransactionCostBreakdown:
        turnover = premium * Decimal(quantity)

        # Brokerage: Flat ₹20 per order
        brokerage = Decimal("20.00")

        # STT: 0.1% on premium on SELL side only (post-2024 budget revisions: 0.1% on sell option premium)
        stt = (
            (turnover * Decimal("0.001")).quantize(_PAISA) if side == Side.SELL else Decimal("0.00")
        )

        # Exchange Turnover (NSE Options): 0.05% on premium turnover
        exchange_turnover = (turnover * Decimal("0.0005")).quantize(_PAISA)

        # SEBI Charges: ₹10 per crore
        sebi = (turnover * Decimal("0.000001")).quantize(_PAISA)

        # Stamp Duty: 0.003% on BUY side premium only
        stamp_duty = (
            (turnover * Decimal("0.00003")).quantize(_PAISA)
            if side == Side.BUY
            else Decimal("0.00")
        )

        # GST: 18% on (Brokerage + Exchange + SEBI)
        gst = ((brokerage + exchange_turnover + sebi) * Decimal("0.18")).quantize(_PAISA)

        # Option slippage on premium
        slippage = (turnover * Decimal(str(slippage_bps / 10000.0))).quantize(_PAISA)

        return TransactionCostBreakdown(
            brokerage=brokerage,
            stt=stt,
            exchange_turnover=exchange_turnover,
            sebi_charges=sebi,
            stamp_duty=stamp_duty,
            gst=gst,
            slippage=slippage,
        )
