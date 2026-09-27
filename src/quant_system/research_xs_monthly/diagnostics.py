"""Factor Monotonicity and Long-Short Diagnostic Engine (R3).

Evaluates cross-sectional factor ranking quality:
1. Universe Decile Portfolios (Q1 through Q10):
   Partitions the ranked eligible universe into 10 disjoint deciles (~42 names each for 423 universe).
   Computes realized forward return per decile and top-bottom long-short spread (Q1 - Q10).
   Checks monotonicity condition (Q1 > Q10).
2. Cross-Sectional Information Coefficient (Spearman Rank IC):
   Measures rank correlation between factor composite scores and realized forward returns.
   Uses exact rank ordering with fractional/average ranks on ties.
3. IC Time-Series Aggregation & Significance:
   Computes mean IC, standard deviation of IC, and Student's t-statistic:
   t = mean_ic / (std_ic / sqrt(N)).
   Evaluates statistical significance hurdle (t > 2.0).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

import numpy as np
from scipy import stats  # type: ignore[import-untyped]

if TYPE_CHECKING:
    from quant_system.research_xs_monthly.ranking import RankedSymbol

__all__ = [
    "DecileDiagnosticEngine",
    "DecileResults",
    "ICSummary",
]


@dataclass(frozen=True)
class DecileResults:
    """Outcome of cross-sectional decile portfolio evaluation."""

    as_of_date: date
    decile_returns: dict[int, Decimal]  # Decile 1 (top) to 10 (bottom)
    top_bottom_spread: Decimal  # Q1 - Q10 spread return
    is_monotonic: bool  # True if Q1 > Q10
    decile_counts: dict[int, int] | None = None


@dataclass(frozen=True)
class ICSummary:
    """Summary statistics for time-series Information Coefficient (IC) distribution."""

    mean_ic: float
    std_ic: float
    t_statistic: float
    n_periods: int
    is_significant: bool  # True if t_statistic > 2.0


class DecileDiagnosticEngine:
    """Diagnostic engine for factor monotonicity, decile spreads, and Spearman rank IC."""

    def evaluate_deciles(
        self,
        ranked_symbols: Sequence[RankedSymbol],
        forward_returns: dict[str, Decimal],
        as_of_date: date | None = None,
    ) -> DecileResults:
        """Partition universe into 10 disjoint deciles and compute decile returns.

        Args:
            ranked_symbols: Sequence of RankedSymbol sorted descending by factor score.
            forward_returns: Mapping from symbol to realized forward return in Decimal.
            as_of_date: Evaluation date (defaults to date.today() if omitted).

        Returns:
            DecileResults with per-decile returns, top-bottom spread, and monotonicity status.

        Raises:
            ValueError: If fewer than 10 symbols are provided.
        """
        n = len(ranked_symbols)
        if n < 10:
            raise ValueError(f"INSUFFICIENT_UNIVERSE: {n} names cannot form 10 deciles")

        bucket_size = n / 10.0
        decile_rets: dict[int, Decimal] = {}
        decile_counts: dict[int, int] = {}

        for d in range(1, 11):
            start_idx = int(round((d - 1) * bucket_size))
            end_idx = int(round(d * bucket_size))
            group = ranked_symbols[start_idx:end_idx]

            rets = [forward_returns[s.symbol] for s in group if s.symbol in forward_returns]
            decile_counts[d] = len(rets)
            if rets:
                decile_rets[d] = sum(rets, Decimal("0.0")) / Decimal(len(rets))
            else:
                decile_rets[d] = Decimal("0.0")

        spread = decile_rets[1] - decile_rets[10]
        is_monotonic = decile_rets[1] > decile_rets[10]
        as_of = as_of_date if as_of_date is not None else date.today()

        return DecileResults(
            as_of_date=as_of,
            decile_returns=decile_rets,
            top_bottom_spread=spread,
            is_monotonic=is_monotonic,
            decile_counts=decile_counts,
        )

    def spearman_rank_ic(
        self,
        scores: Sequence[float],
        forward_returns: Sequence[float],
    ) -> float:
        """Compute cross-sectional Spearman rank correlation.

        Handles ties via fractional rank averaging. Returns 0.0 if inputs have
        fewer than 2 elements or zero variance.

        Args:
            scores: Factor scores across cross-section.
            forward_returns: Realized forward returns for the same instruments.

        Returns:
            Spearman rank correlation coefficient in [-1.0, 1.0].
        """
        if len(scores) < 2 or len(forward_returns) < 2 or len(scores) != len(forward_returns):
            return 0.0

        scores_arr = np.asarray(scores, dtype=float)
        rets_arr = np.asarray(forward_returns, dtype=float)

        # Check for zero variance / constant arrays
        if np.all(scores_arr == scores_arr[0]) or np.all(rets_arr == rets_arr[0]):
            return 0.0

        corr, _ = stats.spearmanr(scores_arr, rets_arr)
        if math.isnan(corr) or math.isinf(corr):
            return 0.0
        return float(corr)

    def aggregate_ic(
        self,
        ic_series: Sequence[float],
    ) -> tuple[float, float, float]:
        """Aggregate an IC time-series into mean, standard deviation, and Student's t-statistic.

        Formula:
            t = mean_ic / (std_ic / sqrt(N))

        Args:
            ic_series: Sequence of cross-sectional IC values across evaluation dates.

        Returns:
            Tuple of (mean_ic, std_ic, t_statistic). Returns (0.0, 0.0, 0.0) if empty.
        """
        if not ic_series:
            return (0.0, 0.0, 0.0)

        n = len(ic_series)
        mean_ic = float(np.mean(ic_series))
        if n < 2:
            return (mean_ic, 0.0, 0.0)

        std_ic = float(np.std(ic_series, ddof=1))
        if std_ic < 1e-12:
            return (mean_ic, std_ic, 0.0)

        t_stat = mean_ic / (std_ic / math.sqrt(n))
        return (mean_ic, std_ic, t_stat)

    def summarize_ic(
        self,
        ic_series: Sequence[float],
    ) -> ICSummary:
        """Generate complete statistical summary of IC time-series."""
        mean_ic, std_ic, t_stat = self.aggregate_ic(ic_series)
        return ICSummary(
            mean_ic=mean_ic,
            std_ic=std_ic,
            t_statistic=t_stat,
            n_periods=len(ic_series),
            is_significant=t_stat > 2.0,
        )

    def check_pairwise_monotonicity(
        self,
        decile_returns: dict[int, Decimal],
    ) -> bool:
        """Check whether decile returns are non-increasing from Q1 to Q10 (Q1 >= Q2 >= ... >= Q10)."""
        if len(decile_returns) < 10:
            return False
        vals = [decile_returns[d] for d in range(1, 11)]
        return all(vals[i] >= vals[i + 1] for i in range(len(vals) - 1))
