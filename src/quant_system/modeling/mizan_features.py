"""The single implementation of the Mizan v3 cross-sectional feature family.

Until this module existed the family was computed only inside
``scripts/build_mizan_feature_store.py``, and ``pooled.build_mizan_feature_dataset`` took the values
as an *argument*. Training therefore had an implementation and execution had none, so any execution
path would have had to write a second one — the defect class
``agent_context/decisions/20260824-canonical-feature-window.md`` exists to prevent, and the reason
the v2 kernel was promoted to a shared boundary in the first place.

The arithmetic here is promoted **verbatim** from the store builder. It is deliberately float rather
than Decimal: fidelity to what training actually computed outranks arithmetic purity, exactly as
``execution.governed_strategy.score_row`` calls the validated scorer instead of a "better" Decimal
reimplementation that disagreed by 4e-13 and flipped a decision at the threshold.

## The canonical window, and why 400

``MIZAN_WINDOW_BARS`` is 51: a 50-session SMA warmup plus the decision bar. That is the correct
*minimum*, and every bounded feature — the returns, the two volatility estimators, both SMA
distances, the volume z-score, the money-flow multiplier — is exactly reproducible from 51 bars.

``rsi_14_centered`` is not bounded. Wilder RSI is an EMA with ``alpha = 1/14``, so the influence of
wherever the series happened to start decays as ``(13/14)^n`` and never reaches zero. Feeding 51 bars
instead of the full history moves the feature by up to **0.246 of its own standard deviation**;
feeding 400 moves it by ``1.71e-12``. The measured decay matches ``(13/14)^400 = 1.34e-13``, so the
convergence point is a property of the estimator rather than of any particular sample. The full
measurement is in ``agent_context/work/active/20260826-NOTICE-mizan-v3-reintroduces-window-dependence.md``.

So the window is *trailing up to 400 bars*. Below 400 that is the whole prefix — which is what the
store builder fed — so the kernel reproduces the published store identically there. Above 400 it is
bounded, and both sides consume the same 400 bars rather than agreeing by luck.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Final

from quant_system.data.market_data import PointInTimeBar
from quant_system.modeling.errors import ModelingError, ModelingFailureCode
from quant_system.modeling.pooled import MIZAN_WINDOW_BARS
from quant_system.modeling.rows import (
    FEATURE_NAMES_V3,
    FEATURE_SCHEMA_ID_V3,
    FEATURE_SCHEMA_VERSION_V3,
)

#: Fewest bars from which a v3 row can be computed at all: the 50-session SMA warmup plus the
#: decision bar. Imported rather than restated so it cannot drift from the dataset builder.
MIZAN_MINIMUM_BARS: Final = MIZAN_WINDOW_BARS

#: Most trailing bars the kernel consumes. Sized by the recursive member of the family, not the
#: longest explicit window — see the module docstring.
MIZAN_CANONICAL_WINDOW_BARS: Final = 400

#: How the store builder writes every feature value. Matching it is not cosmetic: the training
#: dataset consumed this text, so a kernel emitting more digits would feed the model values no
#: training row ever held.
_VALUE_FORMAT: Final = "{:.10f}"

#: Wilder's smoothing period.
_RSI_PERIOD: Final = 14


def wilder_rsi(closes: Sequence[float], period: int = _RSI_PERIOD) -> list[float]:
    """Wilder RSI over a supplied series. Index ``i`` depends on ``closes[: i + 1]`` and nothing later.

    Promoted verbatim from ``scripts/build_mizan_feature_store.py``. Note that "depends on everything
    before i" is the property that makes a canonical window necessary: it is causal but unbounded.
    """
    out = [50.0] * len(closes)
    if len(closes) <= period:
        return out
    gains = losses = 0.0
    for i in range(1, period + 1):
        change = closes[i] - closes[i - 1]
        gains += max(change, 0.0)
        losses += max(-change, 0.0)
    avg_gain, avg_loss = gains / period, losses / period
    for i in range(period, len(closes)):
        if i > period:
            change = closes[i] - closes[i - 1]
            avg_gain = (avg_gain * (period - 1) + max(change, 0.0)) / period
            avg_loss = (avg_loss * (period - 1) + max(-change, 0.0)) / period
        if avg_loss == 0.0:
            out[i] = 100.0 if avg_gain > 0.0 else 50.0
        else:
            out[i] = 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)
    return out


def canonical_mizan_window(
    records: Sequence[PointInTimeBar],
    decision_index: int | None = None,
) -> tuple[PointInTimeBar, ...]:
    """The trailing bars the kernel is allowed to consume for one decision bar.

    ``decision_index`` defaults to the last record. The returned window ends at the decision bar and
    holds at most :data:`MIZAN_CANONICAL_WINDOW_BARS`; when less history exists it is the full
    prefix, which is what the store builder fed and therefore what the published values encode.
    """
    index = len(records) - 1 if decision_index is None else decision_index
    if index < 0 or index >= len(records):
        raise ModelingError(
            ModelingFailureCode.INVALID_PARAMETER,
            f"decision index {index} is outside the supplied {len(records)} records",
        )
    if index + 1 < MIZAN_MINIMUM_BARS:
        raise ModelingError(
            ModelingFailureCode.TRAINING_INPUT_MISMATCH,
            f"the Mizan feature family needs at least {MIZAN_MINIMUM_BARS} bars up to the decision "
            f"bar, found {index + 1}",
        )
    start = max(0, index + 1 - MIZAN_CANONICAL_WINDOW_BARS)
    return tuple(records[start : index + 1])


def compute_mizan_feature_values(
    window: Sequence[PointInTimeBar],
    *,
    india_vix_by_date: Mapping[str, float],
    nifty_by_date: Mapping[str, float],
) -> dict[str, str] | None:
    """The thirteen instrument-level features for the last bar of ``window``.

    Returns ``None`` when the row is not computable — a non-positive price, or macro data missing for
    the decision date or its 5-session lag. The store builder skips such rows rather than
    substituting a value, and so does this.

    The two cross-sectional ranks are left at ``0.0``; they are not functions of one instrument's
    history and are filled by :func:`apply_cross_sectional_ranks` once the whole cross-section for
    the date is known.
    """
    if len(window) < MIZAN_MINIMUM_BARS:
        raise ModelingError(
            ModelingFailureCode.TRAINING_INPUT_MISMATCH,
            f"the Mizan feature family needs at least {MIZAN_MINIMUM_BARS} bars, "
            f"found {len(window)}",
        )
    if len(window) > MIZAN_CANONICAL_WINDOW_BARS:
        raise ModelingError(
            ModelingFailureCode.TRAINING_INPUT_MISMATCH,
            f"window of {len(window)} bars exceeds the canonical "
            f"{MIZAN_CANONICAL_WINDOW_BARS}; a longer window changes rsi_14_centered and would "
            "score values no training row held. Use canonical_mizan_window()",
        )
    _require_ascending(window)

    dates = [record.exchange_date.isoformat() for record in window]
    opens = [float(record.open) for record in window]
    highs = [float(record.high) for record in window]
    lows = [float(record.low) for record in window]
    closes = [float(record.close) for record in window]
    volumes = [float(record.volume) for record in window]
    rsi = wilder_rsi(closes)

    i = len(window) - 1
    close, open_, high, low = closes[i], opens[i], highs[i], lows[i]
    if close <= 0 or open_ <= 0 or high <= 0 or low <= 0:
        return None

    vix = india_vix_by_date.get(dates[i])
    vix_past = india_vix_by_date.get(dates[i - 5])
    nifty = nifty_by_date.get(dates[i])
    nifty_past = nifty_by_date.get(dates[i - 5])
    if vix is None or vix_past is None or nifty is None or nifty_past is None:
        return None

    log_hl = math.log(high / low)
    log_co = math.log(close / open_)
    sma_20 = sum(closes[i - 20 : i]) / 20.0
    sma_50 = sum(closes[i - 50 : i]) / 50.0
    volume_window = volumes[i - 20 : i]
    mean_volume = sum(volume_window) / 20.0
    std_volume = math.sqrt(sum((v - mean_volume) ** 2 for v in volume_window) / 20.0)
    hl_range = high - low

    values = [
        close / closes[i - 1] - 1.0 if closes[i - 1] > 0 else 0.0,
        close / closes[i - 5] - 1.0 if closes[i - 5] > 0 else 0.0,
        close / closes[i - 21] - 1.0 if closes[i - 21] > 0 else 0.0,
        math.sqrt(max(0.0, 0.5 * log_hl**2 - (2.0 * math.log(2.0) - 1.0) * log_co**2)),
        log_hl / math.sqrt(4.0 * math.log(2.0)),
        rsi[i] / 100.0 - 0.5,
        close / sma_20 - 1.0 if sma_20 > 0 else 0.0,
        close / sma_50 - 1.0 if sma_50 > 0 else 0.0,
        (volumes[i] - mean_volume) / max(1.0, std_volume),
        ((close - low) - (high - close)) / hl_range if hl_range > 1e-9 else 0.0,
        vix / 100.0,
        vix / vix_past - 1.0 if vix_past > 0 else 0.0,
        nifty / nifty_past - 1.0 if nifty_past > 0 else 0.0,
        0.0,  # cs_rank_momentum_5, filled once the cross-section is complete
        0.0,  # cs_rank_volume_surprise, likewise
    ]
    return {
        name: _VALUE_FORMAT.format(value)
        # strict: the family and the value list are built together above, so a length mismatch
        # would mean a feature was added in one place and not the other.
        for name, value in zip(FEATURE_NAMES_V3, values, strict=True)
    }


def apply_cross_sectional_ranks(cross_section: dict[str, dict[str, str]]) -> None:
    """Fill both rank features in place, ranking each name against that date's cross-section.

    Uses only contemporaneous information: every row shares one decision date. The rank is
    ``(position + 1) / count - 0.5``, so it depends on **how many names are present** — which is why
    an execution surface must serve the same cross-section the model was fitted over, and why
    ``execution.cross_sectional_strategy`` refuses a partial one by default.
    """
    if not cross_section:
        return
    for source, target in (
        ("return_5", "cs_rank_momentum_5"),
        ("volume_zscore", "cs_rank_volume_surprise"),
    ):
        symbols = sorted(cross_section)
        count = len(symbols)
        # Sort by the source value, matching the builder. `sorted` is stable, and the pre-sort by
        # symbol makes ties resolve identically on every run rather than by dict insertion order.
        order = sorted(symbols, key=lambda s: float(cross_section[s][source]))
        for rank, symbol in enumerate(order):
            cross_section[symbol][target] = _VALUE_FORMAT.format((rank + 1) / count - 0.5)


def compute_mizan_cross_section(
    bars_by_symbol: Mapping[str, Sequence[PointInTimeBar]],
    *,
    india_vix_by_date: Mapping[str, float],
    nifty_by_date: Mapping[str, float],
) -> dict[str, dict[str, str]]:
    """One decision date's complete feature cross-section, ranks included.

    This is the entry point an execution feature provider calls. Each symbol's sequence must end at
    the same decision date; a symbol whose row is not computable is omitted, and the caller decides
    whether the resulting coverage is acceptable — ``CrossSectionalModelStrategy`` refuses a shrunk
    cross-section rather than ranking the remainder, because a missing name moves every rank.
    """
    cross_section: dict[str, dict[str, str]] = {}
    for symbol in sorted(bars_by_symbol):
        window = canonical_mizan_window(list(bars_by_symbol[symbol]))
        values = compute_mizan_feature_values(
            window,
            india_vix_by_date=india_vix_by_date,
            nifty_by_date=nifty_by_date,
        )
        if values is not None:
            cross_section[symbol] = values
    apply_cross_sectional_ranks(cross_section)
    return cross_section


def mizan_schema_identity() -> tuple[str, int]:
    """The schema this kernel computes, for binding against a model's declared identity."""
    return (FEATURE_SCHEMA_ID_V3, FEATURE_SCHEMA_VERSION_V3)


def _require_ascending(window: Sequence[PointInTimeBar]) -> None:
    """Refuse reverse or repeated chronology.

    An exported v2 kernel accepted reverse chronology and had to be repaired at `88a7ac9`. The same
    mistake here would silently change every windowed feature, so it is checked rather than assumed.
    """
    # Deliberately not strict: `window[1:]` is one shorter, which is the point of the pairing.
    for earlier, later in zip(window, window[1:], strict=False):
        if later.exchange_date <= earlier.exchange_date:
            raise ModelingError(
                ModelingFailureCode.RECORD_ORDER_INVALID,
                f"Mizan window must be strictly ascending by exchange date; {later.exchange_date} "
                f"does not follow {earlier.exchange_date}",
            )
