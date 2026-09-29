"""Strategy rules for the lab templates.

A strategy sees a calendar-aligned :class:`Panel` (NaN where a symbol has no bar) and answers one
question at each session close: which symbols should be held from the next open, and with what
weight? It returns ``None`` when nothing needs to change. Indicators are computed on each symbol's
own sessions and indexed so that the value at ``t`` uses only closes up to ``t``.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass

import numpy as np

from quant_system.market import metrics
from quant_system.market.metrics import FloatArray

Targets = dict[str, float]


@dataclass(frozen=True, slots=True)
class Panel:
    """Prices on a shared calendar. ``close[s][t]`` is NaN when symbol ``s`` has no bar at ``t``."""

    dates: list[str]
    symbols: list[str]
    open: Mapping[str, FloatArray]
    close: Mapping[str, FloatArray]

    def has_bar(self, symbol: str, t: int) -> bool:
        return not math.isnan(self.close[symbol][t])


def scatter(values: FloatArray, valid: np.ndarray, length: int) -> FloatArray:
    """Place a per-symbol series (computed on its own sessions) back onto the calendar."""
    out = np.full(length, np.nan, dtype=np.float64)
    out[valid] = values
    return out


class LabStrategy(ABC):
    def __init__(self, first_trade: int) -> None:
        self.first_trade = first_trade

    @abstractmethod
    def prepare(self, panel: Panel) -> None: ...

    @abstractmethod
    def decide(self, t: int, held: frozenset[str]) -> Targets | None: ...


class BuyAndHold(LabStrategy):
    def prepare(self, panel: Panel) -> None:
        self.symbols = list(panel.symbols)

    def decide(self, t: int, held: frozenset[str]) -> Targets | None:
        if t != self.first_trade:
            return None
        weight = 1.0 / len(self.symbols)
        return dict.fromkeys(self.symbols, weight)


class _RuleStrategy(LabStrategy):
    """Per-symbol in/out rules; each symbol gets an equal share of equity when held."""

    def prepare(self, panel: Panel) -> None:
        self.symbols = list(panel.symbols)
        self.weight = 1.0 / len(self.symbols)
        self.want: dict[str, np.ndarray] = {}
        for symbol in self.symbols:
            close = panel.close[symbol]
            valid = ~np.isnan(close)
            want_valid = self._rule(close[valid])
            want = np.zeros(close.size, dtype=bool)
            # Carry the last decision across sessions where the symbol has no bar.
            positions = np.flatnonzero(valid)
            last = False
            cursor = 0
            for t in range(close.size):
                if cursor < positions.size and positions[cursor] == t:
                    last = bool(want_valid[cursor])
                    cursor += 1
                want[t] = last
            self.want[symbol] = want

    @abstractmethod
    def _rule(self, close: FloatArray) -> np.ndarray: ...

    def decide(self, t: int, held: frozenset[str]) -> Targets | None:
        wanted = {s for s in self.symbols if self.want[s][t]}
        if wanted == set(held):
            return None
        return dict.fromkeys(sorted(wanted), self.weight)


class TrendFollowing(_RuleStrategy):
    def __init__(self, first_trade: int, fast: int, slow: int) -> None:
        super().__init__(first_trade)
        self.fast, self.slow = fast, slow

    def _rule(self, close: FloatArray) -> np.ndarray:
        fast = metrics.rolling_mean(close, self.fast)
        slow = metrics.rolling_mean(close, self.slow)
        with np.errstate(invalid="ignore"):
            out: np.ndarray = np.nan_to_num(fast, nan=-np.inf) > np.nan_to_num(slow, nan=np.inf)
        return out


class Breakout(_RuleStrategy):
    def __init__(self, first_trade: int, entry_lookback: int, exit_lookback: int) -> None:
        super().__init__(first_trade)
        self.entry_lookback, self.exit_lookback = entry_lookback, exit_lookback

    def _rule(self, close: FloatArray) -> np.ndarray:
        # Highest/lowest close of the *previous* window, so today's close is compared with the past.
        prior_high = np.roll(metrics.rolling_max(close, self.entry_lookback), 1)
        prior_low = np.roll(metrics.rolling_min(close, self.exit_lookback), 1)
        prior_high[0] = np.nan
        prior_low[0] = np.nan
        out = np.zeros(close.size, dtype=bool)
        in_position = False
        for i in range(close.size):
            if not in_position and not math.isnan(prior_high[i]) and close[i] > prior_high[i]:
                in_position = True
            elif in_position and not math.isnan(prior_low[i]) and close[i] < prior_low[i]:
                in_position = False
            out[i] = in_position
        return out


class Pullback(_RuleStrategy):
    def __init__(
        self,
        first_trade: int,
        rsi_period: int,
        entry_below: int,
        exit_above: int,
        max_hold: int,
        trend_filter: bool,
    ) -> None:
        super().__init__(first_trade)
        self.rsi_period = rsi_period
        self.entry_below, self.exit_above = entry_below, exit_above
        self.max_hold, self.trend_filter = max_hold, trend_filter

    def _rule(self, close: FloatArray) -> np.ndarray:
        rsi = metrics.rsi(close, self.rsi_period)
        sma200 = metrics.rolling_mean(close, 200)
        out = np.zeros(close.size, dtype=bool)
        in_position = False
        held_for = 0
        for i in range(close.size):
            if in_position:
                held_for += 1
                if (
                    not math.isnan(rsi[i]) and rsi[i] > self.exit_above
                ) or held_for >= self.max_hold:
                    in_position = False
            elif not math.isnan(rsi[i]) and rsi[i] < self.entry_below:
                trend_ok = not self.trend_filter or (
                    not math.isnan(sma200[i]) and close[i] > sma200[i]
                )
                if trend_ok:
                    in_position, held_for = True, 0
            out[i] = in_position
        return out


class MomentumRotation(LabStrategy):
    def __init__(
        self,
        first_trade: int,
        lookback: int,
        skip: int,
        top_n: int,
        rebalance: int,
        trend_filter: bool,
    ) -> None:
        super().__init__(first_trade)
        self.lookback, self.skip, self.top_n = lookback, skip, top_n
        self.rebalance, self.trend_filter = rebalance, trend_filter

    def prepare(self, panel: Panel) -> None:
        self.panel = panel
        length = len(panel.dates)
        self.score: dict[str, FloatArray] = {}
        self.trend_ok: dict[str, np.ndarray] = {}
        for symbol in panel.symbols:
            close = panel.close[symbol]
            valid = ~np.isnan(close)
            own = close[valid]
            score_own = np.full(own.size, np.nan, dtype=np.float64)
            span = self.lookback + self.skip
            if own.size > span:
                recent = own[span - self.skip : own.size - self.skip] if self.skip else own[span:]
                past = own[: own.size - span]
                score_own[span:] = recent / past - 1.0
            self.score[symbol] = scatter(score_own, valid, length)
            sma200 = scatter(metrics.rolling_mean(own, 200), valid, length)
            with np.errstate(invalid="ignore"):
                self.trend_ok[symbol] = close > sma200

    def decide(self, t: int, held: frozenset[str]) -> Targets | None:
        if t < self.first_trade or (t - self.first_trade) % self.rebalance != 0:
            return None
        ranked: list[tuple[float, str]] = []
        for symbol in self.panel.symbols:
            value = self.score[symbol][t]
            if math.isnan(value):
                continue
            if self.trend_filter and not bool(self.trend_ok[symbol][t]):
                continue
            ranked.append((value, symbol))
        ranked.sort(key=lambda pair: (-pair[0], pair[1]))
        weight = 1.0 / self.top_n
        return {symbol: weight for _value, symbol in ranked[: self.top_n]}


def build_strategy(
    template_id: str, params: Mapping[str, int | bool], first_trade: int
) -> LabStrategy:
    def num(name: str) -> int:
        return int(params[name])

    if template_id == "buy_hold":
        return BuyAndHold(first_trade)
    if template_id == "trend":
        return TrendFollowing(first_trade, num("fast"), num("slow"))
    if template_id == "breakout":
        return Breakout(first_trade, num("entry_lookback"), num("exit_lookback"))
    if template_id == "pullback":
        return Pullback(
            first_trade,
            num("rsi_period"),
            num("entry_below"),
            num("exit_above"),
            num("max_hold"),
            bool(params["trend_filter"]),
        )
    if template_id == "momentum":
        return MomentumRotation(
            first_trade,
            num("lookback"),
            num("skip"),
            num("top_n"),
            num("rebalance"),
            bool(params["trend_filter"]),
        )
    raise ValueError(f"Unknown strategy template: {template_id}")


def warmup_sessions(template_id: str, params: Mapping[str, int | bool]) -> int:
    """Sessions of history needed before the first trade so indicators are fully formed."""
    if template_id == "trend":
        return int(params["slow"])
    if template_id == "breakout":
        return int(params["entry_lookback"]) + 1
    if template_id == "pullback":
        return 200 if params["trend_filter"] else int(params["rsi_period"]) + 1
    if template_id == "momentum":
        base = int(params["lookback"]) + int(params["skip"]) + 1
        return max(base, 200) if params["trend_filter"] else base
    return 0
