"""Assemble a live Mizan feature cross-section from real bars and real macro.

`scripts/run_paper_pilot_session.py` previously built the model's fifteen inputs by hand: `return_5`
was `return_1 * 1.5`, the three macro features were hardcoded constants, `cs_rank_volume_surprise`
was `volume_zscore * 0.2`, and `rsi_14_centered` was clamped to ±50 when its trained range is
±0.45. The model was therefore scored on values no training row ever held, and the two realistic
universes it was pointed at produced **zero** proposals.

This module exists so the live path calls the same kernel training calls —
`modeling.mizan_features` — rather than approximating it. It does no arithmetic on features itself;
it only gathers the inputs the kernel needs and hands them over.

## What "matches the published store" does and does not mean

This docstring previously said the kernel was "verified bit-identical against the published feature
store". That was a one-off manual run restated as a standing property, no test stood behind it, and
a Red Team sweep of all 1,015,831 published rows showed it was **false**: `cs_rank_momentum_5`
differed on 244 rows across 115 of 2,427 dates, because the ranks were sorted after a 10-decimal
text round trip while the builder sorted raw floats.

That sort now takes the raw floats, so the live path follows the builder's procedure, and
`tests/test_mizan_store_fidelity.py` checks it against the committed store — the property is
measured rather than asserted. It does not make those 244 rows reproducible: both names carry
byte-identical published text, so the order the builder derived from raw floats cannot be recovered
from the store at all. Three residual exposures remain, none closed:

* The 244 published rows stay unreproducible, permanently. The test bounds the divergence to the
  tie class rather than eliminating it.

* `math.log` and `math.sqrt` are libm calls. The store, its verification and the paper runner all
  ran on the same Windows ARM64 machine; CI runs on x86-64. A 1-ULP difference is ~1e-18 relative
  against a 1e-10 text quantum, so it can only bite at an exact rounding boundary — but nothing
  measures it, and the store cannot be rebuilt to check.
* The fidelity test samples the store rather than sweeping all of it, so it bounds the claim rather
  than proving it everywhere.

## Why a completed-bar decision

The model was validated deciding on a session close and entering at the next open
(`decision_at` = close, entry = next session). The live path keeps that contract: features come from
**completed** daily bars, so nothing here consumes a partially-formed intraday bar. That also means
a session's decisions can be computed before the market opens.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Final

from quant_system.data.market_data import PointInTimeBar
from quant_system.modeling.mizan_features import (
    MIZAN_CANONICAL_WINDOW_BARS,
    MIZAN_MINIMUM_BARS,
    compute_mizan_cross_section,
)


class MizanLiveFeatureError(RuntimeError):
    """Raised when a live cross-section cannot be assembled faithfully."""


@dataclass(frozen=True, slots=True)
class CrossSectionCoverage:
    """What the assembled cross-section actually covers, for the caller to judge.

    Coverage is reported rather than silently accepted because a cross-sectional rank divides by the
    number of names present: a shrunk cross-section changes every rank, so a caller that wants
    faithful decisions must decide whether the shortfall is tolerable.
    """

    requested: tuple[str, ...]
    scored: tuple[str, ...]
    skipped_short_history: tuple[str, ...]
    skipped_not_computable: tuple[str, ...]
    skipped_extreme: tuple[str, ...] = ()

    @property
    def fraction(self) -> float:
        return len(self.scored) / len(self.requested) if self.requested else 0.0

    def with_extreme_refusals(self, refused: Sequence[str]) -> CrossSectionCoverage:
        """Coverage after the extreme-row guard has dropped names, with those names recorded.

        `skipped_extreme` was declared here and populated by nothing: the refusals were logged and
        then absent from the coverage report, so the guard's stated advantage over clipping -- "a
        refusal is visible in the coverage report" -- was not true. The refused names also stayed
        counted as `scored`, so the coverage fraction described a cross-section that no longer
        existed by the time anything was ranked.
        """
        dropped = frozenset(refused)
        return CrossSectionCoverage(
            requested=self.requested,
            scored=tuple(s for s in self.scored if s not in dropped),
            skipped_short_history=self.skipped_short_history,
            skipped_not_computable=self.skipped_not_computable,
            skipped_extreme=tuple(sorted(dropped)),
        )

    def summary(self) -> str:
        return (
            f"{len(self.scored)}/{len(self.requested)} names scored "
            f"({self.fraction:.1%}); {len(self.skipped_short_history)} short history, "
            f"{len(self.skipped_not_computable)} not computable, "
            f"{len(self.skipped_extreme)} extreme"
        )


def build_live_cross_section(
    bars_by_symbol: Mapping[str, Sequence[PointInTimeBar]],
    *,
    india_vix_by_date: Mapping[str, float],
    nifty_by_date: Mapping[str, float],
    as_of: date | None = None,
) -> tuple[dict[str, dict[str, str]], CrossSectionCoverage]:
    """Compute one decision date's Mizan features for every symbol that can support them.

    ``bars_by_symbol`` holds **completed** daily bars in ascending date order. Each symbol is
    truncated to the trailing :data:`MIZAN_CANONICAL_WINDOW_BARS` ending at ``as_of`` (or at each
    symbol's last bar when ``as_of`` is omitted).

    Returns the cross-section and a :class:`CrossSectionCoverage` describing what was dropped and
    why. The features themselves are computed entirely by ``modeling.mizan_features``.
    """
    if not bars_by_symbol:
        raise MizanLiveFeatureError("no symbols supplied")

    requested = tuple(sorted(bars_by_symbol))
    windows: dict[str, tuple[PointInTimeBar, ...]] = {}
    short: list[str] = []

    for symbol in requested:
        bars = tuple(bars_by_symbol[symbol])
        if as_of is not None:
            bars = tuple(bar for bar in bars if bar.exchange_date <= as_of)
        if len(bars) < MIZAN_MINIMUM_BARS:
            short.append(symbol)
            continue
        windows[symbol] = bars[-MIZAN_CANONICAL_WINDOW_BARS:]

    if not windows:
        raise MizanLiveFeatureError(
            f"no symbol has the {MIZAN_MINIMUM_BARS} bars the feature family needs"
        )

    _require_one_decision_date(windows)

    cross_section = compute_mizan_cross_section(
        windows,
        india_vix_by_date=india_vix_by_date,
        nifty_by_date=nifty_by_date,
    )
    not_computable = tuple(sorted(set(windows) - set(cross_section)))
    coverage = CrossSectionCoverage(
        requested=requested,
        scored=tuple(sorted(cross_section)),
        skipped_short_history=tuple(short),
        skipped_not_computable=not_computable,
    )
    return cross_section, coverage


def select_top_fraction(
    scores: Mapping[str, float],
    fraction: float,
    *,
    score_threshold: float | None = None,
) -> tuple[str, ...]:
    """The top ``fraction`` of a ranked cross-section, strongest first.

    Ties break by symbol ascending so two runs over identical input select identical names. The
    count rounds **up**, so a non-empty cross-section always yields at least one name rather than
    silently abstaining.

    ``score_threshold`` is an optional floor. It has no default: the runner previously compared
    against a hardcoded ``0.035`` while the trial that produced these weights recorded
    ``0.071454840454``, and a threshold invented at execution time is not the rule the model was
    measured under.
    """
    if not 0.0 < fraction <= 1.0:
        raise MizanLiveFeatureError(f"fraction must lie in (0, 1], got {fraction}")
    if not scores:
        return ()
    ranked = sorted(scores.items(), key=lambda pair: (-pair[1], pair[0]))
    population = len(ranked)
    # Round before the ceiling: 0.2 * 50 is 10.000000000000002 in binary float, and a naive
    # math.ceil would take 11 of 50 at an exact 20% boundary.
    take = min(population, max(1, math.ceil(round(fraction * population, 9))))
    chosen = ranked[:take]
    if score_threshold is not None:
        chosen = [pair for pair in chosen if pair[1] > score_threshold]
    return tuple(symbol for symbol, _ in chosen)


def _require_one_decision_date(windows: Mapping[str, Sequence[PointInTimeBar]]) -> None:
    """Every symbol must end on the same session.

    A cross-sectional rank compares names *on one date*. Ranking a name whose last bar is Friday
    against one whose last bar is Wednesday is not the comparison the model was fitted to make, and
    it is the kind of skew that is invisible in the output.
    """
    last_dates = {symbol: bars[-1].exchange_date for symbol, bars in windows.items()}
    distinct = set(last_dates.values())
    if len(distinct) > 1:
        newest = max(distinct)
        stale = sorted(sym for sym, day in last_dates.items() if day != newest)
        raise MizanLiveFeatureError(
            f"cross-section spans {len(distinct)} decision dates; {len(stale)} symbol(s) do not end "
            f"at {newest.isoformat()} (e.g. {stale[0]} at {last_dates[stale[0]].isoformat()}). "
            "Ranking names as of different sessions is not the comparison the model was fitted to "
            "make"
        )


#: How far a standardized feature may sit from the training mean before the row is refused.
#:
#: **This is a percentile choice, roughly p99.95 of the training distribution.** It is not a measured
#: point at which the linear model stops working, and nothing here measures that. Across the full
#: published store, 25 refuses about 0.05% of rows -- 511 of 1,015,831, on 421 of 2,427 dates -- and
#: the large majority are volume spikes.
#:
#: Two earlier justifications for this constant were wrong and are recorded rather than deleted,
#: because both are the same error and it has now been made three times in this repository:
#:
#: * "A limit of 25 sits clear of" the training distribution. It does not. **511 training rows sit
#:   above 25**, the largest at 84,131 sd. The model was fitted on data this guard would refuse; the
#:   limit cuts into the training tail rather than sitting clear of it.
#: * "It is also insensitive: every limit from 25 to 200 refused exactly the same single name." True
#:   of the one cross-section that motivated it, false generally. Limits 25 and 200 disagree on
#:   **411 of 2,427 dates**, refusing 511 rows against 10 -- a 51x difference. A property of one
#:   sampled day was restated as a property of the constant.
#:
#: That is exactly what `agent_context/work/completed/20260822-NOTICE-dsr-two-point-boundary-crash.md`
#: concluded after being caught twice: cite the proportion and the mechanism, never a single sample.
MAX_STANDARDIZED_DEVIATION: Final = 25.0


def refuse_extreme_rows(
    cross_section: Mapping[str, Mapping[str, str]],
    *,
    means: Mapping[str, float],
    scales: Mapping[str, float],
    limit: float = MAX_STANDARDIZED_DEVIATION,
) -> tuple[dict[str, dict[str, str]], tuple[str, ...]]:
    """Drop names whose standardized features would dominate a linear score.

    ``volume_zscore`` is unbounded and heavy-tailed: ``(volume - mean) / max(1, stdev)`` over a
    20-session window explodes when a quiet name prints a block trade. One real example, BBTC on
    2026-08-27, printed 14,319,956 shares against a trailing-20 mean of 33,814 -- a 423x spike --
    giving a raw feature of 565 and, against this model's standardization scale of 2.08, a
    standardized value of 272. Its score came out 14x the next name in a 499-name cross-section.

    The data is correct and the arithmetic is correct; the problem is that a linear model reduces to
    that one term. Refusing the row is honest about the model's working range. It is deliberately a
    **refusal, not a clip**: clipping would feed the model an input no data produced and quietly
    change what it is being asked, whereas a refusal is visible in the coverage report.

    Returns the surviving cross-section and the refused names.
    """
    if limit <= 0:
        raise MizanLiveFeatureError(f"limit must be positive, got {limit}")
    kept: dict[str, dict[str, str]] = {}
    refused: list[str] = []
    for symbol, values in cross_section.items():
        worst = 0.0
        for name, text in values.items():
            scale = scales.get(name, 0.0)
            if scale <= 0.0:
                continue
            worst = max(worst, abs((float(text) - means.get(name, 0.0)) / scale))
        if worst > limit:
            refused.append(symbol)
        else:
            kept[symbol] = dict(values)
    return kept, tuple(sorted(refused))
