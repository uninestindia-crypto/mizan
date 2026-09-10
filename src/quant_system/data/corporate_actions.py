"""Total-return back-adjustment of NSE daily bars for corporate actions.

Bars acquired from the provider are ``RAW``: a split, bonus or demerger re-bases the quoted price
overnight and nothing in the pipeline compensated. HEG demerged on 2026-09-07 and its series shows a
-64.3% gap that is not a return; the same discontinuity sits in the ten-year training corpus **250
times** inside the research universe alone, where a model reads each one as a genuine ±30-60% day.

This module turns an authority's action records into per-ex-date factors and applies them backwards,
so a series is expressed continuously in its most recent share basis.

Convention
----------
On the ex-date the quote drops. Bars strictly **before** it are on the old basis, so they are scaled
by the cumulative product of every factor whose ex-date is later::

    adjusted[t] = raw[t] * prod(f_k for k where ex_date_k > date_t)

Factors are therefore ``< 1`` for splits, bonuses and dividends, and the newest bar is never
adjusted. Volume moves the other way -- a 5:1 split multiplies share count by 5 -- so historical
volume is divided by the same product.

Total return
------------
``total_return=True`` (the configured policy) also removes dividends, so a payout is not read as a
loss. The factor is ``(P - D) / P`` against the last cum-dividend close. This makes training returns
**inconsistent with the paper books, which credit no dividends** -- a deliberate, recorded choice.

What cannot be parsed
---------------------
NSE publishes demergers with no ratio at all -- the entire vocabulary is ``Demerger``,
``Scheme Of Demerger``, ``Scheme Of Arrangement Of Demerger``. There is no arithmetic that recovers
the ratio from the text, so it is inferred from the ex-date gap, and **only** when the gap is too
large to be an ordinary session. Every inferred factor is labelled ``INFERRED`` so a consumer can
refuse it. An action that can be neither parsed nor safely inferred is reported, never guessed.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Final, Literal

__all__ = [
    "INFERRED_GAP_THRESHOLD",
    "AdjustmentFactor",
    "BarPoint",
    "CorporateActionError",
    "adjust_bars",
    "build_adjustment_factors",
    "parse_subject_factor",
]

#: Minimum absolute overnight gap before a ratio-less action may be inferred from price.
#:
#: A demerger carries no ratio, so the only evidence of its size is the gap itself. Inferring from a
#: small gap would silently absorb ordinary volatility into a "corporate action", which is a worse
#: error than leaving the action unadjusted: it would fabricate a correction nothing asked for. 20%
#: is well outside a normal NSE session and comfortably inside every structural break measured in
#: this cache (the smallest was 31.3%).
INFERRED_GAP_THRESHOLD: Final = Decimal("0.20")

FactorSource = Literal["PARSED", "INFERRED"]


class CorporateActionError(ValueError):
    """A corporate action could not be turned into a defensible factor."""


@dataclass(frozen=True, slots=True)
class BarPoint:
    """One daily bar, in the provider's own units."""

    on: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int


@dataclass(frozen=True, slots=True)
class AdjustmentFactor:
    """The price multiplier applied to every bar *before* ``ex_date``."""

    ex_date: date
    factor: Decimal
    kinds: tuple[str, ...]
    source: FactorSource
    detail: str

    def __post_init__(self) -> None:
        if self.factor <= 0:
            raise CorporateActionError(f"non-positive factor {self.factor} on {self.ex_date}")


# --- subject parsing -------------------------------------------------------------------------
#
# Written against the strings the authority actually holds, not an idealised grammar. Real examples:
#
#   Face Value Split (Sub-Division) - From Rs 10/- Per Share To Rs 2/- Per Share
#   Face Value Split From Rs 10 To Re 1
#   Fv Splt Frm Rs 10 To Rs 2                     <- abbreviated, and it hides outside every
#                                                    keyword bucket a naive filter would use
#   Bonus 1:1/Face Value Split (Sub-Division) - From Rs 10/- Per Share To Rs 2/- Per Share
#   Annual General Meeting/Dividend - Rs 10 Per Share/Face Value Split ...
#
# A single record can carry a dividend *and* a bonus *and* a split, so every component is matched
# independently and the factors multiply.

_SPLIT_RE: Final = re.compile(
    r"(?:from|frm)\s*(?:rs|re)?\.?\s*(\d+(?:\.\d+)?)\s*(?:/-)?\s*(?:per\s+share)?\s*"
    r"to\s*(?:rs|re)?\.?\s*(\d+(?:\.\d+)?)",
    re.I,
)
_BONUS_RE: Final = re.compile(r"bonus\s*(\d+)\s*:\s*(\d+)", re.I)
_DIVIDEND_RE: Final = re.compile(r"(?:rs|re)\.?\s*(\d+(?:\.\d+)?)\s*per\s+share", re.I)
_SPLIT_HINT: Final = re.compile(r"split|sub-?division|splt", re.I)
_DIVIDEND_HINT: Final = re.compile(r"dividend", re.I)
_RATIOLESS_HINT: Final = re.compile(r"demerger|scheme of arrangement", re.I)


def parse_subject_factor(
    subject: str, *, cum_close: Decimal | None = None, total_return: bool = True
) -> tuple[Decimal, tuple[str, ...], bool]:
    """Return ``(factor, kinds, needs_inference)`` for one authority subject line.

    ``factor`` is the multiplier for bars before the ex-date; ``1`` means no price effect.
    ``needs_inference`` marks a ratio-less structural action (a demerger) that the text cannot size.
    """
    factor = Decimal(1)
    kinds: list[str] = []

    if _SPLIT_HINT.search(subject):
        match = _SPLIT_RE.search(subject)
        if match:
            old, new = Decimal(match.group(1)), Decimal(match.group(2))
            if old > 0 and new > 0 and new != old:
                # new/old covers both directions: a sub-division gives a factor < 1, a
                # consolidation (Re 1 -> Rs 10) gives one > 1. One expression, no special case.
                factor *= new / old
                kinds.append("split" if new < old else "consolidation")

    for a_text, b_text in _BONUS_RE.findall(subject):
        a, b = Decimal(a_text), Decimal(b_text)
        if a > 0 and b > 0:
            # "Bonus a:b" = a new shares for every b held.
            factor *= b / (a + b)
            kinds.append("bonus")

    if total_return and _DIVIDEND_HINT.search(subject):
        match = _DIVIDEND_RE.search(subject)
        if match and cum_close is not None and cum_close > 0:
            amount = Decimal(match.group(1))
            if 0 < amount < cum_close:
                factor *= (cum_close - amount) / cum_close
                kinds.append("dividend")

    needs_inference = bool(_RATIOLESS_HINT.search(subject)) and not kinds
    return factor, tuple(kinds), needs_inference


# --- factor construction ---------------------------------------------------------------------


def _prev_close(bars: Sequence[BarPoint], ex_date: date) -> tuple[Decimal | None, int | None]:
    """Last close strictly before ``ex_date``, with its index."""
    found: tuple[Decimal | None, int | None] = (None, None)
    for i, bar in enumerate(bars):
        if bar.on < ex_date:
            found = (bar.close, i)
        else:
            break
    return found


def build_adjustment_factors(
    actions: Iterable[tuple[date, str]],
    bars: Sequence[BarPoint],
    *,
    total_return: bool = True,
    gap_threshold: Decimal = INFERRED_GAP_THRESHOLD,
) -> tuple[list[AdjustmentFactor], list[str]]:
    """Turn ``(ex_date, subject)`` records into factors against a chronological ``bars`` series.

    Returns the factors and a list of human-readable notes for actions that were skipped, so a
    caller can report what was not handled instead of silently proceeding as if it were.
    """
    if any(bars[i].on > bars[i + 1].on for i in range(len(bars) - 1)):
        raise CorporateActionError("bars must be in ascending date order")

    by_date = {bar.on: i for i, bar in enumerate(bars)}
    factors: list[AdjustmentFactor] = []
    skipped: list[str] = []

    for ex_date, subject in sorted(actions, key=lambda item: item[0]):
        cum_close, _ = _prev_close(bars, ex_date)
        factor, kinds, needs_inference = parse_subject_factor(
            subject, cum_close=cum_close, total_return=total_return
        )

        if kinds:
            factors.append(
                AdjustmentFactor(ex_date, factor, tuple(kinds), "PARSED", subject.strip())
            )
            continue

        if not needs_inference:
            continue  # No price effect: AGM, EGM, interest payment, rights, buy-back.

        # Ratio-less structural action. The gap is the only evidence of its size.
        index = by_date.get(ex_date)
        if index is None or cum_close is None or cum_close <= 0:
            skipped.append(f"{ex_date} no bar or no prior close for ratio-less action: {subject!r}")
            continue
        ratio = bars[index].open / cum_close
        if abs(ratio - 1) < gap_threshold:
            skipped.append(
                f"{ex_date} ratio-less action with only a {float(ratio - 1):+.2%} gap, "
                f"too small to size safely: {subject!r}"
            )
            continue
        factors.append(
            AdjustmentFactor(
                ex_date,
                ratio,
                ("demerger",),
                "INFERRED",
                f"{subject.strip()} (gap {float(ratio - 1):+.2%})",
            )
        )

    return factors, skipped


# --- application -----------------------------------------------------------------------------


def adjust_bars(
    bars: Sequence[BarPoint],
    factors: Sequence[AdjustmentFactor],
    *,
    allow_inferred: bool = True,
) -> list[BarPoint]:
    """Back-adjust ``bars`` so the whole series is expressed in the newest share basis.

    Set ``allow_inferred=False`` to refuse factors that were sized from a price gap rather than
    from the authority text.
    """
    usable = [f for f in factors if allow_inferred or f.source == "PARSED"]
    if not usable:
        return list(bars)

    ordered = sorted(usable, key=lambda f: f.ex_date)
    out: list[BarPoint] = []
    # Walk backwards accumulating the product of every factor still ahead of the current bar.
    cumulative = Decimal(1)
    cursor = len(ordered) - 1
    for bar in reversed(bars):
        while cursor >= 0 and ordered[cursor].ex_date > bar.on:
            cumulative *= ordered[cursor].factor
            cursor -= 1
        if cumulative == 1:
            out.append(bar)
        else:
            out.append(
                BarPoint(
                    on=bar.on,
                    open=bar.open * cumulative,
                    high=bar.high * cumulative,
                    low=bar.low * cumulative,
                    close=bar.close * cumulative,
                    # Share count moves inversely to price, so historical volume is rescaled to the
                    # same basis. Truncation is deliberate: a share count is an integer.
                    volume=int(Decimal(bar.volume) / cumulative),
                )
            )
    out.reverse()
    return out
