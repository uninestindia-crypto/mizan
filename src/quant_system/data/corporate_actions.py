"""Back-adjustment of NSE daily bars for the corporate actions the provider does *not* apply.

The manifest labels these bars ``RAW``, and that label is misleading. Measured across the whole
423-name research universe (``nse-research-universe-liquid-10y.csv``) against the all-market cache,
counting every action that has a bar on its own ex-date:

===========================  =====  ============================================================
Action                       n      Already applied by the provider?
===========================  =====  ============================================================
Split / bonus / consolidation 212   **Yes -- 212 of 212.** Largest ``|ln(ex-date gap)|`` is 0.1035
Dividend                     ~4500  Quote drops by the payout, as it should
Ratio-less demerger          54     **No.** Gaps run from -77.3% (NIITLTD) to +71.0% (NMDC)
===========================  =====  ============================================================

So the naive reading -- "bars are RAW, therefore every action needs applying" -- is wrong, and
acting on it is destructive rather than merely useless: applying TATASTEEL's published 10:1 ratio on
top of an already-adjusted series turned a +4.6% day into **+945%**.

The rule this module follows is therefore to *measure, not assume*. A published structural ratio is
applied only when the bars show the provider has not already applied it, which needs no
per-provider configuration and stays correct if the provider's behaviour changes. Demergers are the
real gap: NSE publishes no ratio for them and the provider does not adjust them, so ABFRL (-63.6%),
VEDL (-62.6%), SIEMENS (-50.3%), TMPV (-39.5%) and HEG (-64.3%) all sit in the cache as fake returns.

How "measure, not assume" is implemented
----------------------------------------
Two hypotheses are scored against the observed ex-date gap, in **log-return space** because returns
compound multiplicatively:

===============================  ==============================
Hypothesis                       Predicted ``ln(gap)``
===============================  ==============================
Provider already applied it      ``0``
Provider did not apply it        ``ln(published_factor)``
===============================  ==============================

The nearer hypothesis wins, and only if the observation sits within :data:`MAX_LOG_RESIDUAL` of it.
An observation near neither is **unresolved**, not silently forced into one.

The previous implementation compared ``|observed - published_factor|`` against an absolute 0.20 in
factor space. That test cannot separate the two hypotheses at all whenever ``|1 - factor| <= 0.40``,
because a single observation then satisfies both -- and it resolved such ties toward "not applied",
double-adjusting a series the provider had already fixed. Measured on the research universe, **57 of
212 published-ratio actions (27%) fell in that blind band**, every one a bonus, including
ICICIBANK 1:10, NTPC 1:5, POWERGRID 1:3, GAIL 1:3, IOC 1:2 and LT 1:2. Under the nearest-hypothesis
test all 212 resolve to "already applied", unanimously and with the largest residual at 0.1035.

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

What cannot be parsed, and is no longer guessed
-----------------------------------------------
NSE publishes demergers with no ratio at all -- the entire vocabulary is ``Demerger``,
``Scheme Of Demerger``, ``Scheme Of Arrangement Of Demerger``. There is no arithmetic that recovers
the ratio from the text.

An earlier revision inferred the size from the ex-date gap whenever that gap exceeded 20%. Measured
across all 54 ratio-less actions in the 423-name research universe, that rule would have inferred an
**upward** correction for three of them -- NMDC ``+71.0%``, BAJAJELEC ``+32.2%``, SCI ``+30.0%``. A
demerger cannot raise the parent's price, so those gaps are market movement or a provider
adjustment, and dividing them out would have erased a genuine move *and* invented a fake one in its
place. The gap is the sum of the corporate action and whatever the market did that day: it is
evidence that something structural happened, never proof of how much.

So this module no longer sizes a ratio-less action from price. It reports one as **unresolved**,
and a consumer computing a return across it refuses the observation rather than publishing a
fabricated one (``adjustment_provenance.spans_unresolved``). A factor may still be *supplied* by a
caller that validated it against evidence outside the gap -- the resulting company's own first
traded price together with the entitlement ratio from the company filing -- via
``validated_factors``. That is a genuinely independent measurement; the gap alone is not.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Final, Literal

__all__ = [
    "INFERRED_GAP_THRESHOLD",
    "MAX_LOG_RESIDUAL",
    "AdjustmentFactor",
    "AdjustmentPlan",
    "BarPoint",
    "CorporateActionError",
    "UnresolvedRecord",
    "ValidatedFactor",
    "adjust_bars",
    "build_adjustment_factors",
    "parse_subject_factor",
]

#: Retained for callers that still import it. **No longer used to size anything.**
#:
#: An earlier revision inferred a demerger's size from its ex-date gap whenever that gap exceeded
#: this value. Measured across the 423-name research universe, that rule inferred an *upward*
#: correction for NMDC (+71.0%), BAJAJELEC (+32.2%) and SCI (+30.0%) -- a demerger cannot raise the
#: parent's price, so those gaps are market movement or a provider adjustment, and "correcting" them
#: would have erased a genuine move and invented a fake one. A gap is the sum of the action and
#: whatever the market did that day; it is evidence that *something* happened, never proof of how
#: much. Ratio-less actions are now reported as unresolved instead. See
#: :class:`~quant_system.data.adjustment_provenance.FactorValidation`.
INFERRED_GAP_THRESHOLD: Final = Decimal("0.20")

#: How far, in log-return space, an observed ex-date gap may sit from a hypothesis and still be
#: judged consistent with it.
#:
#: Returns compound multiplicatively, so the comparison is made on ``ln(gap)``: an absolute
#: tolerance in factor space is asymmetric, treating a halving and a doubling as different sizes of
#: event when they are the same size. Calibrated against the corpus rather than chosen: across all
#: 212 published-ratio structural actions in the research universe, the largest ``|ln(gap)|`` is
#: 0.1035 (ASTRAL, 2019-09-16). 0.15 admits every one of them with margin while still excluding a
#: 1:10 bonus that the provider had genuinely not applied (``|ln(0.9091)| = 0.0953`` from the other
#: hypothesis).
MAX_LOG_RESIDUAL: Final = Decimal("0.15")

FactorSource = Literal["PARSED", "VALIDATED"]
"""``PARSED`` is a published ratio the ex-date gap corroborates. ``VALIDATED`` is a ratio-less
action sized by a caller from evidence outside the gap. ``INFERRED`` has been removed: nothing in
this module sizes an action from a price gap any more."""


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


@dataclass(frozen=True, slots=True)
class ValidatedFactor:
    """A ratio-less action sized from evidence other than its own ex-date gap.

    ``evidence`` must name that evidence -- the resulting company's instrument and first traded
    price, the entitlement ratio and the filing it came from. A caller that cannot fill this in
    does not have a validated factor and should leave the action unresolved.
    """

    factor: Decimal
    evidence: str

    def __post_init__(self) -> None:
        if self.factor <= 0:
            raise CorporateActionError(f"non-positive validated factor {self.factor}")
        if not self.evidence.strip():
            raise CorporateActionError("a validated factor must name its corroborating evidence")


@dataclass(frozen=True, slots=True)
class UnresolvedRecord:
    """An action that happened but whose size is not established.

    Kept rather than dropped. A return measured across one of these spans an event of unknown size,
    which is not a measurement; consumers refuse the observation instead of publishing it.
    """

    ex_date: date
    reason: str
    detail: str
    subject: str


@dataclass(frozen=True, slots=True)
class AdjustmentPlan:
    """Everything one instrument's authority yields: what was sized, what was not, and what was not
    needed."""

    factors: tuple[AdjustmentFactor, ...]
    unresolved: tuple[UnresolvedRecord, ...]
    notes: tuple[str, ...]

    def __iter__(self) -> Iterator[list[Any]]:
        """Backward compatibility with the previous ``factors, skipped`` tuple return.

        Existing callers unpack ``factors, skipped = build_adjustment_factors(...)``. They keep
        working and see unresolved actions in the ``skipped`` list, where the previous contract also
        put them. New callers should read ``.factors`` and ``.unresolved`` separately, because the
        distinction between "not needed" and "could not be sized" is the whole point.
        """
        yield list(self.factors)
        yield [f"{item.ex_date} {item.detail}" for item in self.unresolved] + list(self.notes)


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
_DIVIDEND_RE: Final = re.compile(
    r"(?:rs|re)\.?\s*(\d+(?:\.\d+)?)\s*(?:/-)?\s*per\s+sh(?:are)?\b", re.I
)
"""The ``/-`` suffix and the ``Share``/``Sh`` spelling are both optional, because issuers write both.

The ``per share`` anchor itself is **not** optional, and that is deliberate. Dropping it would let
the amount be read from a face-value figure in the same subject line -- ``Dividend/Face Value Split
From Rs 10/- To Rs 2/-`` would price a Rs 10 dividend that does not exist. Requiring the anchor keeps
161 abbreviated-but-amountless records (``Interim Dividend`` with no figure) unpriced rather than
mispriced.

It was previously absent here while ``_SPLIT_RE`` two lines above already allowed it, so
``Dividend - Rs 4/- Per Share`` parsed to nothing and the payout was silently left in the
series. Measured on the committed authorities before the repair: 493 of 5,083 dividend
records in the research universe (9.7%) were unpriced this way, and because no factor and no
unresolved record were produced, nothing downstream could refuse them.
"""
_SPLIT_HINT: Final = re.compile(r"split|sub-?division|splt", re.I)
_DIVIDEND_HINT: Final = re.compile(r"dividend", re.I)
_RATIOLESS_HINT: Final = re.compile(r"demerger|scheme of arrangement", re.I)
_BONUS_HINT: Final = re.compile(r"bonus", re.I)
_RIGHTS_HINT: Final = re.compile(r"\brights\b", re.I)
"""Structural actions this parser cannot size from the subject line alone.

A rights issue moves the price (the theoretical ex-rights price depends on the subscription
price and the ratio), but sizing it needs more than the text carries. Before these hints
existed a rights record matched **no hint at all**: it produced no factor *and* no unresolved
record, so ``spans_unresolved`` returned ``False`` and a return measured straight through the
ex-rights gap was published as if it were real. 39 such actions exist in the research
universe, plus 3 bonus records whose wording ``_BONUS_RE`` does not match.

Buybacks are deliberately **not** hinted here. A tender-offer buyback has a record date but no
ex-date price adjustment, so treating one as unresolved would refuse 140 windows for no
reason.
"""


_STRUCTURAL_KINDS: Final = frozenset({"split", "consolidation", "bonus"})
"""Kinds that represent a *sized* structural effect. A dividend is not one of them."""


@dataclass(frozen=True, slots=True)
class SubjectComponents:
    """The separable price effects in one authority subject line.

    Structural and dividend effects are kept apart because they are treated differently: the
    provider already applies structural ones, so those are gap-verified before use, while removing
    a dividend is a return-definition choice that no gap can corroborate. A single record routinely
    carries both -- ``Annual General Meeting/Dividend - Rs 10 Per Share/Face Value Split ...`` --
    so collapsing them into one number makes the record impossible to handle correctly.
    """

    structural: Decimal
    dividend: Decimal
    kinds: tuple[str, ...]
    needs_inference: bool

    @property
    def combined(self) -> Decimal:
        return self.structural * self.dividend


def parse_subject_factor(
    subject: str, *, cum_close: Decimal | None = None, total_return: bool = True
) -> SubjectComponents:
    """Split one authority subject line into its separable price effects.

    Each factor is the multiplier for bars before the ex-date; ``1`` means no effect of that kind.
    ``needs_inference`` marks a ratio-less structural action (a demerger) the text cannot size.
    """
    structural = Decimal(1)
    dividend = Decimal(1)
    kinds: list[str] = []

    split_match = _SPLIT_RE.search(subject) if _SPLIT_HINT.search(subject) else None
    if split_match:
        old, new = Decimal(split_match.group(1)), Decimal(split_match.group(2))
        if old > 0 and new > 0 and new != old:
            # new/old covers both directions: a sub-division gives a factor < 1, a
            # consolidation (Re 1 -> Rs 10) gives one > 1. One expression, no special case.
            structural *= new / old
            kinds.append("split" if new < old else "consolidation")

    for a_text, b_text in _BONUS_RE.findall(subject):
        a, b = Decimal(a_text), Decimal(b_text)
        if a > 0 and b > 0:
            # "Bonus a:b" = a new shares for every b held.
            structural *= b / (a + b)
            kinds.append("bonus")

    if total_return and _DIVIDEND_HINT.search(subject) and cum_close is not None and cum_close > 0:
        # A face-value figure inside the split clause is not a dividend. Accepting the ``/-`` suffix
        # made ``Dividend/Face Value Split From Rs 10/- Per Share To Rs 2/- Per Share`` price a Rs 10
        # dividend that does not exist -- a misprice, which is worse than the missing price the
        # suffix fix was closing. So any amount lying inside the split match is skipped.
        split_span = split_match.span() if split_match else None
        for match in _DIVIDEND_RE.finditer(subject):
            if split_span and split_span[0] <= match.start() < split_span[1]:
                continue
            amount = Decimal(match.group(1))
            if 0 < amount < cum_close:
                dividend *= (cum_close - amount) / cum_close
                kinds.append("dividend")
            break

    # Fail closed: a structural action that is *recognised* but not *sized* must be reported
    # unresolved, never passed over in silence. The previous rule asked only whether the text looked
    # ratio-less, so a rights issue -- which matches no hint -- fell through both paths at once. It
    # also used `not kinds`, so a record carrying a dividend *and* a demerger sized the dividend and
    # declared the demerger resolved.
    structural_hinted = bool(
        _SPLIT_HINT.search(subject)
        or _BONUS_HINT.search(subject)
        or _RIGHTS_HINT.search(subject)
        or _RATIOLESS_HINT.search(subject)
    )
    structural_sized = any(kind in _STRUCTURAL_KINDS for kind in kinds)
    needs_inference = structural_hinted and not structural_sized
    return SubjectComponents(structural, dividend, tuple(kinds), needs_inference)


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


def _nearest_hypothesis(
    observed: Decimal, published: Decimal, *, max_log_residual: Decimal
) -> tuple[str, Decimal, Decimal]:
    """Score the observed ex-date gap against both provider hypotheses in log-return space.

    Returns ``(verdict, distance_to_applied, distance_to_unapplied)`` where ``verdict`` is one of
    ``ALREADY_APPLIED``, ``NOT_APPLIED`` or ``MATCHES_NEITHER``.
    """
    log_observed = observed.ln()
    log_unapplied = published.ln()
    to_applied = abs(log_observed)
    to_unapplied = abs(log_observed - log_unapplied)
    if to_unapplied < to_applied and to_unapplied <= max_log_residual:
        return "NOT_APPLIED", to_applied, to_unapplied
    if to_applied <= max_log_residual:
        return "ALREADY_APPLIED", to_applied, to_unapplied
    return "MATCHES_NEITHER", to_applied, to_unapplied


def build_adjustment_factors(
    actions: Iterable[tuple[date, str]],
    bars: Sequence[BarPoint],
    *,
    total_return: bool = True,
    max_log_residual: Decimal = MAX_LOG_RESIDUAL,
    validated_factors: Mapping[date, ValidatedFactor] | None = None,
) -> AdjustmentPlan:
    """Turn ``(ex_date, subject)`` records into a plan against a chronological ``bars`` series.

    ``validated_factors`` supplies sizes for ratio-less actions that a caller established from
    evidence *outside* the ex-date gap -- the resulting company's own first traded price and the
    entitlement ratio from the company filing. Without one, a ratio-less action is reported as
    unresolved; it is never sized from the gap. See the module docstring for why.
    """
    if any(bars[i].on > bars[i + 1].on for i in range(len(bars) - 1)):
        raise CorporateActionError("bars must be in ascending date order")

    supplied = dict(validated_factors or {})
    by_date = {bar.on: i for i, bar in enumerate(bars)}
    factors: list[AdjustmentFactor] = []
    unresolved: list[UnresolvedRecord] = []
    notes: list[str] = []

    for ex_date, subject in sorted(actions, key=lambda item: item[0]):
        cum_close, _ = _prev_close(bars, ex_date)
        parsed = parse_subject_factor(subject, cum_close=cum_close, total_return=total_return)
        index = by_date.get(ex_date)
        observed = (
            bars[index].open / cum_close
            if index is not None and cum_close is not None and cum_close > 0
            else None
        )

        # --- structural: split, bonus, consolidation ---
        #
        # Scored against both hypotheses rather than tested against one. Measured on the research
        # universe: all 212 published-ratio actions resolve to ALREADY_APPLIED, so this branch
        # almost never fires -- which is the point. It fires if the provider ever stops adjusting.
        if parsed.structural != 1:
            structural_kinds = tuple(k for k in parsed.kinds if k != "dividend")
            if observed is None or observed <= 0:
                unresolved.append(
                    UnresolvedRecord(
                        ex_date,
                        "NO_EX_DATE_BAR",
                        f"no bar on the ex-date, so neither hypothesis can be scored: "
                        f"{subject.strip()}",
                        subject.strip(),
                    )
                )
            else:
                verdict, to_applied, to_unapplied = _nearest_hypothesis(
                    observed, parsed.structural, max_log_residual=max_log_residual
                )
                if verdict == "NOT_APPLIED":
                    factors.append(
                        AdjustmentFactor(
                            ex_date,
                            parsed.structural,
                            structural_kinds,
                            "PARSED",
                            f"{subject.strip()} (gap {float(observed - 1):+.2%} matches the "
                            f"published ratio; residual {float(to_unapplied):.4f})",
                        )
                    )
                elif verdict == "ALREADY_APPLIED":
                    notes.append(
                        f"{ex_date} structural action already applied by the provider "
                        f"(gap {float(observed - 1):+.2%}, published ratio "
                        f"{float(parsed.structural):.4f}, residual {float(to_applied):.4f}): "
                        f"{subject.strip()}"
                    )
                else:
                    unresolved.append(
                        UnresolvedRecord(
                            ex_date,
                            "MATCHES_NEITHER_HYPOTHESIS",
                            f"gap {float(observed - 1):+.2%} sits {float(to_applied):.4f} from "
                            f"'already applied' and {float(to_unapplied):.4f} from the published "
                            f"ratio {float(parsed.structural):.4f}; both exceed "
                            f"{float(max_log_residual):.4f}",
                            subject.strip(),
                        )
                    )

        # --- dividend ---
        #
        # Not gap-verified, and deliberately so. The quote really does drop by the payout, so no
        # gap can distinguish "already applied" from "correctly quoted". Removing it is a
        # return-definition choice -- total return rather than price return -- not the repair of a
        # provider error.
        if parsed.dividend != 1:
            factors.append(
                AdjustmentFactor(ex_date, parsed.dividend, ("dividend",), "PARSED", subject.strip())
            )

        # --- ratio-less structural action, i.e. a demerger ---
        #
        # Never sized from the gap. Either a caller supplies an independently validated factor, or
        # the action is unresolved and every return spanning it is refused.
        if parsed.needs_inference:
            validated = supplied.pop(ex_date, None)
            if validated is not None:
                factors.append(
                    AdjustmentFactor(
                        ex_date,
                        validated.factor,
                        ("demerger",),
                        "VALIDATED",
                        f"{subject.strip()} :: {validated.evidence}",
                    )
                )
            else:
                gap_text = (
                    f"observed gap {float(observed - 1):+.2%}"
                    if observed is not None
                    else "no ex-date bar"
                )
                unresolved.append(
                    UnresolvedRecord(
                        ex_date,
                        "RATIO_NOT_PUBLISHED",
                        f"no usable ratio could be parsed from this action and no independently "
                        f"validated factor was supplied ({gap_text}); the gap alone is not proof "
                        f"of the amount",
                        subject.strip(),
                    )
                )

    for leftover_date, leftover in sorted(supplied.items()):
        notes.append(
            f"{leftover_date} supplied validated factor {float(leftover.factor):.6f} matched no "
            f"ratio-less action in the authority and was not applied"
        )

    factors.sort(key=lambda item: item.ex_date)
    unresolved.sort(key=lambda item: item.ex_date)
    return AdjustmentPlan(tuple(factors), tuple(unresolved), tuple(notes))


# --- application -----------------------------------------------------------------------------


def adjust_bars(
    bars: Sequence[BarPoint],
    factors: Sequence[AdjustmentFactor],
    *,
    allow_validated: bool = True,
) -> list[BarPoint]:
    """Back-adjust ``bars`` so the whole series is expressed in the newest share basis.

    Set ``allow_validated=False`` to use only factors whose ratio the authority itself published,
    refusing ones a caller established from external evidence. Every factor reaching here is either
    ``PARSED`` or ``VALIDATED``; nothing sized from a bare price gap can arrive, because
    :func:`build_adjustment_factors` no longer produces one.
    """
    usable = [f for f in factors if allow_validated or f.source == "PARSED"]
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
