"""Score short-horizon trial 10 (Kronos zero-shot, hold 3) exactly as declared, and only once.

Declaration: ``reports/kronos_trial/TRIAL-LEDGER.md``, frozen before any real forecast existed.
Forecasts: ``reports/kronos_trial/kronos-forecasts.json``, written by
``scripts/generate_kronos_forecasts.py`` under the isolated interpreter. This script runs in the
QuantOS environment and imports the short-horizon harness rather than reimplementing it:

- **Decisions, labels and costs** come from ``run_short_horizon_experiment.build_decisions``, the
  governed label path that trials 1-9 used. Dated NSE statutory costs are quoted on raw
  executable opens.
- **Scoring** is ``research_short_horizon.evaluation.score_decisions``, the repaired
  staggered-tranche ledger (``056fb1c6``).
- **The noise control** is ``run_short_horizon_experiment._noise_predictions``, seeds 0-29, sent
  through the identical rule on the identical decisions.

What differs from trials 1-9, and why, is written in the ledger before the result. Only decisions
on or after 2024-07-01 are scored, because Kronos's pre-training data runs to June 2024. The rule
is a fixed cost threshold, because that window is too short for the harness's calibration folds.

"Once" is enforced: an existing results file is a refusal, not something to overwrite.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import numpy as np

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "scripts"))
sys.path.insert(0, str(ROOT_DIR / "src"))

from quant_system.analytics.multiplicity import OverfittingDiagnostics  # noqa: E402
from quant_system.modeling.promotion import GatePolicyV1  # noqa: E402
from quant_system.research_short_horizon.evaluation import (  # noqa: E402
    Decision,
    StrategyScore,
    score_decisions,
)

DECLARED_TRIALS = 10
"""Ordinal 10 of the short-horizon family: trials 1-9 in its ledger, then this one."""

HELD_SESSIONS = 3
PERIODS_PER_YEAR = round(252 / HELD_SESSIONS)
THRESHOLD = 0.00224
"""Long when the forecast open-to-open return beats the round trip; otherwise cash."""

WINDOW_START = date(2024, 7, 1)
NOISE_SEEDS = 30
MIN_NAMES_FOR_IC = 5
IC_STRIDE = HELD_SESSIONS
"""Every third decision date: hold-3 labels on those dates do not overlap."""


def load_predictions(path: Path) -> dict[tuple[date, str], float]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        (date.fromisoformat(item["on"]), str(item["symbol"])): float(item["predicted_return"])
        for item in payload["forecasts"]
    }


def in_window(decisions: Sequence[Decision], start: date = WINDOW_START) -> list[Decision]:
    """Decisions on or after ``start``, ordered by date then name."""
    return sorted(
        (decision for decision in decisions if decision.on >= start),
        key=lambda decision: (decision.on, decision.symbol),
    )


def take_by_threshold(
    decisions: Sequence[Decision],
    predictions: Mapping[tuple[date, str], float],
    threshold: float = THRESHOLD,
) -> tuple[list[bool], int]:
    """The declared rule, and how many decisions had no forecast. A missing forecast is cash."""
    take: list[bool] = []
    missing = 0
    for decision in decisions:
        value = predictions.get((decision.on, decision.symbol))
        if value is None:
            missing += 1
            take.append(False)
        else:
            take.append(value > threshold)
    return take, missing


def deflated(score: StrategyScore) -> float:
    return float(
        OverfittingDiagnostics.deflated_sharpe_ratio(
            estimated_sharpe=score.sharpe,
            num_trials=DECLARED_TRIALS,
            sample_length_bars=max(score.portfolio_periods, 3),
            periods_per_year=PERIODS_PER_YEAR,
        )
    )


def gate_passes(score: StrategyScore, dsr: float, gate: GatePolicyV1) -> bool:
    return (
        dsr >= float(gate.min_deflated_sharpe)
        and score.max_drawdown <= float(gate.max_drawdown)
        and score.trades >= gate.min_attributable_records
    )


def verdict(
    *, gate_passed: bool, candidate_sharpe: float, noise_sharpes: Sequence[float], always: float
) -> tuple[str, dict[str, bool]]:
    """All three declared conditions, each reported, then the verdict they imply."""
    checks = {
        "gate_passed": gate_passed,
        "beats_every_noise_seed": bool(noise_sharpes) and candidate_sharpe > max(noise_sharpes),
        "beats_always_trade": candidate_sharpe > always,
    }
    passed = all(checks.values())
    return ("PASS_PENDING_INDEPENDENT_CHECK" if passed else "RESEARCH_ONLY"), checks


def average_ranks(values: Sequence[float]) -> np.ndarray:
    """Ranks from 1, ties sharing their average rank."""
    order = np.argsort(np.asarray(values, dtype=float), kind="mergesort")
    ranks = np.empty(len(values), dtype=float)
    ordered = np.asarray(values, dtype=float)[order]
    start = 0
    while start < len(ordered):
        end = start
        while end + 1 < len(ordered) and ordered[end + 1] == ordered[start]:
            end += 1
        ranks[order[start : end + 1]] = (start + end) / 2.0 + 1.0
        start = end + 1
    return ranks


def spearman(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    """Spearman rank correlation, or None when either side has no spread."""
    if len(xs) != len(ys) or len(xs) < 2:
        raise ValueError("spearman needs two equal-length samples of at least two")
    rx, ry = average_ranks(xs), average_ranks(ys)
    if float(np.std(rx)) == 0.0 or float(np.std(ry)) == 0.0:
        return None
    return float(np.corrcoef(rx, ry)[0, 1])


def t_stat(values: Sequence[float]) -> float | None:
    if len(values) < 2:
        return None
    array = np.asarray(values, dtype=float)
    spread = float(array.std(ddof=1))
    if spread == 0.0:
        return None
    return float(array.mean() / (spread / math.sqrt(len(array))))


def by_date(
    decisions: Sequence[Decision], predictions: Mapping[tuple[date, str], float]
) -> dict[date, list[tuple[float, float]]]:
    """(prediction, realised net return) per decision date, forecast names only."""
    grouped: dict[date, list[tuple[float, float]]] = {}
    for decision in decisions:
        value = predictions.get((decision.on, decision.symbol))
        if value is not None:
            grouped.setdefault(decision.on, []).append((value, float(decision.net_return)))
    return grouped


def diagnostics(
    decisions: Sequence[Decision], predictions: Mapping[tuple[date, str], float]
) -> dict[str, Any]:
    """Declared diagnostics (b) and (c). Reported, never verdict-bearing."""
    grouped = by_date(decisions, predictions)
    ics: list[tuple[date, float]] = []
    edges: list[tuple[date, float]] = []
    for on, rows in sorted(grouped.items()):
        if len(rows) < MIN_NAMES_FOR_IC:
            continue
        ic = spearman([p for p, _ in rows], [r for _, r in rows])
        if ic is not None:
            ics.append((on, ic))
        ranked = sorted(rows, key=lambda row: row[0], reverse=True)
        top = ranked[: max(1, len(ranked) // 5)]
        edges.append((on, sum(r for _, r in top) / len(top) - sum(r for _, r in rows) / len(rows)))

    def summary(series: list[tuple[date, float]]) -> dict[str, Any]:
        spaced = [value for index, (_, value) in enumerate(series) if index % IC_STRIDE == 0]
        return {
            "dates": len(series),
            "mean_all_dates": (sum(v for _, v in series) / len(series)) if series else None,
            "non_overlapping_dates": len(spaced),
            "mean_non_overlapping": (sum(spaced) / len(spaced)) if spaced else None,
            "t_non_overlapping": t_stat(spaced),
        }

    return {
        "rank_ic": summary(ics),
        "top_quintile_edge_vs_equal_weight": summary(edges),
        "note": "declared diagnostics (b) and (c); never verdict-bearing",
    }


def build_window_decisions(args: argparse.Namespace) -> tuple[list[Decision], dict[str, Any]]:
    """The harness's decisions for hold 3, restricted to the declared window."""
    import run_short_horizon_experiment as harness
    import train_mizan
    from build_mizan_feature_store import (
        authority_manifest_hash,
        code_revision,
        load_validated_demerger_factors,
    )

    from quant_system.research_short_horizon import hold_specs

    loaded = train_mizan.governed_acquisitions(args.market_cache)
    eligible = harness.universe_bound(loaded)
    symbols = harness.turnover_ranked(args.universe, eligible)[: args.subset_size]
    acquisitions = {symbol: loaded[symbol] for symbol in symbols}
    features = harness.load_feature_store(args.feature_store, set(symbols))
    spec = next(item for item in hold_specs() if item.held_sessions == HELD_SESSIONS)
    decisions, refused = harness.build_decisions(
        symbols,
        acquisitions,
        features,
        horizon_sessions=spec.horizon_sessions,
        args=argparse.Namespace(
            corporate_actions_dir=args.corporate_actions_dir,
            price_return=False,
            calendar_version="provider-derived-v1",
            quantity=1,
        ),
        validated=load_validated_demerger_factors(args.validated_factors),
        authority_hash=authority_manifest_hash(args.corporate_actions_dir) or "",
        revision=code_revision(),
        derived_at=datetime.now(UTC),
    )
    context = {
        "subset": symbols,
        "refused": [list(item) for item in refused],
        "horizon_sessions": spec.horizon_sessions,
        "all_decisions": len(decisions),
    }
    return in_window(decisions), context


def run(args: argparse.Namespace) -> int:
    if args.out.exists():
        print(f"REFUSED: {args.out} exists. The trial is scored once; the result stands.")
        return 2
    if not args.forecasts.is_file():
        print(f"REFUSED: no forecasts at {args.forecasts}")
        return 2
    import run_short_horizon_experiment as harness

    predictions = load_predictions(args.forecasts)
    decisions, context = build_window_decisions(args)
    if not decisions:
        print("REFUSED: no decisions in the declared window")
        return 2
    take, missing = take_by_threshold(decisions, predictions)

    def score(strategy: str, choices: Sequence[bool]) -> StrategyScore:
        return score_decisions(
            strategy,
            decisions,
            choices,
            periods_per_year=PERIODS_PER_YEAR,
            held_sessions=HELD_SESSIONS,
        )

    candidate = score("CANDIDATE", take)
    any_positive, _ = take_by_threshold(decisions, predictions, threshold=0.0)
    scores = [
        candidate,
        score("CANDIDATE_ANY_POSITIVE", any_positive),
        score("CASH", [False] * len(decisions)),
        score("ALWAYS_TRADE", [True] * len(decisions)),
        score("PREVIOUS_SIGN", [row.previous_return > 0 for row in decisions]),
    ]
    gate = GatePolicyV1(policy_id="kronos-trial-10")
    candidate_dsr = deflated(candidate)
    passed_gate = gate_passes(candidate, candidate_dsr, gate)

    noise: list[dict[str, Any]] = []
    for seed in range(NOISE_SEEDS):
        drawn = harness._noise_predictions(decisions, HELD_SESSIONS, seed=seed)
        noise_take, _ = take_by_threshold(decisions, drawn)
        noise_score = score(f"NOISE_{seed}", noise_take)
        noise.append(
            {
                "seed": seed,
                "sharpe": noise_score.sharpe,
                "dsr": deflated(noise_score),
                "trades": noise_score.trades,
            }
        )
    always = next(item for item in scores if item.strategy_id == "ALWAYS_TRADE")
    outcome, checks = verdict(
        gate_passed=passed_gate,
        candidate_sharpe=candidate.sharpe,
        noise_sharpes=[item["sharpe"] for item in noise],
        always=always.sharpe,
    )
    noise_dsrs = sorted(item["dsr"] for item in noise)
    results = {
        "generated_at": datetime.now(UTC).isoformat(),
        "declaration": "reports/kronos_trial/TRIAL-LEDGER.md",
        "trial": 10,
        "held_sessions": HELD_SESSIONS,
        "window_start": WINDOW_START.isoformat(),
        "window_first_decision": decisions[0].on.isoformat(),
        "window_last_decision": decisions[-1].on.isoformat(),
        "decisions": len(decisions),
        "decision_dates": len({row.on for row in decisions}),
        "missing_forecasts": missing,
        "threshold": THRESHOLD,
        "multiplicity_count": DECLARED_TRIALS,
        "periods_per_year": PERIODS_PER_YEAR,
        "candidate_dsr": round(candidate_dsr, 6),
        "gate": {
            "policy_id": gate.policy_id,
            "min_deflated_sharpe": gate.min_deflated_sharpe,
            "max_drawdown": gate.max_drawdown,
            "min_attributable_records": gate.min_attributable_records,
            "passed": passed_gate,
        },
        "checks": checks,
        "verdict": outcome,
        "strategies": [item.to_dict() for item in scores],
        "noise_control": {
            "seeds": NOISE_SEEDS,
            "sharpe_max": max(item["sharpe"] for item in noise),
            "sharpe_median": float(np.median([item["sharpe"] for item in noise])),
            "dsr_min": noise_dsrs[0],
            "dsr_median": float(np.median(noise_dsrs)),
            "dsr_max": noise_dsrs[-1],
            "draws": noise,
        },
        "diagnostics": {
            **diagnostics(decisions, predictions),
            "candidate_any_positive": "see strategies: CANDIDATE_ANY_POSITIVE",
            "missing_forecasts": missing,
        },
        "harness": context,
        "forecasts_file": args.forecasts.as_posix(),
        "forecasts_sha256": hashlib.sha256(args.forecasts.read_bytes()).hexdigest(),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"decisions {len(decisions):,} ({results['decision_dates']} dates), missing {missing}")
    for item in scores:
        print(
            f"  {item.strategy_id:24s} sharpe {item.sharpe:+.4f}  trades {item.trades:,}  "
            f"exposure {item.exposure:.3f}  maxDD {item.max_drawdown:.4f}"
        )
    print(f"candidate DSR (10 trials) {candidate_dsr:.6f}; gate passed: {passed_gate}")
    print(
        f"noise Sharpe max {results['noise_control']['sharpe_max']:+.4f}, "
        f"DSR median {results['noise_control']['dsr_median']:.4f}"
    )
    print(f"checks {checks}")
    print(f"VERDICT {outcome}")
    print(f"written {args.out}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--forecasts", type=Path, default=ROOT_DIR / "reports/kronos_trial/kronos-forecasts.json"
    )
    parser.add_argument(
        "--feature-store",
        type=Path,
        default=ROOT_DIR
        / "data/evidence/feature-store/mizan-adjusted-v1/mizan_feature_store.csv.gz",
    )
    parser.add_argument(
        "--market-cache",
        type=Path,
        default=ROOT_DIR / "data/evidence/market-cache/nifty50-current-20160822-20260821/store",
    )
    parser.add_argument(
        "--universe",
        type=Path,
        default=ROOT_DIR / "data/authorities/nse-research-universe-liquid-10y.csv",
    )
    parser.add_argument(
        "--corporate-actions-dir",
        type=Path,
        default=ROOT_DIR
        / "data/evidence/market-cache/all-market-20160822-20260821/corporate-actions",
    )
    parser.add_argument(
        "--validated-factors",
        type=Path,
        default=ROOT_DIR / "data/authorities/nse-validated-demerger-factors.json",
    )
    parser.add_argument("--subset-size", type=int, default=50)
    parser.add_argument(
        "--out", type=Path, default=ROOT_DIR / "reports/kronos_trial/results-kronos.json"
    )
    return run(parser.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
