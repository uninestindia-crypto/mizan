"""Cross-sectional monthly top-fraction screen — pre-declared, research only.

VALIDATED rule (the only one that may be read as a finding):
  score = trailing FORMATION-session close-to-close gross return ending at the
  decision close (point-in-time: closes at or before T only) → rank descending
  → equal-weight long the top TOP_FRAC → hold HOLD sessions → next-open entry
  at T+1, exit at open T+HOLD → net of COST_RATIO per name per round trip.

Diagnostics (context, never findings): hold-2 long-only, hold-2 long-short,
hold-21 long-short.

Accounting: Decimal throughout; no imputation; locked days (volume 0 or
high == low on entry/exit) skipped; empty structures fail closed with typed
errors. Verdict is always RESEARCH_ONLY — a screen cannot promote.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, localcontext
from math import sqrt
from typing import Final

from quant_system.research_xs_monthly.bars import Bar

FORMATION_SESSIONS: Final = 21
HOLD_SESSIONS: Final = 21
TOP_FRAC: Final = Decimal("0.20")
COST_RATIO: Final = Decimal("0.00224")  # 0.224% NSE statutory round trip
WARMUP_SESSIONS: Final = 42
MIN_COVERAGE_FRAC: Final = Decimal("0.70")
DIAG_HOLD_SHORT: Final = 2


class ScreenError(ValueError):
    """Fail-closed screen error with a machine-readable code prefix."""


@dataclass(frozen=True)
class PeriodResult:
    decision_date: date
    entry_date: date
    exit_date: date
    held: tuple[str, ...]
    per_name_net: tuple[str, ...]  # Decimal text aligned with held
    period_net: str  # Decimal text
    skipped_locked: int


@dataclass(frozen=True)
class LegSummary:
    n_periods: int
    mean_net: str
    stdev_net: str
    t_stat: str | None
    sharpe_per_period: str | None
    sharpe_annualized: str | None
    degenerate: bool
    skipped_locked: int
    empty_periods: int


def _mean(values: list[Decimal]) -> Decimal:
    with localcontext() as ctx:
        ctx.prec = 28
        return sum(values, start=Decimal(0)) / Decimal(len(values))


def _sample_stdev(values: list[Decimal], mean: Decimal) -> Decimal:
    if len(values) < 2:
        return Decimal(0)
    with localcontext() as ctx:
        ctx.prec = 28
        var = sum(((v - mean) ** 2 for v in values), start=Decimal(0)) / Decimal(len(values) - 1)
        return var.sqrt() if var > 0 else Decimal(0)


def summarize_leg(period_nets: list[Decimal], skipped_locked: int, empty: int) -> LegSummary:
    if not period_nets:
        raise ScreenError("INSUFFICIENT_DATA: no valid holding periods")
    mean = _mean(period_nets)
    sd = _sample_stdev(period_nets, mean)
    degenerate = sd == 0
    t_stat: str | None = None
    sharpe: str | None = None
    sharpe_ann: str | None = None
    if not degenerate and len(period_nets) >= 3:
        with localcontext() as ctx:
            ctx.prec = 28
            t_stat = str(mean / (sd / Decimal(len(period_nets)).sqrt()))
            sharpe = str(mean / sd)
            sharpe_ann = str((mean / sd) * Decimal(sqrt(12)))
    return LegSummary(
        n_periods=len(period_nets),
        mean_net=str(mean),
        stdev_net=str(sd),
        t_stat=t_stat,
        sharpe_per_period=sharpe,
        sharpe_annualized=sharpe_ann,
        degenerate=degenerate,
        skipped_locked=skipped_locked,
        empty_periods=empty,
    )


def build_calendar(bars_by_symbol: dict[str, list[Bar]]) -> list[date]:
    """Common session calendar: dates where coverage >= MIN_COVERAGE_FRAC of names."""
    if not bars_by_symbol:
        raise ScreenError("INSUFFICIENT_DATA: empty universe")
    counts: dict[date, int] = {}
    for bars in bars_by_symbol.values():
        for bar in bars:
            counts[bar.exchange_date] = counts.get(bar.exchange_date, 0) + 1
    need = max(2, int(Decimal(len(bars_by_symbol)) * MIN_COVERAGE_FRAC))
    calendar = sorted(d for d, c in counts.items() if c >= need)
    if len(calendar) < WARMUP_SESSIONS + HOLD_SESSIONS + 1:
        raise ScreenError(
            f"INSUFFICIENT_DATA: calendar has {len(calendar)} sessions, "
            f"need >= {WARMUP_SESSIONS + HOLD_SESSIONS + 1}"
        )
    return calendar


def _index_symbol(bars: list[Bar]) -> dict[date, Bar]:
    return {bar.exchange_date: bar for bar in bars}


def formation_score(
    indexed: dict[date, Bar], calendar: list[date], decision_pos: int
) -> Decimal | None:
    """Trailing FORMATION-session gross return ending at the decision close.

    Requires the symbol to have bars on ALL FORMATION calendar sessions ending
    at decision_pos (strict, no imputation) and a positive base close.
    """
    if decision_pos < FORMATION_SESSIONS - 1:
        return None
    first = indexed.get(calendar[decision_pos - FORMATION_SESSIONS + 1])
    last = indexed.get(calendar[decision_pos])
    if first is None or last is None:
        return None
    for k in range(decision_pos - FORMATION_SESSIONS + 1, decision_pos + 1):
        if calendar[k] not in indexed:
            return None
    if first.close <= 0:
        return None
    with localcontext() as ctx:
        ctx.prec = 28
        return (last.close - first.close) / first.close


def _is_locked(bar: Bar) -> bool:
    return bar.volume == 0 or bar.high == bar.low


def forward_net(
    indexed: dict[date, Bar],
    calendar: list[date],
    entry_pos: int,
    exit_pos: int,
) -> tuple[Decimal | None, bool]:
    """Next-bar forward net return. Returns (net, skipped_locked)."""
    entry = indexed.get(calendar[entry_pos])
    exit_bar = indexed.get(calendar[exit_pos])
    if entry is None or exit_bar is None or entry.open <= 0:
        return None, False
    if _is_locked(entry) or _is_locked(exit_bar):
        return None, True
    with localcontext() as ctx:
        ctx.prec = 28
        gross = (exit_bar.open - entry.open) / entry.open
        return gross - COST_RATIO, False


def _pearson_on_floats(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 3:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True))
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx <= 0 or syy <= 0:
        return None
    return sxy / sqrt(sxx * syy)


def _ranks(values: list[Decimal], descending: bool = True) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: values[i], reverse=descending)
    ranks = [0.0] * len(values)
    for rank, idx in enumerate(order, start=1):
        ranks[idx] = float(rank)
    return ranks


def run_screen(
    bars_by_symbol: dict[str, list[Bar]],
    hold: int = HOLD_SESSIONS,
    top_frac: Decimal = TOP_FRAC,
) -> dict:
    """Run one long top-fraction leg plus IC accounting over all rebalances."""
    if hold < 1:
        raise ScreenError("BAD_PARAM: hold must be >= 1")
    if not bars_by_symbol:
        raise ScreenError("INSUFFICIENT_DATA: empty universe")
    calendar = build_calendar(bars_by_symbol)
    indexed = {symbol: _index_symbol(bars) for symbol, bars in bars_by_symbol.items()}

    decision_positions = [
        d
        for d in range(WARMUP_SESSIONS - 1, len(calendar) - hold)
        if (d - (WARMUP_SESSIONS - 1)) % hold == 0 and d + hold < len(calendar)
    ]
    if not decision_positions:
        raise ScreenError("INSUFFICIENT_DATA: no rebalance slots for this hold")

    periods: list[PeriodResult] = []
    period_nets: list[Decimal] = []
    market_nets: list[Decimal] = []
    ic_values: list[float] = []
    skipped_locked = 0
    empty_periods = 0
    scored_names_total = 0

    for d in decision_positions:
        scored: list[tuple[str, Decimal]] = []
        for symbol, idx in indexed.items():
            score = formation_score(idx, calendar, d)
            if score is not None:
                scored.append((symbol, score))
        if not scored:
            empty_periods += 1
            continue
        scored_names_total += len(scored)
        scored.sort(key=lambda item: item[1], reverse=True)
        width = max(1, int(Decimal(len(scored)) * top_frac))
        selected = [symbol for symbol, _ in scored[:width]]

        entry_pos, exit_pos = d + 1, d + hold
        held: list[str] = []
        nets: list[Decimal] = []
        net_texts: list[str] = []
        for symbol in selected:
            net, locked = forward_net(indexed[symbol], calendar, entry_pos, exit_pos)
            if locked:
                skipped_locked += 1
                continue
            if net is None:
                continue
            held.append(symbol)
            nets.append(net)
            net_texts.append(str(net))
        # IC over ALL scored names with valid forwards (selection-independent).
        fwd_all: list[tuple[Decimal, Decimal]] = []
        for symbol, score in scored:
            net, _ = forward_net(indexed[symbol], calendar, entry_pos, exit_pos)
            if net is not None:
                fwd_all.append((score, net))
        if len(fwd_all) >= 3:
            ic = _pearson_on_floats(
                _ranks([s for s, _ in fwd_all]),
                _ranks([f for _, f in fwd_all]),
            )
            if ic is not None:
                ic_values.append(ic)
            market_nets.append(_mean([f for _, f in fwd_all]))
        if not nets:
            empty_periods += 1
            continue
        period_net = _mean(nets)
        period_nets.append(period_net)
        periods.append(
            PeriodResult(
                decision_date=calendar[d],
                entry_date=calendar[entry_pos],
                exit_date=calendar[exit_pos],
                held=tuple(held),
                per_name_net=tuple(net_texts),
                period_net=str(period_net),
                skipped_locked=skipped_locked,
            )
        )

    leg = summarize_leg(period_nets, skipped_locked, empty_periods)
    market_leg = summarize_leg(market_nets, 0, 0) if market_nets else None
    ic_mean: float | None = None
    ic_t: float | None = None
    if len(ic_values) >= 3:
        mean_ic = sum(ic_values) / len(ic_values)
        var = sum((v - mean_ic) ** 2 for v in ic_values) / (len(ic_values) - 1)
        sd = sqrt(var) if var > 0 else 0.0
        ic_mean = mean_ic
        ic_t = mean_ic / (sd / sqrt(len(ic_values))) if sd > 0 else None
    return {
        "rule": "longTopFrac",
        "formation_sessions": FORMATION_SESSIONS,
        "hold_sessions": hold,
        "top_frac": str(top_frac),
        "cost_ratio": str(COST_RATIO),
        "calendar_sessions": len(calendar),
        "calendar_start": calendar[0].isoformat(),
        "calendar_end": calendar[-1].isoformat(),
        "universe_names": len(bars_by_symbol),
        "rebalances": len(periods),
        "scored_name_decisions": scored_names_total,
        "leg": {
            "n_periods": leg.n_periods,
            "mean_net": leg.mean_net,
            "stdev_net": leg.stdev_net,
            "t_stat": leg.t_stat,
            "sharpe_per_period": leg.sharpe_per_period,
            "sharpe_annualized": leg.sharpe_annualized,
            "degenerate": leg.degenerate,
            "skipped_locked": leg.skipped_locked,
            "empty_periods": leg.empty_periods,
        },
        "ic_n": len(ic_values),
        "ic_mean": ic_mean,
        "ic_t": ic_t,
        "market_equalweight": (
            {
                "n_periods": market_leg.n_periods,
                "mean_net": market_leg.mean_net,
                "stdev_net": market_leg.stdev_net,
                "t_stat": market_leg.t_stat,
                "sharpe_annualized": market_leg.sharpe_annualized,
            }
            if market_leg is not None
            else None
        ),
        "periods": [
            {
                "decision_date": p.decision_date.isoformat(),
                "entry_date": p.entry_date.isoformat(),
                "exit_date": p.exit_date.isoformat(),
                "held": list(p.held),
                "per_name_net": list(p.per_name_net),
                "period_net": p.period_net,
            }
            for p in periods
        ],
        "verdict": "RESEARCH_ONLY",
    }


def run_long_short(
    bars_by_symbol: dict[str, list[Bar]],
    hold: int,
    top_frac: Decimal = TOP_FRAC,
) -> dict:
    """Diagnostic long-short leg: long top frac, short bottom frac, equal weight."""
    if hold < 1:
        raise ScreenError("BAD_PARAM: hold must be >= 1")
    calendar = build_calendar(bars_by_symbol)
    indexed = {symbol: _index_symbol(bars) for symbol, bars in bars_by_symbol.items()}
    decision_positions = [
        d
        for d in range(WARMUP_SESSIONS - 1, len(calendar) - hold)
        if (d - (WARMUP_SESSIONS - 1)) % hold == 0 and d + hold < len(calendar)
    ]
    nets: list[Decimal] = []
    skipped = 0
    empty = 0
    for d in decision_positions:
        scored: list[tuple[str, Decimal]] = []
        for symbol, idx in indexed.items():
            score = formation_score(idx, calendar, d)
            if score is not None:
                scored.append((symbol, score))
        if not scored:
            empty += 1
            continue
        scored.sort(key=lambda item: item[1], reverse=True)
        width = max(1, int(Decimal(len(scored)) * top_frac))
        longs = [s for s, _ in scored[:width]]
        shorts = [s for s, _ in scored[-width:]]
        entry_pos, exit_pos = d + 1, d + hold
        legs: list[Decimal] = []
        for symbol in longs:
            net, locked = forward_net(indexed[symbol], calendar, entry_pos, exit_pos)
            if locked:
                skipped += 1
            elif net is not None:
                legs.append(net)
        shorts_nets: list[Decimal] = []
        for symbol in shorts:
            net, locked = forward_net(indexed[symbol], calendar, entry_pos, exit_pos)
            if locked:
                skipped += 1
            elif net is not None:
                shorts_nets.append(-net)
        if not legs or not shorts_nets:
            empty += 1
            continue
        with localcontext() as ctx:
            ctx.prec = 28
            nets.append((_mean(legs) + _mean(shorts_nets)) / Decimal(2))
    leg = summarize_leg(nets, skipped, empty)
    return {
        "rule": "longShort",
        "hold_sessions": hold,
        "top_frac": str(top_frac),
        "n_periods": leg.n_periods,
        "mean_net": leg.mean_net,
        "stdev_net": leg.stdev_net,
        "t_stat": leg.t_stat,
        "sharpe_per_period": leg.sharpe_per_period,
        "sharpe_annualized": leg.sharpe_annualized,
        "degenerate": leg.degenerate,
        "skipped_locked": leg.skipped_locked,
        "empty_periods": leg.empty_periods,
        "verdict": "RESEARCH_ONLY_DIAGNOSTIC",
    }
