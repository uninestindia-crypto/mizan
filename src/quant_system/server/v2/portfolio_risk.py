"""How a person's holdings have moved together, from their daily price history.

A portfolio of five shares is not always five bets: two banks tend to rise and fall together. This works out, from the last
year of daily moves, the typical yearly swing of the whole portfolio, how many *independent* bets it behaves like, and each
holding's share of the risk next to its share of the money.

The covariance is Qlib's Ledoit-Wolf shrinkage estimator toward a constant-correlation target
(``quant_system.research.qlib.riskmodel``, copied from Microsoft Qlib under the MIT licence): the raw covariance of a dozen
shares over a year is noisy, and the noise makes a portfolio look more or less diversified than it is.

It describes the past. It is never a forecast, and the answer says so.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

import numpy as np

from quant_system.market.index import BarSeries, SymbolNotFoundError

SESSIONS_PER_YEAR = 252
WINDOW_SESSIONS = 252
MIN_SESSIONS = 60
LARGEST_RISKS = 3
NOTE = (
    "Based on how these holdings moved day to day over the sessions shown. It describes the past and is not a forecast: "
    "a calm year says little about a bad one."
)
NOT_ENOUGH_HISTORY = (
    "There is not enough price history to describe how these holdings move together. "
    "Open Settings, then Market data, to see how far back your data goes."
)
NO_HOLDINGS = "There are no holdings to look at yet."
NO_MOVEMENT = (
    "These holdings have hardly moved over this period, so there is no risk figure to show."
)
_VARIANCE_FLOOR = 1e-16


class BarSource(Protocol):
    def bars(self, symbol: str, start: str | None = None, end: str | None = None) -> BarSeries: ...


@dataclass(frozen=True, slots=True)
class RiskHolding:
    symbol: str
    value: float


def unavailable(message: str, left_out: list[dict[str, str]] | None = None) -> dict[str, Any]:
    return {
        "available": False,
        "message": message,
        "window": None,
        "volatility_pct": None,
        "effective_bets": None,
        "diversification": None,
        "shrinkage": None,
        "holdings": [],
        "left_out": left_out or [],
        "note": NOTE,
    }


def portfolio_risk(source: BarSource, holdings: Sequence[RiskHolding]) -> dict[str, Any]:
    """The risk picture for ``holdings`` (valued in rupees), from ``source``'s daily bars."""
    merged: dict[str, float] = {}
    for holding in holdings:
        symbol = holding.symbol.strip().upper()
        if symbol and math.isfinite(holding.value) and holding.value > 0:
            merged[symbol] = merged.get(symbol, 0.0) + holding.value
    if not merged:
        return unavailable(NO_HOLDINGS)

    left_out: list[dict[str, str]] = []
    prices: dict[str, dict[str, float]] = {}
    for symbol in sorted(merged):
        try:
            bars = source.bars(symbol)
        except (SymbolNotFoundError, LookupError):
            left_out.append({"symbol": symbol, "reason": "Not in your market data."})
            continue
        prices[symbol] = {d: float(c) for d, c in zip(bars.dates, bars.close, strict=True)}

    aligned = _align(prices, left_out)
    if aligned is None:
        return unavailable(NOT_ENOUGH_HISTORY, left_out)
    symbols, window_dates, closes = aligned

    returns = closes[1:] / closes[:-1] - 1.0
    keep, left_days = _without_data_breaks(source, symbols, window_dates)
    returns = returns[keep]
    if len(returns) < MIN_SESSIONS:
        return unavailable(NOT_ENOUGH_HISTORY, left_out)

    values = np.array([merged[s] for s in symbols])
    weights = values / values.sum()
    # Imported here, not at the top: the Qlib package pulls in scipy and pandas, which every server and worker start-up
    # would otherwise pay for, and only a risk question needs them.
    from quant_system.research.qlib.riskmodel import ShrinkCovEstimator

    model = ShrinkCovEstimator(alpha="lw", target="const_corr", scale_return=False)
    cov = np.asarray(model.predict(returns, is_price=False))
    return _describe(
        symbols, weights, cov, model.shrinkage_, window_dates, len(returns), left_days, left_out
    )


def risk_from_quantities(source: BarSource, quantities: Mapping[str, float]) -> dict[str, Any]:
    """The same, for shares held: each value is the latest close times the quantity."""
    valued: list[RiskHolding] = []
    left_out: list[dict[str, str]] = []
    for symbol, quantity in quantities.items():
        try:
            bars = source.bars(symbol)
        except (SymbolNotFoundError, LookupError):
            left_out.append({"symbol": symbol.upper(), "reason": "Not in your market data."})
            continue
        if len(bars.close):
            valued.append(RiskHolding(symbol, float(bars.close[-1]) * float(quantity)))
    out = portfolio_risk(source, valued)
    known = {item["symbol"] for item in out["left_out"]}
    out["left_out"] = out["left_out"] + [item for item in left_out if item["symbol"] not in known]
    return out


def risk_summary(risk: Mapping[str, Any]) -> dict[str, Any] | None:
    """A few lines of the picture for the assistant. None when there is no picture."""
    if not risk.get("available"):
        return None
    rows = risk["holdings"]
    return {
        "volatility_pct": risk["volatility_pct"],
        "effective_bets": risk["effective_bets"],
        "holdings_counted": len(rows),
        "sessions": risk["window"]["sessions"],
        "largest_risks": [
            {"symbol": r["symbol"], "money_pct": r["money_pct"], "risk_pct": r["risk_pct"]}
            for r in rows[:LARGEST_RISKS]
        ],
        "note": NOTE,
    }


def _align(
    prices: dict[str, dict[str, float]], left_out: list[dict[str, str]]
) -> tuple[list[str], list[str], np.ndarray] | None:
    """The shares and the last year of dates they all have, dropping the share with the shortest history until it fits.

    A share with a short history is left out rather than allowed to shorten every other share's window.
    """
    names = sorted(prices)
    while names:
        common = sorted(set.intersection(*(set(prices[n]) for n in names)))
        if len(common) - 1 >= MIN_SESSIONS:
            dates = common[-(WINDOW_SESSIONS + 1) :]
            closes = np.array([[prices[n][d] for n in names] for d in dates], dtype=np.float64)
            if np.isfinite(closes).all() and (closes > 0).all():
                return names, dates, closes
        if len(names) == 1:
            break
        shortest = min(names, key=lambda n: len(prices[n]))
        left_out.append(
            {
                "symbol": shortest,
                "reason": f"Only {len(prices[shortest])} sessions of price history, so it was left out.",
            }
        )
        names.remove(shortest)
    if names:
        left_out.append({"symbol": names[0], "reason": "Not enough price history."})
    return None


def _without_data_breaks(
    source: BarSource, symbols: list[str], dates: list[str]
) -> tuple[np.ndarray, int]:
    """Which of the window's daily returns to keep: those not on a day the market index flags as a data break."""
    keep = np.ones(len(dates) - 1, dtype=bool)
    flags = getattr(source, "flags_in_window", None)
    if flags is None:
        return keep, 0
    try:
        found = flags(symbols, dates[0], dates[-1])
    except Exception:
        return keep, 0
    flagged = {str(f["d"]) for rows in found.values() for f in rows}
    for i, day in enumerate(dates[1:]):
        if day in flagged:
            keep[i] = False
    return keep, int((~keep).sum())


def _describe(
    symbols: list[str],
    weights: np.ndarray,
    cov: np.ndarray,
    shrinkage: float | None,
    dates: list[str],
    sessions: int,
    days_left_out: int,
    left_out: list[dict[str, str]],
) -> dict[str, Any]:
    variance = float(weights @ cov @ weights)
    vols = np.sqrt(np.clip(np.diag(cov), 0.0, None))
    if variance < _VARIANCE_FLOOR:
        return unavailable(NO_MOVEMENT, left_out)
    marginal = cov @ weights
    risk_share = weights * marginal / variance
    # Holdings that move in opposite directions can score above their own number; "independent holdings" cannot exceed it.
    effective_bets = min(float((weights @ vols) ** 2 / variance), float(len(symbols)))
    average_link = _average_correlation(cov, vols)
    rows: list[dict[str, Any]] = [
        {
            "symbol": symbol,
            "money_pct": round(float(weights[i]) * 100, 1),
            "risk_pct": round(float(risk_share[i]) * 100, 1),
            "volatility_pct": round(float(vols[i]) * math.sqrt(SESSIONS_PER_YEAR) * 100, 1),
        }
        for i, symbol in enumerate(symbols)
    ]
    rows.sort(key=lambda row: -row["risk_pct"])
    return {
        "available": True,
        "message": None,
        "window": {
            "sessions": sessions,
            "from": dates[0],
            "to": dates[-1],
            "days_left_out": days_left_out,
        },
        "volatility_pct": round(math.sqrt(variance) * math.sqrt(SESSIONS_PER_YEAR) * 100, 2),
        "effective_bets": round(effective_bets, 2),
        "diversification": {"holdings": len(symbols), "average_correlation": average_link},
        "shrinkage": None if shrinkage is None else round(float(shrinkage), 3),
        "holdings": rows,
        "left_out": left_out,
        "note": NOTE,
    }


def _average_correlation(cov: np.ndarray, vols: np.ndarray) -> float | None:
    n = len(vols)
    if n < 2:
        return None
    denominator = np.outer(vols, vols)
    corr = np.divide(cov, denominator, out=np.zeros_like(cov), where=denominator > 0)
    return round(float((corr.sum() - np.trace(corr)) / (n * (n - 1))), 2)
