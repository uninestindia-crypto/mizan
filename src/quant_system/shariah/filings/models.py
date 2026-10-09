"""Plain data for the filings engine. Money is Decimal and nothing here touches the network."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Any

SYMBOL_PATTERN = re.compile(r"[A-Za-z0-9&-]{1,15}")
_TAG = re.compile(r"<[^>]*>")
#: Periods whose filing normally carries a balance sheet (half-year and year end).
BALANCE_SHEET_PERIODS = frozenset({"second quarter", "fourth quarter", "first half", "second half"})


class ReadStatus(StrEnum):
    READ_OK = "READ_OK"
    READ_PARTIAL = "READ_PARTIAL"
    TIE_OUT_FAILED = "TIE_OUT_FAILED"
    FORMAT_NOT_READ = "FORMAT_NOT_READ"
    NO_BALANCE_SHEET = "NO_BALANCE_SHEET"


def normalize_symbol(symbol: str) -> str | None:
    """The upper-case NSE symbol, or None when it is not a plausible one."""
    text = symbol if isinstance(symbol, str) else ""
    return text.upper() if SYMBOL_PATTERN.fullmatch(text) else None


def clean_text(value: object, limit: int) -> str:
    """Text from outside the app: no markup, no control characters, one line, bounded."""
    text = _TAG.sub(" ", str(value))
    kept: list[str] = []
    for char in text:
        category = unicodedata.category(char)
        if char in "<>" or category == "Cc":
            kept.append(" ")
        elif category[0] != "C":
            kept.append(char)
    return " ".join("".join(kept).split())[:limit]


def shares_from(paid_up: Decimal | None, face_value: Decimal | None) -> int | None:
    """Paid-up capital over face value, when that is a positive whole number of shares."""
    if paid_up is None or face_value is None or paid_up <= 0 or face_value <= 0:
        return None
    if paid_up % face_value != 0:
        return None
    return int(paid_up // face_value)


@dataclass(frozen=True)
class IndustryGroup:
    name: str
    industry: str
    isin: str


@dataclass(frozen=True)
class ResultRow:
    """One line of NSE's list of a company's results filings."""

    symbol: str
    company_name: str
    isin: str
    period_end: date
    relating_to: str
    period_kind: str
    consolidated: bool
    audited: bool
    ind_as: bool
    lender_flag: str
    filed_on: date | None
    xbrl_url: str
    detail_url: str | None

    @property
    def format_kind(self) -> str:
        if self.lender_flag == "B":
            return "BANK"
        if self.lender_flag == "F":
            return "NBFC"
        if self.lender_flag != "N":
            return "OTHER"
        return "IND_AS" if self.ind_as else "NON_IND_AS"

    @property
    def carries_balance_sheet_hint(self) -> bool:
        return self.relating_to.strip().lower() in BALANCE_SHEET_PERIODS


@dataclass(frozen=True)
class FilingProof:
    source_url: str
    detail_url: str | None
    period_end: date
    period_label: str
    filed_on: date | None
    consolidated: bool
    audited: bool
    ind_as: bool
    sha256: str
    fetched_at: str

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "source_url": self.source_url,
            "detail_url": self.detail_url,
            "period_end": self.period_end.isoformat(),
            "period_label": self.period_label,
            "filed_on": self.filed_on.isoformat() if self.filed_on else None,
            "consolidated": self.consolidated,
            "audited": self.audited,
            "ind_as": self.ind_as,
            "sha256": self.sha256,
            "fetched_at": self.fetched_at,
        }

    @classmethod
    def from_json_dict(cls, data: dict[str, Any]) -> FilingProof:
        filed = data["filed_on"]
        return cls(
            source_url=_text(data, "source_url"),
            detail_url=data["detail_url"],
            period_end=date.fromisoformat(_text(data, "period_end")),
            period_label=_text(data, "period_label"),
            filed_on=date.fromisoformat(filed) if filed else None,
            consolidated=bool(data["consolidated"]),
            audited=bool(data["audited"]),
            ind_as=bool(data["ind_as"]),
            sha256=_text(data, "sha256"),
            fetched_at=_text(data, "fetched_at"),
        )


@dataclass(frozen=True)
class FigureLine:
    xbrl_tag: str
    label: str
    value_inr: Decimal
    context: str
    decimals: str | None = None

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "xbrl_tag": self.xbrl_tag,
            "label": self.label,
            "value_inr": str(self.value_inr),
            "context": self.context,
            "decimals": self.decimals,
        }

    @classmethod
    def from_json_dict(cls, key: str, data: dict[str, Any]) -> FigureLine:
        raw = data["value_inr"]
        if not isinstance(raw, str):
            raise ValueError(f"lines.{key}.value_inr must be text, not a number")
        try:
            value = Decimal(raw)
        except InvalidOperation:
            raise ValueError(f"lines.{key}.value_inr is not a number") from None
        return cls(
            _text(data, "xbrl_tag"),
            _text(data, "label"),
            value,
            _text(data, "context"),
            data["decimals"],
        )

    def rounding_inr(self) -> Decimal:
        """Half of the unit the filer rounded to (INR 0.5 crore when filed to the nearest crore)."""
        try:
            places = int(self.decimals) if self.decimals is not None else 0
        except ValueError:
            return Decimal(0)
        return Decimal(10) ** (-places) / 2 if places < 0 else Decimal(0)


@dataclass(frozen=True)
class TieOutCheck:
    name: str
    ok: bool
    detail: str

    def to_json_dict(self) -> dict[str, Any]:
        return {"name": self.name, "ok": self.ok, "detail": self.detail}

    @classmethod
    def from_json_dict(cls, data: dict[str, Any]) -> TieOutCheck:
        return cls(_text(data, "name"), bool(data["ok"]), _text(data, "detail"))


@dataclass(frozen=True)
class FilingFigures:
    symbol: str
    isin: str
    company_name: str
    proof: FilingProof
    lines: dict[str, FigureLine]
    tie_out: tuple[TieOutCheck, ...]
    read_status: ReadStatus
    read_note: str = ""
    segment_names: tuple[str, ...] = ()

    def value(self, key: str) -> Decimal | None:
        line = self.lines.get(key)
        return line.value_inr if line else None

    @property
    def shares_in_issue(self) -> int | None:
        return shares_from(self.value("paid_up_equity_capital"), self.value("face_value"))

    def to_json_dict(self) -> dict[str, Any]:
        shares = self.shares_in_issue
        return {
            "symbol": self.symbol,
            "isin": self.isin,
            "company_name": self.company_name,
            "proof": self.proof.to_json_dict(),
            "lines": {key: line.to_json_dict() for key, line in self.lines.items()},
            "shares_in_issue": str(shares) if shares is not None else None,
            "tie_out": [check.to_json_dict() for check in self.tie_out],
            "read_status": self.read_status.value,
            "read_note": self.read_note,
            "segment_names": list(self.segment_names),
        }

    @classmethod
    def from_json_dict(cls, data: dict[str, Any]) -> FilingFigures:
        """Rebuild from a stored document. Raises ValueError when it is not a valid one."""
        for key in ("symbol", "isin", "company_name", "proof", "lines", "tie_out", "read_status"):
            if key not in data:
                raise ValueError(f"the stored filing is missing {key}")
        try:
            return cls(
                symbol=_text(data, "symbol"),
                isin=_text(data, "isin"),
                company_name=_text(data, "company_name"),
                proof=FilingProof.from_json_dict(data["proof"]),
                lines={k: FigureLine.from_json_dict(k, v) for k, v in data["lines"].items()},
                tie_out=tuple(TieOutCheck.from_json_dict(c) for c in data["tie_out"]),
                read_status=ReadStatus(data["read_status"]),
                read_note=str(data.get("read_note", "")),
                segment_names=tuple(str(name) for name in data.get("segment_names", ())),
            )
        except (KeyError, TypeError, AttributeError) as error:
            raise ValueError(f"the stored filing is malformed ({type(error).__name__})") from None


def _text(data: dict[str, Any], key: str) -> str:
    value = data[key]
    if not isinstance(value, str):
        raise ValueError(f"{key} must be text")
    return value
