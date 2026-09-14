"""Run the declared short-horizon trials: a simple ridge and TimesFM 3.0, at holds 1, 2 and 3.

The budget this obeys
---------------------
`reports/short_horizon/TRIAL-LEDGER.md`, frozen before any result existed: **six published trials**
(two model families x three holds) plus **one** abstention grid declared once for all six. This
script runs exactly those and records each one whatever it returns.

Data, and why it is the governed path
-------------------------------------
Features come from the corporate-action-adjusted store built by `build_mizan_feature_store.py`.
Labels come from `modeling.labels.build_label_dataset` against a **derived adjusted acquisition**, so
the return is measured on adjusted prices while the costs stay quoted on raw executable opens at
dated NSE statutory rules. A window spanning a corporate action nobody could size produces no label
at all.

That is the same path the governed Mizan retrain uses. Nothing here writes to a governed evidence
store or spends a multiplicity ordinal -- these are declared research trials, scored against the
existing `GatePolicyV1` thresholds rather than promoted by them.

The holdout
-----------
The final chronological segment is sliced off **before** any fold is constructed and is not passed to
`evaluate_walk_forward` at all. Evaluating it is a separate `--evaluate-holdout` run, made once,
after a candidate is frozen. This script refuses to do both in one invocation.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import sys
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "scripts"))
sys.path.insert(0, str(ROOT_DIR / "src"))

import run_governed_ridge_training as runner  # noqa: E402
import train_mizan  # noqa: E402
from build_mizan_feature_store import (  # noqa: E402
    authority_manifest_hash,
    code_revision,
    load_validated_demerger_factors,
)

from quant_system.analytics.multiplicity import OverfittingDiagnostics  # noqa: E402
from quant_system.modeling.errors import ModelingError  # noqa: E402
from quant_system.modeling.promotion import GatePolicyV1  # noqa: E402
from quant_system.modeling.rows import FEATURE_NAMES_V3, decimal_result  # noqa: E402
from quant_system.research_short_horizon import hold_specs  # noqa: E402
from quant_system.research_short_horizon.evaluation import (  # noqa: E402
    Decision,
    EvaluationResult,
    evaluate_walk_forward,
)

DECLARED_TRIALS = 9
"""Every SPENT trial in ``reports/short_horizon/TRIAL-LEDGER.md``. The multiplicity count below.

Three model families x three holds: QuantOS ridge (1-3), TimesFM 3.0 (4-6), TimesFM 2.5 (7-9). This
read 6 while the ledger had grown to 9, so every DSR a fresh run published was deflated against a
search two thirds its real size. The ledger's rows 7-9 already carried the corrected figures in
their text, computed by hand; nothing that ran agreed with them.

The drift is now a test failure rather than a discrepancy someone has to notice:
``tests/test_short_horizon_trial_count.py`` reads the ledger and refuses to let the two diverge.
The calibration grid (C1) and the NOISE control are deliberately not counted -- see the ledger.
"""

RIDGE_PENALTY = 1.0
"""One fixed penalty, not searched. Searching it would be more trials against the frozen budget."""

NOISE_SEED = 20260910
"""Fixed seed for the noise control, so "what does this configuration award pure noise?" reproduces."""

TIMESFM_CONTEXT = 512
"""Trailing sessions handed to TimesFM. Its own maximum useful context, and fixed for all holds."""


def turnover_ranked(universe_path: Path, eligible: set[str]) -> list[str]:
    """Research-universe names present in ``eligible``, ranked by median daily turnover."""
    ranked: list[tuple[str, float]] = []
    for line in universe_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("#") or line.startswith("Symbol") or not line.strip():
            continue
        parts = line.split(",")
        if len(parts) >= 5 and parts[0].strip() in eligible:
            ranked.append((parts[0].strip(), float(parts[4])))
    ranked.sort(key=lambda item: -item[1])
    return [symbol for symbol, _ in ranked]


def universe_bound(acquisitions: dict[str, Any]) -> set[str]:
    """Symbols whose selected acquisition carries a point-in-time universe authority.

    The governed label path refuses anything else, and refuses it correctly: without a historical
    universe authority a label cannot be bound to the membership that was true at its decision time.
    """
    return {
        symbol
        for symbol, acquisition in acquisitions.items()
        if acquisition.manifest.historical_universe_authority is not None
    }


def load_feature_store(path: Path, symbols: set[str]) -> dict[str, dict[date, dict[str, str]]]:
    """Feature values for the requested symbols only, keyed by symbol then decision date."""
    out: dict[str, dict[date, dict[str, str]]] = {}
    with gzip.open(path, "rt", newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if row["symbol"] not in symbols:
                continue
            values = {name: decimal_result(Decimal(row[name])) for name in FEATURE_NAMES_V3}
            out.setdefault(row["symbol"], {})[date.fromisoformat(row["date"])] = values
    return out


def build_decisions(
    symbols: list[str],
    acquisitions: dict[str, Any],
    features_by_symbol: dict[str, dict[date, dict[str, str]]],
    *,
    horizon_sessions: int,
    args: argparse.Namespace,
    validated: dict[str, Any],
    authority_hash: str,
    revision: str,
    derived_at: datetime,
) -> tuple[list[Decision], list[tuple[str, str]]]:
    """One :class:`Decision` per instrument per decision date, with governed cost-aware labels."""
    decisions: list[Decision] = []
    refused: list[tuple[str, str]] = []
    for symbol in symbols:
        raw = acquisitions.get(symbol)
        values = features_by_symbol.get(symbol)
        if raw is None or not values:
            refused.append((symbol, "NO_ACQUISITION_OR_FEATURES"))
            continue
        if raw.manifest.historical_universe_authority is None:
            refused.append((symbol, "NO_UNIVERSE_AUTHORITY"))
            continue
        try:
            measured, _plan = train_mizan.adjusted_constituent_acquisition(
                raw,
                corporate_actions_dir=args.corporate_actions_dir,
                validated=validated.get(symbol),
                total_return=not args.price_return,
                authority_hash=authority_hash,
                revision=revision,
                derived_at=derived_at,
            )
            feature_dataset, label_dataset, _calendar = train_mizan._constituent(
                symbol,
                measured,
                values,
                args.calendar_version,
                args.quantity,
                horizon_sessions,
                raw,
            )
        except (ModelingError, runner.ConfigurationRefused, ValueError) as error:
            code = error.code.value if isinstance(error, ModelingError) else type(error).__name__
            refused.append((symbol, code))
            continue

        by_decision = {row.decision_at: row for row in feature_dataset.rows}
        for label in label_dataset.rows:
            feature_row = by_decision.get(label.decision_at)
            if feature_row is None:
                continue
            vector = tuple(float(feature_row.features[name]) for name in FEATURE_NAMES_V3)
            decisions.append(
                Decision(
                    on=label.decision_at.date(),
                    symbol=symbol,
                    features=vector,
                    net_return=Decimal(label.net_return),
                    previous_return=float(feature_row.features["return_1"]),
                )
            )
    return decisions, refused


def split_holdout(
    decisions: list[Decision], holdout_sessions: int
) -> tuple[list[Decision], list[Decision]]:
    """Slice the final chronological segment off before anything looks at anything.

    Returned separately and never handed to the fold builder. A holdout carved out after folds are
    chosen is not a holdout, and one that any calibration has seen is not either.
    """
    ordered = sorted({decision.on for decision in decisions})
    if holdout_sessions >= len(ordered):
        raise ValueError(
            f"holdout of {holdout_sessions} sessions leaves nothing to train on from "
            f"{len(ordered)} decision dates"
        )
    boundary = ordered[-holdout_sessions]
    development = [row for row in decisions if row.on < boundary]
    holdout = [row for row in decisions if row.on >= boundary]
    return development, holdout


def summarise(result: EvaluationResult, *, sample_periods: int) -> dict[str, Any]:
    """Everything one trial produced, in a shape the report and the ledger both read.

    ``sample_periods`` is ignored for the deflation and kept only in the payload for comparison with
    what earlier runs used. Two things were wrong with feeding it to the DSR:

    - it counted every **decision date** in the development partition, while the compounded Sharpe
      rests on non-overlapping portfolio periods -- at hold 3 that overstated the sample by about 3x,
      and the sampling error the deflation subtracts shrinks as 1/sqrt(n), so a larger n makes a
      candidate look *better*;
    - ``deflated_sharpe_ratio`` de-annualises the Sharpe with ``periods_per_year``, which defaulted
      to 252, while the Sharpe reaching it had been annualised with ``252 / held_sessions``. The two
      conventions disagreed by sqrt(held_sessions) and nothing reconciled them.
    """
    candidate = result.candidate
    gate = GatePolicyV1(policy_id="short-horizon-research-v1")
    scored_periods = max(candidate.portfolio_periods, 3)
    dsr = OverfittingDiagnostics.deflated_sharpe_ratio(
        estimated_sharpe=candidate.sharpe,
        num_trials=DECLARED_TRIALS,
        sample_length_bars=scored_periods,
        periods_per_year=round(252 / result.held_sessions),
    )
    passes = (
        dsr >= float(gate.min_deflated_sharpe)
        and candidate.max_drawdown <= float(gate.max_drawdown)
        and candidate.trades >= gate.min_attributable_records
    )
    return {
        "held_sessions": result.held_sessions,
        "horizon_sessions": result.horizon_sessions,
        "folds": result.folds,
        "train_rows": result.train_rows,
        "validation_rows": result.validation_rows,
        "purged_rows": result.purged_rows,
        "embargoed_rows": result.embargoed_rows,
        "missing_predictions": result.missing_predictions,
        "missing_prediction_fraction": (
            round(result.missing_predictions / result.validation_rows, 6)
            if result.validation_rows
            else 0.0
        ),
        "abstention_threshold": str(result.calibration.policy.threshold),
        "abstention_calibrated_on": result.calibration.policy.calibrated_on,
        "abstention_grid": [
            {"threshold": str(t), "mean_per_decision": str(m), "trades": n}
            for t, m, n in result.calibration.scores
        ],
        "abstention_refused": [str(t) for t in result.calibration.refused],
        "abstention_pooled_is_disclosure_only": True,
        "abstention_applied_per_fold": result.applied_policies,
        "deflated_sharpe_ratio": round(dsr, 6),
        "dsr_sample_periods": scored_periods,
        "dsr_periods_per_year": round(252 / result.held_sessions),
        "development_decision_dates": sample_periods,
        "multiplicity_count": DECLARED_TRIALS,
        "gate_policy_id": gate.policy_id,
        "gate_min_deflated_sharpe": gate.min_deflated_sharpe,
        "gate_max_drawdown": gate.max_drawdown,
        "gate_passed": passes,
        "verdict": "PROMOTABLE_PENDING_HOLDOUT" if passes else "RESEARCH_ONLY",
        "strategies": [score.to_dict() for score in result.scores],
    }


def _predictions_for(
    args: argparse.Namespace, held_sessions: int, development: list[Decision]
) -> dict[tuple[date, str], float] | None:
    """The forecaster for one arm. ``None`` means the harness fits its own ridge."""
    if args.arm == "timesfm":
        return _load_forecasts(args.timesfm_forecasts, held_sessions)
    if args.arm == "noise":
        return _noise_predictions(development, held_sessions, seed=0)
    return None


def run(args: argparse.Namespace) -> int:
    print("=== SHORT-HORIZON EXPERIMENT: holds 1, 2, 3 ===", flush=True)
    # `governed_acquisitions` selects the longest acquisition **among those carrying a universe
    # authority**, which is not the same as the longest acquisition. Several symbols have two
    # datasets where the longer one is unbound, and picking by length alone silently dropped
    # RELIANCE, HDFCBANK, ICICIBANK and SBIN from the subset -- exactly the names the turnover rule
    # is meant to select. Use the same selector the governed trainer uses.
    loaded = train_mizan.governed_acquisitions(args.market_cache)
    eligible = universe_bound(loaded)
    ranked = turnover_ranked(args.universe, eligible)
    excluded = sorted(set(turnover_ranked(args.universe, set(loaded))) - eligible)
    symbols = ranked[: args.subset_size]
    acquisitions = {symbol: loaded[symbol] for symbol in symbols}
    print(
        f"governed store   : {len(loaded)} acquisitions, {len(eligible)} universe-bound", flush=True
    )
    if excluded:
        print(f"  not universe-bound (excluded): {', '.join(excluded)}", flush=True)
    print(f"declared subset  : {len(symbols)} names (turnover-ranked, universe-bound)", flush=True)

    features_by_symbol = load_feature_store(args.feature_store, set(symbols))
    print(f"feature store    : {len(features_by_symbol)} symbols", flush=True)

    validated = load_validated_demerger_factors(args.validated_factors)
    authority_hash = authority_manifest_hash(args.corporate_actions_dir) or ""
    revision = code_revision()
    derived_at = datetime.now(UTC)

    if args.arm == "timesfm" and not args.timesfm_forecasts.is_file():
        print(
            f"REFUSED: no TimesFM forecasts at {args.timesfm_forecasts}. "
            f"Run scripts/generate_timesfm_forecasts.py first."
        )
        return 2

    results: dict[str, Any] = {
        "generated_at": derived_at.isoformat(),
        "code_revision": revision,
        "arm": args.arm,
        "declared_trials": DECLARED_TRIALS,
        "subset": symbols,
        "subset_rule": (
            "research-universe names with a universe-bound governed acquisition, turnover-ranked"
        ),
        "excluded_not_universe_bound": excluded,
        "feature_store": args.feature_store.as_posix(),
        "corporate_action_authority_sha256": authority_hash,
        "holdout_sessions": args.holdout_sessions,
        "ridge_penalty": RIDGE_PENALTY if args.arm == "ridge" else None,
        "noise_seed": NOISE_SEED if args.arm == "noise" else None,
        "is_control": args.arm == "noise",
        "trials": {},
    }

    for spec in hold_specs():
        print(f"\n--- hold {spec.held_sessions} (horizon {spec.horizon_sessions}) ---", flush=True)
        decisions, refused = build_decisions(
            symbols,
            acquisitions,
            features_by_symbol,
            horizon_sessions=spec.horizon_sessions,
            args=args,
            validated=validated,
            authority_hash=authority_hash,
            revision=revision,
            derived_at=derived_at,
        )
        if refused:
            print(f"  refused constituents: {len(refused)}", flush=True)
        if not decisions:
            print("  REFUSED: no decision survived label construction")
            results["trials"][spec.label] = {"status": "NO_DECISIONS", "refused": refused}
            continue

        development, holdout = split_holdout(decisions, args.holdout_sessions)
        dates = len({row.on for row in development})
        print(
            f"  decisions        : {len(decisions):,} ({dates:,} development dates, "
            f"{len({r.on for r in holdout}):,} holdout dates reserved)",
            flush=True,
        )

        try:
            result = evaluate_walk_forward(
                development,
                held_sessions=spec.held_sessions,
                horizon_sessions=spec.horizon_sessions,
                embargo_sessions=spec.embargo_sessions,
                validation_size=args.validation_sessions,
                minimum_train=args.minimum_train_sessions,
                penalty=RIDGE_PENALTY,
                periods_per_year=252.0 / spec.held_sessions,
                predictions=_predictions_for(args, spec.held_sessions, development),
            )
        except ValueError as error:
            print(f"  REFUSED: {error}")
            results["trials"][spec.label] = {"status": "REFUSED", "detail": str(error)}
            continue

        sample_periods = len({row.on for row in development})
        summary = summarise(result, sample_periods=sample_periods)
        summary["refused_constituents"] = refused

        if args.arm == "noise" and args.noise_seeds > 1:
            # One seed is a single draw from the noise distribution, which is exactly the kind of
            # n=1 evidence this repository refuses elsewhere. Labels are already built, so extra
            # seeds cost only the evaluation.
            draws: list[dict[str, float]] = []
            for seed in range(args.noise_seeds):
                repeat = evaluate_walk_forward(
                    development,
                    held_sessions=spec.held_sessions,
                    horizon_sessions=spec.horizon_sessions,
                    embargo_sessions=spec.embargo_sessions,
                    validation_size=args.validation_sessions,
                    minimum_train=args.minimum_train_sessions,
                    penalty=RIDGE_PENALTY,
                    periods_per_year=252.0 / spec.held_sessions,
                    predictions=_noise_predictions(development, spec.held_sessions, seed=seed),
                )
                drawn = summarise(repeat, sample_periods=sample_periods)
                draws.append(
                    {
                        "seed": seed,
                        "sharpe": repeat.candidate.sharpe,
                        "deflated_sharpe_ratio": drawn["deflated_sharpe_ratio"],
                        "exposure": repeat.candidate.exposure,
                    }
                )
            dsrs = sorted(item["deflated_sharpe_ratio"] for item in draws)
            sharpes = sorted(item["sharpe"] for item in draws)
            summary["noise_distribution"] = {
                "seeds": len(draws),
                "dsr_min": dsrs[0],
                "dsr_median": dsrs[len(dsrs) // 2],
                "dsr_max": dsrs[-1],
                "dsr_p90": dsrs[int(0.9 * (len(dsrs) - 1))],
                "sharpe_min": sharpes[0],
                "sharpe_median": sharpes[len(sharpes) // 2],
                "sharpe_max": sharpes[-1],
                "draws": draws,
            }
            print(
                f"  noise over {len(draws)} seeds: DSR min {dsrs[0]:.4f} / median "
                f"{dsrs[len(dsrs) // 2]:.4f} / p90 {dsrs[int(0.9 * (len(dsrs) - 1))]:.4f} / "
                f"max {dsrs[-1]:.4f}",
                flush=True,
            )

        results["trials"][spec.label] = summary

        print(
            f"  folds            : {result.folds}, purged {result.purged_rows:,}, "
            f"embargoed {result.embargoed_rows:,}",
            flush=True,
        )
        if result.missing_predictions:
            print(
                f"  MISSING FORECAST : {result.missing_predictions:,} of {result.validation_rows:,} "
                f"out-of-sample decisions "
                f"({result.missing_predictions / result.validation_rows:.1%}) scored as zero",
                flush=True,
            )
        print(f"  abstention       : {result.calibration.policy.threshold}", flush=True)
        print(f"  {'strategy':26}{'sharpe':>9}{'mean/dec':>13}{'trades':>8}{'expo':>7}{'maxDD':>8}")
        for score in result.scores:
            print(
                f"  {score.strategy_id:26}{score.sharpe:>9.4f}"
                f"{float(score.mean_net_return_per_decision):>13.6f}"
                f"{score.trades:>8}{score.exposure:>7.3f}{score.max_drawdown:>8.3f}"
            )
        print(
            f"  DSR              : {summary['deflated_sharpe_ratio']:.6f} "
            f"vs gate {summary['gate_min_deflated_sharpe']} -> {summary['verdict']}",
            flush=True,
        )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    if args.out.exists() and not args.overwrite:
        # Two runs writing one path is a real hazard here, not a hypothetical: in this session a
        # stale run carrying a defective subset selector finished *after* the corrected one and
        # silently replaced its output. It was caught only because the payload records its own
        # subset, and a 19-name result sat where a 45-name one belonged. Moving the incumbent aside
        # makes the collision visible instead of silent.
        stale = args.out.with_suffix(f".superseded-{derived_at:%Y%m%dT%H%M%S}.json")
        args.out.rename(stale)
        print(f"existing output moved aside: {stale.name}", flush=True)
    args.out.write_text(json.dumps(results, indent=2, sort_keys=True), encoding="utf-8")
    print(f"\nwritten          : {args.out}")
    return 0


def _noise_predictions(
    decisions: list[Decision], held_sessions: int, seed: int = 0
) -> dict[tuple[date, str], float]:
    """Seeded pseudo-random forecasts: a forecaster with no information at all.

    This is a **control**, not a candidate. It exists to answer one question the six real trials
    cannot answer about themselves: what deflated Sharpe does this configuration hand out to
    something that knows nothing? A number noise can reach is not evidence, and the only way to
    locate that line is to measure it on the identical folds, costs and abstention grid.

    Scaled to the realised return dispersion so the abstention grid sees forecasts of a plausible
    magnitude. A control whose forecasts were all tiny would abstain everywhere and prove nothing.
    """
    import random

    generator = random.Random(NOISE_SEED + held_sessions * 1000 + seed)
    values = [float(row.net_return) for row in decisions]
    mean = sum(values) / len(values)
    spread = (sum((value - mean) ** 2 for value in values) / max(1, len(values) - 1)) ** 0.5
    return {(row.on, row.symbol): generator.gauss(0.0, spread or 0.01) for row in decisions}


def _load_forecasts(path: Path, held_sessions: int) -> dict[tuple[date, str], float]:
    """External forecasts for one hold, keyed by (decision date, symbol).

    ``held_sessions`` selects the matching forecast step. A single call with ``horizon=3`` returns
    steps 1, 2 and 3, and each declared hold must read **its own** step: scoring a 3-session hold
    against the 1-step forecast would test a model nobody proposed, and would do it silently.
    """
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    key = str(held_sessions)
    out: dict[tuple[date, str], float] = {}
    for item in payload.get("forecasts", []):
        by_hold = item.get("predicted_return_by_hold") or {}
        if key not in by_hold:
            continue
        out[(date.fromisoformat(item["on"]), item["symbol"])] = float(by_hold[key])
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", choices=("ridge", "timesfm", "noise"), default="ridge")
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
        "--index-cache",
        type=Path,
        default=ROOT_DIR / "reports/short_horizon/nifty50-current-index.json",
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
    parser.add_argument(
        "--timesfm-forecasts",
        type=Path,
        default=ROOT_DIR / "reports/short_horizon/timesfm-forecasts.json",
    )
    parser.add_argument("--subset-size", type=int, default=50)
    parser.add_argument("--holdout-sessions", type=int, default=252)
    parser.add_argument("--validation-sessions", type=int, default=126)
    parser.add_argument("--minimum-train-sessions", type=int, default=756)
    parser.add_argument("--quantity", type=int, default=1)
    parser.add_argument("--calendar-version", default="provider-derived-v1")
    parser.add_argument(
        "--noise-seeds",
        type=int,
        default=1,
        help="Noise-control draws. One seed is a single sample; a distribution needs many.",
    )
    parser.add_argument("--price-return", action="store_true")
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace an existing results file in place instead of moving the incumbent aside.",
    )
    parser.add_argument(
        "--out", type=Path, default=ROOT_DIR / "reports/short_horizon/results-ridge.json"
    )
    return run(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
