"""What the proof builder is given: a stock's figures with where each came from, and how its business was judged."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from quant_system.shariah.services.activity_check import ActivityResult

__all__ = ["FigureIn", "FilingIn", "MarketValueIn", "ProofInputs"]


@dataclass(frozen=True, slots=True)
class FigureIn:
    """One figure read from a filing: its key, plain label, the tag it was filed under, and its rupee value."""

    key: str
    label: str
    xbrl_tag: str | None
    value_inr: Decimal


@dataclass(frozen=True, slots=True)
class FilingIn:
    """The filing the figures came from, with what a person needs to open it and check."""

    source_url: str
    detail_url: str | None
    period_end: str
    period_label: str
    filed_on: str | None
    consolidated: bool
    audited: bool | None
    sha256: str
    tie_out: tuple[dict[str, Any], ...]
    tie_out_ok: bool


@dataclass(frozen=True, slots=True)
class MarketValueIn:
    """The 36-month average market value, worked out from QuantOS's own daily prices and the filed share count."""

    average_cr: Decimal
    shares_in_issue: int
    label: str


@dataclass(frozen=True, slots=True)
class ProofInputs:
    symbol: str
    company_name: str
    activity: ActivityResult
    data_status: str  # VERIFIED_FILING, STALE, UNVERIFIED_SAMPLE or NOT_SCREENED
    screened_at: str
    filing: FilingIn | None = None
    figures: Mapping[str, FigureIn] = field(default_factory=dict)
    market_value: MarketValueIn | None = None
    sample: dict[str, Any] | None = (
        None  # the hand-entered row: the figures when no filing, a comparison otherwise
    )
    isin: str | None = None
