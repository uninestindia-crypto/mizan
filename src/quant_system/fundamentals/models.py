"""Plain data for the fundamentals engine. Money is Decimal and nothing here touches the network.

A figure is only ever a number a company filed, with the XBRL tag it came from. Nothing is estimated or carried
over from another filing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Any, Final

__all__ = [
    "BalanceFigures",
    "Figure",
    "QuarterFigures",
    "ReadStatus",
    "TieOut",
]

PASS: Final = "PASS"
FAIL: Final = "FAIL"
SKIPPED: Final = "SKIPPED"
_OUTCOMES: Final = frozenset({PASS, FAIL, SKIPPED})
#: Smallest set of lines a quarter needs before it can feed any metric.
REQUIRED_LINES: Final = (
    "revenue_from_operations",
    "total_income",
    "expenses",
    "profit_before_tax",
    "profit_for_period",
)
#: Smallest set of lines a balance sheet needs before it can feed any ratio.
REQUIRED_BALANCE_LINES: Final = ("total_assets", "equity_total")


class ReadStatus(StrEnum):
    READ_OK = "READ_OK"
    READ_PARTIAL = "READ_PARTIAL"
    TIE_OUT_FAILED = "TIE_OUT_FAILED"
    FORMAT_NOT_READ = "FORMAT_NOT_READ"
    NOT_A_QUARTER = "NOT_A_QUARTER"


def _text(data: dict[str, Any], key: str) -> str:
    value = data[key]
    if not isinstance(value, str):
        raise ValueError(f"{key} must be text")
    return value


def _decimal(raw: object, name: str) -> Decimal:
    if not isinstance(raw, str):
        raise ValueError(f"{name} must be text, not a number")
    try:
        value = Decimal(raw)
    except InvalidOperation:
        raise ValueError(f"{name} is not a number") from None
    if not value.is_finite():
        raise ValueError(f"{name} is not a finite number")
    return value


def _day(raw: object) -> date | None:
    if raw is None:
        return None
    if not isinstance(raw, str):
        raise ValueError("a date must be text")
    return date.fromisoformat(raw)


@dataclass(frozen=True)
class Figure:
    """One number as filed: rupees (or rupees per share for earnings per share) and the tag it was read from."""

    tag: str
    value: Decimal
    decimals: str | None = None

    def rounding_inr(self) -> Decimal:
        """Half the unit the filer rounded to, 0 when the figure was filed to the rupee or finer."""
        try:
            places = int(self.decimals) if self.decimals is not None else 0
        except ValueError:
            return Decimal(0)
        return Decimal(10) ** (-places) / 2 if places < 0 else Decimal(0)

    def to_json_dict(self) -> dict[str, Any]:
        return {"tag": self.tag, "value": str(self.value), "decimals": self.decimals}

    @classmethod
    def from_json_dict(cls, key: str, data: dict[str, Any]) -> Figure:
        return cls(
            _text(data, "tag"), _decimal(data["value"], f"lines.{key}.value"), data["decimals"]
        )


@dataclass(frozen=True)
class TieOut:
    """One check a filing makes against itself. SKIPPED means an input was not filed, so it could not be made."""

    name: str
    outcome: str
    detail: str

    @property
    def ok(self) -> bool:
        return self.outcome != FAIL

    def to_json_dict(self) -> dict[str, Any]:
        return {"name": self.name, "outcome": self.outcome, "detail": self.detail}

    @classmethod
    def from_json_dict(cls, data: dict[str, Any]) -> TieOut:
        outcome = _text(data, "outcome")
        if outcome not in _OUTCOMES:
            raise ValueError("a tie-out outcome must be PASS, FAIL or SKIPPED")
        return cls(_text(data, "name"), outcome, _text(data, "detail"))


@dataclass(frozen=True)
class BalanceFigures:
    """The balance sheet that came in the same filing, at its own date."""

    as_of: date
    lines: dict[str, Figure]
    tie_out: tuple[TieOut, ...]

    @property
    def usable(self) -> bool:
        have = all(key in self.lines for key in REQUIRED_BALANCE_LINES)
        return have and all(check.ok for check in self.tie_out)

    def value(self, key: str) -> Decimal | None:
        line = self.lines.get(key)
        return line.value if line else None

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "as_of": self.as_of.isoformat(),
            "lines": {key: line.to_json_dict() for key, line in self.lines.items()},
            "tie_out": [check.to_json_dict() for check in self.tie_out],
        }

    @classmethod
    def from_json_dict(cls, data: dict[str, Any]) -> BalanceFigures:
        as_of = _day(data["as_of"])
        if as_of is None:
            raise ValueError("a balance sheet needs a date")
        return cls(
            as_of,
            {k: Figure.from_json_dict(k, v) for k, v in data["lines"].items()},
            tuple(TieOut.from_json_dict(c) for c in data["tie_out"]),
        )


@dataclass(frozen=True)
class QuarterFigures:
    """One quarterly results filing, read. `status` says whether its figures may feed a metric."""

    symbol: str
    isin: str
    company_name: str
    period_end: date
    period_start: date | None
    period_label: str
    filed_on: date | None
    consolidated: bool
    audited: bool
    source_url: str
    sha256: str
    fetched_at: str
    status: ReadStatus
    note: str = ""
    lines: dict[str, Figure] = field(default_factory=dict)
    tie_out: tuple[TieOut, ...] = ()
    balance: BalanceFigures | None = None

    @property
    def usable(self) -> bool:
        return self.status is ReadStatus.READ_OK

    def value(self, key: str) -> Decimal | None:
        line = self.lines.get(key)
        return line.value if line else None

    def profit_figure(self) -> Figure | None:
        """Profit for the company's owners when filed, else profit for the period (a standalone filing has no split)."""
        return self.lines.get("owners_profit") or self.lines.get("profit_for_period")

    @property
    def shares(self) -> int | None:
        """Shares in issue: paid-up equity capital over face value, when that is a whole positive number."""
        paid, face = self.value("paid_up_capital"), self.value("face_value")
        if paid is None or face is None or paid <= 0 or face <= 0 or paid % face != 0:
            return None
        return int(paid // face)

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "isin": self.isin,
            "company_name": self.company_name,
            "period_end": self.period_end.isoformat(),
            "period_start": self.period_start.isoformat() if self.period_start else None,
            "period_label": self.period_label,
            "filed_on": self.filed_on.isoformat() if self.filed_on else None,
            "consolidated": self.consolidated,
            "audited": self.audited,
            "source_url": self.source_url,
            "sha256": self.sha256,
            "fetched_at": self.fetched_at,
            "status": self.status.value,
            "note": self.note,
            "lines": {key: line.to_json_dict() for key, line in self.lines.items()},
            "tie_out": [check.to_json_dict() for check in self.tie_out],
            "balance": self.balance.to_json_dict() if self.balance else None,
        }

    @classmethod
    def from_json_dict(cls, data: dict[str, Any]) -> QuarterFigures:
        """Rebuild from a stored document. Raises ValueError when it is not a valid one."""
        try:
            end = _day(data["period_end"])
            if end is None:
                raise ValueError("a quarter needs an end date")
            balance = data["balance"]
            return cls(
                symbol=_text(data, "symbol"),
                isin=_text(data, "isin"),
                company_name=_text(data, "company_name"),
                period_end=end,
                period_start=_day(data["period_start"]),
                period_label=_text(data, "period_label"),
                filed_on=_day(data["filed_on"]),
                consolidated=bool(data["consolidated"]),
                audited=bool(data["audited"]),
                source_url=_text(data, "source_url"),
                sha256=_text(data, "sha256"),
                fetched_at=_text(data, "fetched_at"),
                status=ReadStatus(data["status"]),
                note=_text(data, "note"),
                lines={k: Figure.from_json_dict(k, v) for k, v in data["lines"].items()},
                tie_out=tuple(TieOut.from_json_dict(c) for c in data["tie_out"]),
                balance=BalanceFigures.from_json_dict(balance) if balance else None,
            )
        except (KeyError, TypeError, AttributeError) as error:
            raise ValueError(f"the stored filing is malformed ({type(error).__name__})") from None
