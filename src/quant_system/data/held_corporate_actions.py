"""Corporate actions on held positions: finding the ones not yet applied, and sizing an adjustment.

A paper ledger holds each position as a share count and a cost basis, and marks it with a live
quote. Live quotes are never back-adjusted. The morning after a 1:1 bonus the quote halves while the
ledger still holds the pre-bonus share count, so the book records a 50% loss that did not happen.
After a demerger it records the parent's fall with no entitlement against it -- which is how HEG put
a Rs 6,124 phantom loss into the XS book in September 2026. Neither book defended against the first
case, and the flagship defended against neither.

Both books now use this module. The flagship refuses to trade a holding carried across an action no
one has reviewed, and the XS paper watch declines to value such a leg. A person reviews each action
against the company's filing and records it with ``scripts/apply_paper_corporate_action.py``. A
split, consolidation or bonus changes the share count and the cost per share and keeps total cost;
anything else is acknowledged with a stated reason. Nothing here applies an action on its own: the
ratio is confirmed by a person and cross-checked against what NSE published, because a guess applied
to a ledger is worse than a refusal (``data/corporate_actions.py``, and the two withdrawn premises in
``CURRENT.md``).

The records are the NSE corporate-action lists the scheduled refresh stores per symbol as
``nse-corporate-actions-<SYMBOL>.json``: a list of objects with an ``exDate`` such as
``07-Sep-2026`` and a free-text ``subject``. The refresh fetches them up to the day before it runs,
so an action whose ex-date is the session day itself is seen from the following session.
"""

from __future__ import annotations

import json
import math
from collections.abc import Container, Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, localcontext
from fractions import Fraction
from pathlib import Path
from typing import Any

from quant_system.data.corporate_actions import parse_subject_factor

#: Components of a subject line that change the share count by a ratio the line can state.
_SIZEABLE: frozenset[str] = frozenset({"split", "consolidation", "bonus"})


@dataclass(frozen=True, slots=True)
class HeldThroughAction:
    """One structural corporate action whose ex-date fell inside a holding's window."""

    symbol: str
    opened_on: date
    ex_date: date
    subject: str
    #: Splits, consolidations and bonuses whose ratio the subject line states.
    sized: tuple[str, ...]
    #: Demergers, rights issues, and any split or bonus whose ratio could not be read.
    unsized: tuple[str, ...]

    def describe(self) -> str:
        kinds = ", ".join((*self.sized, *self.unsized))
        return (
            f"{self.symbol}: held since {self.opened_on.isoformat()} across its "
            f"{self.ex_date.isoformat()} {kinds} ({self.subject.strip()})"
        )


def _ex_date(value: object) -> date | None:
    """NSE writes ``07-Sep-2026``. Anything else, including its ``-`` placeholder, is no date."""
    if not isinstance(value, str):
        return None
    try:
        return datetime.strptime(value.strip(), "%d-%b-%Y").date()
    except ValueError:
        return None


def _structural_parts(subject: str) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """The sized and unsized structural components of one subject line; both empty if none."""
    parts = parse_subject_factor(subject, total_return=False)
    return tuple(kind for kind in parts.kinds if kind != "dividend"), parts.unsized


def structural_actions_on_holdings(
    holdings: Mapping[str, date],
    session_date: date,
    records: Mapping[str, Sequence[Mapping[str, Any]]],
    reviewed: Container[tuple[str, date]] = frozenset(),
) -> list[HeldThroughAction]:
    """Every unreviewed structural action with an ex-date after a holding opened, up to today.

    ``holdings`` maps each held symbol to the date it was opened. An action whose ex-date is that
    same date is excluded, because the entry was priced after it. Dividends, meetings and buybacks
    are not structural and are ignored: a dividend lowers the price by the payout, which this book
    does not yet credit, but it cannot make the share count wrong. The subject parser decides the
    rest. A split, consolidation or bonus it can size is ``sized``. A demerger, a rights issue, or a
    split or bonus it cannot size is ``unsized``. ``reviewed`` holds the ``(symbol, ex_date)`` pairs
    a person has already recorded, and those are skipped.
    """
    found: set[HeldThroughAction] = set()
    for symbol, opened_on in holdings.items():
        for record in records.get(symbol, ()):
            ex_date = _ex_date(record.get("exDate"))
            if ex_date is None or not opened_on < ex_date <= session_date:
                continue
            if (symbol, ex_date) in reviewed:
                continue
            subject = str(record.get("subject", ""))
            sized, unsized = _structural_parts(subject)
            if not sized and not unsized:
                continue
            found.add(HeldThroughAction(symbol, opened_on, ex_date, subject, sized, unsized))
    return sorted(found, key=lambda action: (action.ex_date, action.symbol, action.subject))


def structural_subjects_on(records: Sequence[Mapping[str, Any]], ex_date: date) -> list[str]:
    """The subject lines of one symbol's structural records dated ``ex_date``, in record order."""
    subjects: list[str] = []
    for record in records:
        if _ex_date(record.get("exDate")) != ex_date:
            continue
        subject = str(record.get("subject", ""))
        sized, unsized = _structural_parts(subject)
        if (sized or unsized) and subject not in subjects:
            subjects.append(subject)
    return subjects


def load_nse_corporate_actions(
    directory: Path, symbols: Iterable[str]
) -> tuple[dict[str, list[dict[str, Any]]], list[str]]:
    """The stored NSE records for ``symbols``, and the symbols with no readable record file.

    A missing or unreadable file comes back as missing, never as an empty list. "No record" and "no
    corporate action" are different statements, and reading the first as the second is the defect
    the corporate-action authority repair at ``ee1b0cb3`` removed.
    """
    records: dict[str, list[dict[str, Any]]] = {}
    missing: list[str] = []
    for symbol in sorted(set(symbols)):
        path = directory / f"nse-corporate-actions-{symbol}.json"
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            missing.append(symbol)
            continue
        if not isinstance(payload, list):
            missing.append(symbol)
            continue
        records[symbol] = [entry for entry in payload if isinstance(entry, dict)]
    return records, missing


# --- sizing an adjustment --------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ShareAdjustment:
    """What a sized structural action does to a holding: new shares for each old share."""

    label: str
    multiplier: Fraction


def _ratio(text: str, what: str) -> tuple[Fraction, Fraction]:
    left, sep, right = text.partition(":")
    if not sep:
        raise ValueError(f"{what} must be written A:B, got {text!r}")
    try:
        a, b = Fraction(Decimal(left.strip())), Fraction(Decimal(right.strip()))
    except (InvalidOperation, ValueError) as error:
        raise ValueError(f"{what} must be written A:B with numbers, got {text!r}") from error
    if a <= 0 or b <= 0:
        raise ValueError(f"{what} must be positive on both sides, got {text!r}")
    return a, b


def parse_face_value(text: str) -> ShareAdjustment:
    """``FROM:TO`` face value, as NSE writes it: ``10:2`` is a 1-for-5 split, ``1:10`` a 10-for-1
    consolidation. Each old share becomes ``FROM / TO`` new ones."""
    old, new = _ratio(text, "a face-value change")
    if old == new:
        raise ValueError(f"a face-value change must change the face value, got {text!r}")
    kind = "split" if new < old else "consolidation"
    return ShareAdjustment(f"face value {text.strip()} ({kind})", old / new)


def parse_bonus(text: str) -> ShareAdjustment:
    """``A:B``, as NSE writes it: ``A`` new shares for every ``B`` held, so ``B`` become ``A + B``."""
    new, held = _ratio(text, "a bonus ratio")
    return ShareAdjustment(f"bonus {text.strip()}", (new + held) / held)


def combine(adjustments: Sequence[ShareAdjustment]) -> ShareAdjustment:
    """One record can carry a split and a bonus together; their effects multiply."""
    if not adjustments:
        raise ValueError("no adjustment given")
    multiplier = Fraction(1)
    for adjustment in adjustments:
        multiplier *= adjustment.multiplier
    return ShareAdjustment(" + ".join(a.label for a in adjustments), multiplier)


@dataclass(frozen=True, slots=True)
class AdjustedHolding:
    """A holding after a sized action: whole shares, the same total cost, and what was dropped."""

    quantity: int
    average_cost: Decimal
    #: The part of a share the ratio produced that a whole-share book cannot hold. The issuer pays
    #: cash in lieu; that cash is not credited here, so the book shows it as a small loss.
    fractional_shares: Fraction


def adjust_holding(
    quantity: int, average_cost: Decimal, adjustment: ShareAdjustment
) -> AdjustedHolding:
    """Apply ``adjustment`` to one holding, keeping its total cost.

    The share count is floored, as depositories credit whole shares. The cost per share is total
    cost over the new count, so neither cash nor realized P&L moves: a split is not a trade.
    """
    if quantity <= 0:
        raise ValueError(f"cannot adjust a holding of {quantity} shares")
    if average_cost <= 0:
        raise ValueError(f"cannot adjust a holding with cost {average_cost}")
    exact = Fraction(quantity) * adjustment.multiplier
    new_quantity = math.floor(exact)
    if new_quantity < 1:
        raise ValueError(
            f"{adjustment.label} leaves {quantity} share(s) as {float(exact):.4f}, under one whole "
            "share; this needs a person, not a formula"
        )
    with localcontext() as ctx:
        ctx.prec = 28
        new_cost = (average_cost * quantity / new_quantity).quantize(Decimal("0.000001"))
    return AdjustedHolding(new_quantity, new_cost, exact - new_quantity)


def published_ratio_agrees(adjustment: ShareAdjustment, subject: str) -> bool | None:
    """Whether an NSE subject line states the same ratio: ``True``, ``False``, or ``None`` when the
    line states none that can be read.

    The parser gives the factor for prices before the ex-date, the reciprocal of the share
    multiplier, so the two agree when their product is one.
    """
    parts = parse_subject_factor(subject, total_return=False)
    if not _SIZEABLE & set(parts.kinds):
        return None
    with localcontext() as ctx:
        ctx.prec = 28
        product = (
            parts.structural
            * Decimal(adjustment.multiplier.numerator)
            / Decimal(adjustment.multiplier.denominator)
        )
    return abs(product - 1) <= Decimal("1e-12")
