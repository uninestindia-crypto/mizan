"""Find paper holdings that crossed a corporate action the ledger has not applied.

A paper ledger holds each position as a share count and a cost basis, and marks it with a live
quote. Live quotes are never back-adjusted. The morning after a 1:1 bonus the quote halves while the
ledger still holds the pre-bonus share count, so the book records a 50% loss that did not happen.
After a demerger it records the parent's fall with no entitlement against it -- which is how HEG put
a Rs 6,124 phantom loss into the XS book in September 2026. The flagship runner had no defence
against either.

This module only finds them. Applying one needs the ratio checked against the data first
(``data/corporate_actions.py``, and the two withdrawn premises recorded in ``CURRENT.md``), and a
guess applied to a ledger is worse than a refusal.

The records are the NSE corporate-action lists the scheduled refresh stores per symbol as
``nse-corporate-actions-<SYMBOL>.json``: a list of objects with an ``exDate`` such as
``07-Sep-2026`` and a free-text ``subject``. The refresh fetches them up to the day before it runs,
so an action whose ex-date is the session day itself is seen from the following session.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

from quant_system.data.corporate_actions import parse_subject_factor


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


def structural_actions_on_holdings(
    holdings: Mapping[str, date],
    session_date: date,
    records: Mapping[str, Sequence[Mapping[str, Any]]],
) -> list[HeldThroughAction]:
    """Every structural action with an ex-date after a holding opened and on or before today.

    ``holdings`` maps each held symbol to the date it was opened. An action whose ex-date is that
    same date is excluded, because the entry was priced after it. Dividends, meetings and buybacks
    are not structural and are ignored: a dividend lowers the price by the payout, which this book
    does not yet credit, but it cannot make the share count wrong. The subject parser decides the
    rest. A split, consolidation or bonus it can size is ``sized``. A demerger, a rights issue, or a
    split or bonus it cannot size is ``unsized``.
    """
    found: set[HeldThroughAction] = set()
    for symbol, opened_on in holdings.items():
        for record in records.get(symbol, ()):
            ex_date = _ex_date(record.get("exDate"))
            if ex_date is None or not opened_on < ex_date <= session_date:
                continue
            subject = str(record.get("subject", ""))
            parts = parse_subject_factor(subject, total_return=False)
            sized = tuple(kind for kind in parts.kinds if kind != "dividend")
            if not sized and not parts.unsized:
                continue
            found.add(HeldThroughAction(symbol, opened_on, ex_date, subject, sized, parts.unsized))
    return sorted(found, key=lambda action: (action.ex_date, action.symbol, action.subject))


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
