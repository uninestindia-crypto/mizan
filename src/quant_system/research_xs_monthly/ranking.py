"""Multi-factor cross-sectional ranking engine for monthly portfolio alpha (R1).

Point-in-time calculation at decision close T (zero look-ahead, only bars with
exchange_date <= T).

Factors:
1. Intermediate Momentum (21 to 63 sessions):
   Captures durable intermediate trend over 1 to 3 months.
2. Short-Term Mean-Reversion Dampening (3 to 5 sessions):
   Dampens retail overreaction and exhaustion spikes over 1 week.
3. Idiosyncratic Volatility Scaling (63 sessions):
   Residual volatility from rolling CAPM regression against equal-weighted
   market universe returns over 63 sessions, penalizing lottery tickets.
4. Composite Factor Scoring:
   Combines intermediate momentum, short reversion dampening, and idiosyncratic
   volatility scaling into an investable, cost-surviving composite ranking.
5. Deterministic Tie-Breaking:
   Ranks universe descending by composite score, with ties broken lexicographically
   by symbol name.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

import numpy as np

from quant_system.research_xs_monthly.bars import Bar

# Canonical point-in-time bar alias for interface compatibility
PointInTimeBar = Bar


class RankingEngineError(ValueError):
    """Base error for ranking engine failures."""


class InsufficientHistoryError(RankingEngineError):
    """Raised when historical bars are insufficient (< required window)."""


class PointInTimeError(RankingEngineError):
    """Raised when future bars (> as_of_date) are detected in strict PIT mode."""


def _is_finite_positive_decimal(val: Decimal) -> bool:
    """Check if Decimal is finite and strictly positive (> 0), handling NaN/Inf safely."""
    try:
        return not (val.is_nan() or val.is_infinite()) and val > Decimal(0)
    except Exception:
        return False


@dataclass(frozen=True, slots=True)
class FactorConfig:
    """Immutable configuration parameters for multi-factor ranking."""

    momentum_window: int = 63  # 63 sessions intermediate momentum window (approx 3 months)
    momentum_lag: int = 0  # Lag in sessions (0: up to T; 21: up to T-21 for 21..63 skip momentum)
    reversion_window: int = 5  # 5 sessions short-term mean-reversion dampening (approx 1 week)
    reversion_lag: int = 0  # Lag for short-term return
    volatility_window: int = 63  # 63 sessions idiosyncratic volatility estimation window
    dampening_lambda: float = 0.5  # Weight of short-term mean-reversion penalty
    volatility_weight: float = 0.5  # Weight of volatility penalty (for linear z-score)
    scoring_method: str = "ratio_zscore"  # "ratio_zscore", "ratio", "linear_zscore"
    winsorize_std: float = 3.0  # Clipping threshold for z-scores
    min_history_bars: int = (
        64  # Minimum historical bars required (at least 64 bars for 63 sessions)
    )
    filter_circuit_locked: bool = (
        True  # Exclude names with volume <= 0 or high <= low on decision date
    )
    reject_future_bars: bool = False  # If True, raise PointInTimeError on bars > as_of_date

    def __post_init__(self) -> None:
        if self.min_history_bars <= 30:
            eff_window = max(2, self.min_history_bars - 1)
            if self.momentum_window >= self.min_history_bars:
                object.__setattr__(self, "momentum_window", eff_window)
            if self.volatility_window >= self.min_history_bars:
                object.__setattr__(self, "volatility_window", eff_window)
            if self.reversion_window >= self.min_history_bars:
                object.__setattr__(self, "reversion_window", max(1, self.min_history_bars // 4))


@dataclass(frozen=True)
class FactorComponents:
    """Computed point-in-time factor components for an individual symbol."""

    intermediate_momentum_21_63: float
    short_reversion_3_5: float
    idiosyncratic_volatility_63: float
    composite_score: float
    market_beta: float = 1.0
    raw_momentum_63: float | None = None
    raw_momentum_21: float | None = None
    raw_reversion_5: float | None = None
    raw_reversion_3: float | None = None

    @property
    def intermediate_return(self) -> float:
        return self.intermediate_momentum_21_63

    @property
    def short_return(self) -> float:
        return self.short_reversion_3_5

    @property
    def idiosyncratic_vol(self) -> float:
        return self.idiosyncratic_volatility_63

    @property
    def score(self) -> float:
        return self.composite_score


@dataclass(frozen=True)
class RankedSymbol:
    """Ranked symbol entry in cross-sectional universe."""

    symbol: str
    rank: int
    score: float
    components: FactorComponents

    def __init__(
        self,
        symbol: str,
        rank: int,
        score: float,
        components: FactorComponents | None = None,
        factor_values: FactorComponents | None = None,
    ) -> None:
        comp = components if components is not None else factor_values
        if comp is None:
            raise ValueError("Either components or factor_values must be provided")
        object.__setattr__(self, "symbol", symbol)
        object.__setattr__(self, "rank", int(rank))
        object.__setattr__(self, "score", float(score))
        object.__setattr__(self, "components", comp)

    @property
    def factor_values(self) -> FactorComponents:
        return self.components


def compute_intermediate_momentum(
    bars: Sequence[Bar],
    as_of_date: date,
    window: int = 63,
    lag: int = 0,
) -> float | None:
    """Compute point-in-time intermediate-term momentum (e.g. 63-session return).

    Formula: (Close[T - lag] - Close[T - lag - window]) / Close[T - lag - window].
    Fails closed (returns None) if history is incomplete or prices are non-positive.
    """
    valid_bars = [b for b in bars if b.exchange_date <= as_of_date]
    valid_bars.sort(key=lambda b: b.exchange_date)
    if len(valid_bars) < window + lag + 1:
        return None
    if valid_bars[-1].exchange_date != as_of_date:
        return None

    idx_end = -1 - lag
    idx_start = -1 - lag - window

    try:
        c_end = float(valid_bars[idx_end].close)
        c_start = float(valid_bars[idx_start].close)
    except Exception:
        return None

    if not math.isfinite(c_start) or not math.isfinite(c_end) or c_start <= 0.0 or c_end <= 0.0:
        return None
    ret = (c_end - c_start) / c_start
    if not math.isfinite(ret):
        return None
    return ret


def compute_short_term_reversion(
    bars: Sequence[Bar],
    as_of_date: date,
    window: int = 5,
    lag: int = 0,
) -> float | None:
    """Compute point-in-time short-term mean-reversion return (e.g. 3-5 session return).

    Formula: (Close[T - lag] - Close[T - lag - window]) / Close[T - lag - window].
    Fails closed (returns None) if history is incomplete or prices are non-positive.
    """
    valid_bars = [b for b in bars if b.exchange_date <= as_of_date]
    valid_bars.sort(key=lambda b: b.exchange_date)
    if len(valid_bars) < window + lag + 1:
        return None
    if valid_bars[-1].exchange_date != as_of_date:
        return None

    idx_end = -1 - lag
    idx_start = -1 - lag - window

    try:
        c_end = float(valid_bars[idx_end].close)
        c_start = float(valid_bars[idx_start].close)
    except Exception:
        return None

    if not math.isfinite(c_start) or not math.isfinite(c_end) or c_start <= 0.0 or c_end <= 0.0:
        return None
    ret = (c_end - c_start) / c_start
    if not math.isfinite(ret):
        return None
    return ret


def compute_idiosyncratic_volatility(
    bars: Sequence[Bar],
    as_of_date: date,
    market_returns: Sequence[float] | None = None,
    window: int = 63,
) -> tuple[float, float] | None:
    """Compute 63-session idiosyncratic volatility via CAPM OLS regression.

    Returns (idiosyncratic_volatility, market_beta) or None if insufficient history.
    If market_returns is omitted or degenerate, falls back to realized total volatility
    with beta = 1.0.
    """
    valid_bars = [b for b in bars if b.exchange_date <= as_of_date]
    valid_bars.sort(key=lambda b: b.exchange_date)
    if not valid_bars or valid_bars[-1].exchange_date != as_of_date:
        return None

    if market_returns is not None:
        needed_bars = len(market_returns) + 1
        if len(valid_bars) < needed_bars:
            return None
        tail_bars = valid_bars[-needed_bars:]
    else:
        needed_bars = window + 1
        if len(valid_bars) < needed_bars:
            return None
        tail_bars = valid_bars[-needed_bars:]

    try:
        closes = [float(b.close) for b in tail_bars]
    except Exception:
        return None

    if any(not math.isfinite(c) or c <= 0.0 for c in closes):
        return None

    returns = [(closes[t] - closes[t - 1]) / closes[t - 1] for t in range(1, len(closes))]
    if len(returns) < 2 or any(not math.isfinite(r) for r in returns):
        return None

    # Standalone fallback: total volatility
    if (
        market_returns is None
        or len(market_returns) != len(returns)
        or any(not math.isfinite(mr) for mr in market_returns)
    ):
        tot_vol = float(np.std(returns, ddof=1))
        tot_vol = max(tot_vol, 1e-6)
        return (tot_vol, 1.0)

    # CAPM regression against market return
    r_i = np.array(returns, dtype=float)
    r_m = np.array(market_returns, dtype=float)
    var_m = float(np.var(r_m, ddof=1))

    if not math.isfinite(var_m) or var_m < 1e-12:
        tot_vol = max(float(np.std(r_i, ddof=1)), 1e-6)
        return (tot_vol, 1.0)

    cov_mat = np.cov(r_i, r_m, ddof=1)
    cov_im = float(cov_mat[0, 1])
    if not math.isfinite(cov_im):
        tot_vol = max(float(np.std(r_i, ddof=1)), 1e-6)
        return (tot_vol, 1.0)

    beta = cov_im / var_m
    if not math.isfinite(beta):
        tot_vol = max(float(np.std(r_i, ddof=1)), 1e-6)
        return (tot_vol, 1.0)

    residuals = (r_i - float(np.mean(r_i))) - beta * (r_m - float(np.mean(r_m)))
    res_var = float(np.var(residuals, ddof=1))
    if not math.isfinite(res_var) or res_var < 0.0:
        res_var = 1e-8
    res_vol = math.sqrt(max(1e-8, res_var))
    res_vol = max(res_vol, 1e-6)
    return (res_vol, beta)


class MultiFactorRankingEngine:
    """Point-in-time multi-factor ranking engine for cross-sectional portfolio alpha."""

    def __init__(self, config: FactorConfig | None = None) -> None:
        self.config = config or FactorConfig()

    def compute_factor_components(
        self,
        symbol: str,
        as_of_date: date,
        bars: Sequence[Bar],
        market_returns: Sequence[float] | None = None,
    ) -> FactorComponents | None:
        """Compute point-in-time factor components for a single symbol at decision close T.

        Fails closed (returns None) if bars are missing, insufficient, non-positive,
        or circuit-locked at T.
        """
        if self.config.reject_future_bars:
            for b in bars:
                if b.exchange_date > as_of_date:
                    raise PointInTimeError(
                        f"Future bar detected for {symbol} on {b.exchange_date} > {as_of_date}"
                    )

        valid_bars = [b for b in bars if b.exchange_date <= as_of_date]
        valid_bars.sort(key=lambda b: b.exchange_date)

        if len(valid_bars) < self.config.min_history_bars:
            return None

        last_bar = valid_bars[-1]
        if last_bar.exchange_date != as_of_date:
            return None

        if not (
            _is_finite_positive_decimal(last_bar.open)
            and _is_finite_positive_decimal(last_bar.high)
            and _is_finite_positive_decimal(last_bar.low)
            and _is_finite_positive_decimal(last_bar.close)
        ):
            return None

        if last_bar.high < last_bar.low:
            return None

        if self.config.filter_circuit_locked and (
            last_bar.volume <= 0 or last_bar.high <= last_bar.low
        ):
            return None

        mom_val = compute_intermediate_momentum(
            valid_bars,
            as_of_date,
            window=self.config.momentum_window,
            lag=self.config.momentum_lag,
        )
        if mom_val is None or not math.isfinite(mom_val):
            return None

        rev_val = compute_short_term_reversion(
            valid_bars,
            as_of_date,
            window=self.config.reversion_window,
            lag=self.config.reversion_lag,
        )
        if rev_val is None or not math.isfinite(rev_val):
            return None

        vol_res = compute_idiosyncratic_volatility(
            valid_bars,
            as_of_date,
            market_returns=market_returns,
            window=self.config.volatility_window,
        )
        if vol_res is None:
            return None
        idio_vol, beta = vol_res
        if not math.isfinite(idio_vol) or idio_vol <= 0.0 or not math.isfinite(beta):
            return None

        # Auxiliary raw components
        raw_63 = compute_intermediate_momentum(valid_bars, as_of_date, window=63, lag=0)
        raw_21 = compute_intermediate_momentum(valid_bars, as_of_date, window=21, lag=0)
        raw_5 = compute_short_term_reversion(valid_bars, as_of_date, window=5, lag=0)
        raw_3 = compute_short_term_reversion(valid_bars, as_of_date, window=3, lag=0)

        # Standalone composite score (ratio form)
        composite = (mom_val - self.config.dampening_lambda * rev_val) / idio_vol
        if not math.isfinite(composite):
            return None

        return FactorComponents(
            intermediate_momentum_21_63=float(mom_val),
            short_reversion_3_5=float(rev_val),
            idiosyncratic_volatility_63=float(idio_vol),
            composite_score=float(composite),
            market_beta=float(beta),
            raw_momentum_63=float(raw_63) if raw_63 is not None and math.isfinite(raw_63) else None,
            raw_momentum_21=float(raw_21) if raw_21 is not None and math.isfinite(raw_21) else None,
            raw_reversion_5=float(raw_5) if raw_5 is not None and math.isfinite(raw_5) else None,
            raw_reversion_3=float(raw_3) if raw_3 is not None and math.isfinite(raw_3) else None,
        )

    def rank_universe(
        self,
        as_of_date: date,
        eligible_symbols: list[str],
        bars_by_symbol: Mapping[str, Sequence[Bar]],
    ) -> list[RankedSymbol]:
        """Compute point-in-time rankings across universe descending by composite score.

        Ties are broken deterministically by symbol name (lexicographic ascending).
        Zero look-ahead: only bars with exchange_date <= as_of_date are considered.
        """
        if self.config.reject_future_bars:
            for sym in eligible_symbols:
                for b in bars_by_symbol.get(sym, []):
                    if b.exchange_date > as_of_date:
                        raise PointInTimeError(
                            f"Future bar detected for {sym} on {b.exchange_date} > {as_of_date}"
                        )

        # 1. Filter symbols with sufficient history and valid as_of_date bar
        valid_bars_by_sym: dict[str, list[Bar]] = {}
        for sym in sorted(set(eligible_symbols)):
            bars = bars_by_symbol.get(sym, [])
            vbars = [b for b in bars if b.exchange_date <= as_of_date]
            vbars.sort(key=lambda b: b.exchange_date)
            if len(vbars) < self.config.min_history_bars:
                continue
            last_bar = vbars[-1]
            if last_bar.exchange_date != as_of_date:
                continue
            if not (
                _is_finite_positive_decimal(last_bar.open)
                and _is_finite_positive_decimal(last_bar.high)
                and _is_finite_positive_decimal(last_bar.low)
                and _is_finite_positive_decimal(last_bar.close)
            ):
                continue
            if last_bar.high < last_bar.low:
                continue
            if self.config.filter_circuit_locked and (
                last_bar.volume <= 0 or last_bar.high <= last_bar.low
            ):
                continue
            valid_bars_by_sym[sym] = vbars

        if not valid_bars_by_sym:
            return []

        # 2. Compute equal-weighted universe market return series for CAPM residual volatility
        w_vol = self.config.volatility_window
        min_bars = min(len(vb) for vb in valid_bars_by_sym.values())
        w_effective = min(w_vol, min_bars - 1)

        market_returns: list[float] | None = None
        if w_effective >= 2 and len(valid_bars_by_sym) >= 2:
            sym_returns: list[list[float]] = []
            for vbars in valid_bars_by_sym.values():
                tail = vbars[-(w_effective + 1) :]
                try:
                    closes = [float(b.close) for b in tail]
                except Exception:
                    continue
                if any(not math.isfinite(c) or c <= 0.0 for c in closes):
                    continue
                rets = [(closes[t] - closes[t - 1]) / closes[t - 1] for t in range(1, len(closes))]
                if len(rets) == w_effective and all(math.isfinite(r) for r in rets):
                    sym_returns.append(rets)
            if sym_returns:
                m_rets = [
                    float(np.mean([sym_returns[s][t] for s in range(len(sym_returns))]))
                    for t in range(w_effective)
                ]
                if all(math.isfinite(mr) for mr in m_rets):
                    market_returns = m_rets

        # 3. Compute factor components for each eligible symbol
        preliminary: dict[str, FactorComponents] = {}
        for sym, vbars in valid_bars_by_sym.items():
            comp = self.compute_factor_components(
                sym, as_of_date, vbars, market_returns=market_returns
            )
            if (
                comp is not None
                and math.isfinite(comp.intermediate_momentum_21_63)
                and math.isfinite(comp.short_reversion_3_5)
                and math.isfinite(comp.idiosyncratic_volatility_63)
                and comp.idiosyncratic_volatility_63 > 0.0
                and math.isfinite(comp.composite_score)
            ):
                preliminary[sym] = comp

        if not preliminary:
            return []

        # 4. Cross-sectional composite factor scoring
        final_components: dict[str, FactorComponents] = {}
        method = self.config.scoring_method

        if method == "ratio" or len(preliminary) < 2:
            final_components = preliminary
        elif method in ("ratio_zscore", "linear_zscore"):
            moms = [comp.intermediate_momentum_21_63 for comp in preliminary.values()]
            revs = [comp.short_reversion_3_5 for comp in preliminary.values()]
            vols = [comp.idiosyncratic_volatility_63 for comp in preliminary.values()]

            mean_m = float(np.mean(moms))
            std_m = float(np.std(moms))
            mean_r = float(np.mean(revs))
            std_r = float(np.std(revs))
            mean_v = float(np.mean(vols))
            std_v = float(np.std(vols))

            for sym, comp in preliminary.items():
                z_m = (comp.intermediate_momentum_21_63 - mean_m) / std_m if std_m > 1e-8 else 0.0
                z_r = (comp.short_reversion_3_5 - mean_r) / std_r if std_r > 1e-8 else 0.0
                z_m = float(np.clip(z_m, -self.config.winsorize_std, self.config.winsorize_std))
                z_r = float(np.clip(z_r, -self.config.winsorize_std, self.config.winsorize_std))

                if method == "ratio_zscore":
                    score = (
                        z_m - self.config.dampening_lambda * z_r
                    ) / comp.idiosyncratic_volatility_63
                else:  # linear_zscore
                    z_v = (
                        (comp.idiosyncratic_volatility_63 - mean_v) / std_v if std_v > 1e-8 else 0.0
                    )
                    z_v = float(np.clip(z_v, -self.config.winsorize_std, self.config.winsorize_std))
                    score = (
                        z_m
                        - self.config.dampening_lambda * z_r
                        - self.config.volatility_weight * z_v
                    )

                if not math.isfinite(score):
                    continue

                final_components[sym] = FactorComponents(
                    intermediate_momentum_21_63=comp.intermediate_momentum_21_63,
                    short_reversion_3_5=comp.short_reversion_3_5,
                    idiosyncratic_volatility_63=comp.idiosyncratic_volatility_63,
                    composite_score=float(score),
                    market_beta=comp.market_beta,
                    raw_momentum_63=comp.raw_momentum_63,
                    raw_momentum_21=comp.raw_momentum_21,
                    raw_reversion_5=comp.raw_reversion_5,
                    raw_reversion_3=comp.raw_reversion_3,
                )
        else:
            final_components = preliminary

        # 5. Sort descending by composite score, with ties broken lexicographically by symbol
        candidates = [
            (sym, comp.composite_score, comp)
            for sym, comp in final_components.items()
            if math.isfinite(comp.composite_score)
        ]
        candidates.sort(key=lambda item: (-item[1], item[0]))

        # 6. Assign 1-indexed ranks
        return [
            RankedSymbol(symbol=sym, rank=idx + 1, score=score, components=comp)
            for idx, (sym, score, comp) in enumerate(candidates)
        ]
