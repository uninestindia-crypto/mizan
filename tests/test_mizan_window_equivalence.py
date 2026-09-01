"""Training's expanding prefix and execution's bounded window must agree. (Mizan v3 notice)

`agent_context/work/active/20260826-NOTICE-mizan-v3-reintroduces-window-dependence.md` raises a P1:
`scripts/build_mizan_feature_store.py` computes `wilder_rsi` over an instrument's **entire** close
series, while `execution/mizan_live_features.py:141` truncates to the trailing
`MIZAN_CANONICAL_WINDOW_BARS`. Wilder RSI seeds at the start of the sequence supplied, so the two
sides compute a different `rsi_14_centered` for the same decision bar -- which is exactly the defect
schema v2 was adopted to remove.

The mechanism is real. **The divergence at the canonical window is not**, and these tests are what
makes that a tested property rather than a numerical accident:

- history <= the canonical window: both sides use the identical prefix, so they agree exactly;
- history > it: they differ by less than the store's published quantisation.

The second holds because Wilder's smoothing decays the seed geometrically -- after 400 bars the
initial value carries weight (13/14)**386, about 1e-12. If anyone shortens the canonical window,
these fail rather than silently changing what the published coefficients were fitted to.
"""

from __future__ import annotations

import random

import pytest

from quant_system.modeling.mizan_features import MIZAN_CANONICAL_WINDOW_BARS, wilder_rsi

#: The store publishes feature values to 10 decimals.
PUBLISHED_QUANTISATION = 1e-10


def _price_path(n: int, seed: int) -> list[float]:
    rng = random.Random(seed)
    closes = [1000.0]
    for _ in range(n - 1):
        closes.append(max(1.0, closes[-1] * (1 + rng.gauss(0, 0.013))))
    return closes


@pytest.mark.parametrize("seed", [7, 11, 13, 17, 19])
def test_the_canonical_window_agrees_with_a_full_ten_year_prefix(seed: int) -> None:
    """2,460 bars is the ten-year series the store builder actually feeds."""
    closes = _price_path(2460, seed)
    full = wilder_rsi(closes)

    worst = 0.0
    for index in range(MIZAN_CANONICAL_WINDOW_BARS, len(closes), 7):
        start = index + 1 - MIZAN_CANONICAL_WINDOW_BARS
        windowed = wilder_rsi(closes[start : index + 1])[-1]
        worst = max(worst, abs(windowed - full[index]))

    assert worst < PUBLISHED_QUANTISATION, (
        f"the canonical window diverges from the training prefix by {worst:.3e}, at or above the "
        f"{PUBLISHED_QUANTISATION:.0e} the store publishes. Training and execution would then "
        "score different values for the same decision bar."
    )


def test_a_history_shorter_than_the_window_is_bit_identical() -> None:
    """Both sides take the whole prefix, so there is nothing to diverge."""
    closes = _price_path(MIZAN_CANONICAL_WINDOW_BARS - 50, 23)

    assert wilder_rsi(closes)[-1] == wilder_rsi(closes[-MIZAN_CANONICAL_WINDOW_BARS:])[-1]


def test_a_history_exactly_the_window_is_bit_identical() -> None:
    closes = _price_path(MIZAN_CANONICAL_WINDOW_BARS, 29)

    assert wilder_rsi(closes)[-1] == wilder_rsi(closes[-MIZAN_CANONICAL_WINDOW_BARS:])[-1]


@pytest.mark.parametrize(
    ("window", "detectable"),
    [(51, True), (100, True), (200, True), (MIZAN_CANONICAL_WINDOW_BARS, False)],
)
def test_the_measurement_can_detect_a_divergence_it_does_not_find_at_400(
    window: int, detectable: bool
) -> None:
    """A test that cannot fail proves nothing.

    At 51 bars the divergence is whole RSI points; at 100 it is ~0.07; at 200 ~5e-05. The same
    procedure finds nothing at 400, so the negative result at 400 is evidence rather than a
    limitation of the method.
    """
    closes = _price_path(2460, 31)
    full = wilder_rsi(closes)

    worst = 0.0
    for index in range(window, len(closes), 7):
        worst = max(
            worst, abs(wilder_rsi(closes[index + 1 - window : index + 1])[-1] - full[index])
        )

    assert (worst >= PUBLISHED_QUANTISATION) is detectable, (
        f"window {window} gave divergence {worst:.3e}"
    )
