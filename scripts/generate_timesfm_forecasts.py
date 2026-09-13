"""Generate TimesFM 3.0 zero-shot forecasts for the declared short-horizon subset.

Run with the **isolated** interpreter, not the QuantOS one::

    D:/quant_system_workspaces/scratch/timesfm-probe-20260910/Scripts/python.exe \
        scripts/generate_timesfm_forecasts.py

Why this is a separate script
-----------------------------
Three reasons, all practical:

- **`torch` is not a QuantOS dependency** and must not become one for a research screen. This script
  runs under the isolated environment; the evaluation harness reads its JSON output and never
  imports `timesfm`.
- **It is the expensive step.** ~116 ms per series per decision, and 2.57 GB resident. Separating it
  means the evaluation can be re-run freely without re-forecasting, and means the forecasting never
  runs concurrently with a training job -- which cost a governed retrain to OOM in this session.
- **One pass serves all three holds.** A single call with ``horizon=3`` returns steps 1, 2 and 3, so
  the three declared holds share one forecast rather than costing three passes.

What is forecast, and what is *not* leaked
------------------------------------------
For a decision at session ``k`` the model sees **adjusted closes up to and including session k** and
nothing later. The predicted return is from the entry open at ``k+1`` to the exit open at
``k+hold``... which the model cannot see, so it is approximated by the close-to-close path it does
predict:

    predicted_return(hold) = forecast[hold] / close[k] - 1

That is deliberately an approximation, and it is the *right* one to make: the alternative is to hand
the model the entry open, which is a price from after the decision. A forecast that needs
tomorrow's open to predict tomorrow's open is not a forecast.

The consequence is that the TimesFM arm predicts a close-to-close return while being **scored** on
the open-to-open net return the label actually measures. That mismatch is real, it is disclosed with
every TimesFM number, and it is not correctable without leaking.

No covariates are supplied. ``past_future_covariates`` is a leakage surface by construction -- it
presents values to the model as known over the forecast window -- and the declared trial is zero-shot
with no covariates.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Callable
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "scripts"))
sys.path.insert(0, str(ROOT_DIR / "src"))

CHECKPOINT = "google/timesfm-3.0-pytorch"
"""Default checkpoint, and deliberately still the default.

Trials 4-6 were published against these weights. Swapping this constant to point at 2.5 would have
made that published evidence unreproducible from this script, so the checkpoint is a flag instead
and 3.0 remains what you get if you pass nothing.
"""

CHECKPOINT_2P5 = "google/timesfm-2.5-200m-pytorch"
"""Apache-2.0, where the 3.0 weights are `timesfm-non-commercial-license-v1.0`.

This is a different architecture, not a version bump. Pointing the 2.5 class at a 3.0 checkpoint
fails on missing `state_dict` keys and vice versa, so `build_predictor` dispatches on the checkpoint
name rather than letting a mismatched pair fail deep inside `from_pretrained`.
"""

BATCH = 8
"""`per_core_batch_size` for the 2.5 path. 8 is the value the scratchpad smoke validated end to end
(shape, determinism and affine equivariance); a 3-4 hour run is the wrong place to introduce an
unvalidated one.
"""

CONTEXT = 512
MAX_HORIZON = 3
"""Steps 1, 2 and 3 in one pass -- the three declared holds share a single forecast."""


def load_series(args: argparse.Namespace) -> dict[str, list[tuple[date, float]]]:
    """Adjusted close series per symbol, from the same path the evaluation uses.

    Adjusted, not raw. The evaluation measures returns on the adjusted basis, so forecasting the raw
    series would have the model predicting a different quantity from the one it is scored on -- on
    top of the close-to-close approximation, which is one mismatch too many.
    """
    import train_mizan
    from build_mizan_feature_store import (
        adjusted_bar_points,
        load_corporate_actions,
        load_validated_demerger_factors,
    )
    from run_short_horizon_experiment import turnover_ranked, universe_bound

    # The same selector the evaluation uses: longest acquisition *among those carrying a universe
    # authority*. Selecting by length alone picks unbound duplicates and silently drops RELIANCE,
    # HDFCBANK, ICICIBANK and SBIN -- the very names the turnover rule exists to select. The two
    # scripts must agree on the subset or they are not evaluating the same experiment.
    loaded = train_mizan.governed_acquisitions(args.market_cache)
    symbols = turnover_ranked(args.universe, universe_bound(loaded))[: args.subset_size]
    print(f"subset       : {len(symbols)} names", flush=True)

    validated = load_validated_demerger_factors(args.validated_factors)
    out: dict[str, list[tuple[date, float]]] = {}
    for symbol in symbols:
        bars, _plan = adjusted_bar_points(
            loaded[symbol],
            load_corporate_actions(args.corporate_actions_dir, symbol),
            total_return=True,
            validated_factors=validated.get(symbol),
        )
        out[symbol] = [(bar.on, float(bar.close)) for bar in bars if bar.close > 0]
    return out


def build_predictor(timesfm: Any, numpy: Any, checkpoint: str) -> Callable[[list[Any]], Any]:
    """Return ``predict(contexts) -> ndarray`` of shape ``(n_series, MAX_HORIZON)``.

    The two families do not share an API. 3.0 exposes ``predict_batch`` and returns objects carrying
    a ``.forecast`` attribute; 2.5 needs an explicit ``compile()`` first and returns a bare
    ``(points, quantiles)`` tuple. Normalising both to one callable keeps a single forecast loop
    below, so the record-building code cannot drift between arms -- the 3.0 arm has already shipped
    one bug of exactly that shape, reading the 1-step forecast for all three holds.
    """
    if "timesfm-2.5" in checkpoint:
        model = timesfm.TimesFM_2p5_200M_torch.from_pretrained(checkpoint)
        model.compile(
            timesfm.ForecastConfig(
                max_context=CONTEXT,
                max_horizon=MAX_HORIZON,
                normalize_inputs=True,
                per_core_batch_size=BATCH,
            )
        )

        def predict_2p5(contexts: list[Any]) -> Any:
            # `forecast` pads the batch internally and trims back to len(inputs), so the row count
            # matches the caller's contexts. Asserted below rather than assumed.
            points, _quantiles = model.forecast(horizon=MAX_HORIZON, inputs=list(contexts))
            return numpy.asarray(points, dtype=float)

        return predict_2p5

    model = timesfm.TimesFM3Forecaster.from_pretrained(checkpoint)

    def predict_3(contexts: list[Any]) -> Any:
        outputs = model.predict_batch(contexts=contexts, horizon=MAX_HORIZON)
        return numpy.asarray([output.forecast for output in outputs], dtype=float)

    return predict_3


def run(args: argparse.Namespace) -> int:
    import numpy
    import timesfm  # type: ignore[import-not-found]

    series_by_symbol = load_series(args)
    print(f"loading      : {args.checkpoint}", flush=True)
    predict = build_predictor(timesfm, numpy, args.checkpoint)

    symbols = sorted(series_by_symbol)
    # Every decision date on which *every* subset name has enough context. Using the shared grid
    # keeps the forecast set aligned with the evaluation's cross-section.
    dated = {
        symbol: {on: i for i, (on, _) in enumerate(rows)}
        for symbol, rows in series_by_symbol.items()
    }
    all_dates = sorted({on for rows in series_by_symbol.values() for on, _ in rows[CONTEXT:]})
    if args.stride > 1:
        all_dates = all_dates[:: args.stride]
    if args.limit_dates:
        all_dates = all_dates[-args.limit_dates :]
    print(f"decision dates: {len(all_dates):,} (stride {args.stride})", flush=True)

    # Checkpointed as JSON Lines, appended as it goes. The first version wrote only at the end, so
    # a session restart at 300 of 1,967 dates threw away 27 minutes of forecasting. A ~2.5 hour run
    # that cannot survive an interruption is a run that will be started several times and finished
    # none of them.
    checkpoint = args.out.with_suffix(".partial.jsonl")
    done: set[tuple[str, str]] = set()
    forecasts: list[dict[str, Any]] = []
    if checkpoint.is_file() and not args.restart:
        for line in checkpoint.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue  # a torn final line from a kill mid-write; drop it and recompute that date
            forecasts.append(item)
            done.add((item["on"], item["symbol"]))
        print(f"resumed      : {len(forecasts):,} forecasts from {checkpoint.name}", flush=True)
    elif checkpoint.is_file():
        checkpoint.unlink()

    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    handle = checkpoint.open("a", encoding="utf-8")
    started = time.perf_counter()
    for index, on in enumerate(all_dates, 1):
        contexts: list[Any] = []
        keys: list[tuple[str, float]] = []
        for symbol in symbols:
            if (on.isoformat(), symbol) in done:
                continue
            position = dated[symbol].get(on)
            if position is None or position < CONTEXT:
                continue
            window = [
                value for _, value in series_by_symbol[symbol][position - CONTEXT : position + 1]
            ]
            contexts.append(numpy.asarray(window, dtype=numpy.float32))
            keys.append((symbol, window[-1]))
        if not contexts:
            continue
        paths = predict(contexts)
        if len(paths) != len(keys):
            raise RuntimeError(
                f"forecaster returned {len(paths)} paths for {len(keys)} contexts on {on}; "
                "the previous zip(..., strict=True) would have caught this and it must stay caught"
            )
        for (symbol, last_close), path in zip(keys, paths, strict=True):
            record = {
                "on": on.isoformat(),
                "symbol": symbol,
                "last_close": last_close,
                # Step `h` of the forecast is the close `h` sessions ahead. Hold `h` is scored
                # open(k+1) -> open(k+h); this is the close-to-close proxy documented above.
                "predicted_return": float(path[0] / last_close - 1.0),
                "predicted_return_by_hold": {
                    str(h): float(path[h - 1] / last_close - 1.0) for h in range(1, MAX_HORIZON + 1)
                },
            }
            forecasts.append(record)
            handle.write(json.dumps(record) + "\n")
        if index % 25 == 0:
            handle.flush()
            elapsed = time.perf_counter() - started
            rate = elapsed / index
            print(
                f"  {index}/{len(all_dates)} dates, {len(forecasts):,} forecasts, "
                f"{elapsed / 60:.1f} min elapsed, ~{rate * (len(all_dates) - index) / 60:.1f} min left",
                flush=True,
            )

    handle.close()
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "checkpoint": args.checkpoint,
        "fine_tuned": False,
        "context_length": CONTEXT,
        "max_horizon": MAX_HORIZON,
        "stride": args.stride,
        "covariates": "none -- past_future_covariates is a leakage surface and the trial is zero-shot",
        "prediction_basis": "close-to-close proxy for an open-to-open label; see the module docstring",
        "series_basis": "corporate-action adjusted, total return",
        "symbols": symbols,
        "forecast_count": len(forecasts),
        "seconds_total": round(time.perf_counter() - started, 1),
        "forecasts": forecasts,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload), encoding="utf-8")
    print(f"\nforecasts    : {len(forecasts):,}")
    print(f"elapsed      : {payload['seconds_total'] / 60:.1f} min")
    print(f"written      : {args.out}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
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
    parser.add_argument("--subset-size", type=int, default=50)
    parser.add_argument(
        "--checkpoint",
        default=CHECKPOINT,
        help=(
            f"Forecasting checkpoint. Default {CHECKPOINT} (non-commercial licence, trials 4-6). "
            f"Use {CHECKPOINT_2P5} for the Apache-2.0 arm (trials 7-9). Pair a non-default "
            "checkpoint with a non-default --out: the default output path resumes from the 3.0 "
            "partial file and would silently produce a mixed-checkpoint forecast set."
        ),
    )
    parser.add_argument(
        "--stride",
        type=int,
        default=1,
        help="Forecast every Nth decision date. A stride > 1 is a declared subsample and must be "
        "recorded in the trial ledger before the run.",
    )
    parser.add_argument("--limit-dates", type=int, default=0)
    parser.add_argument(
        "--restart",
        action="store_true",
        help="Discard any checkpoint and forecast from scratch.",
    )
    parser.add_argument(
        "--out", type=Path, default=ROOT_DIR / "reports/short_horizon/timesfm-forecasts.json"
    )
    args = parser.parse_args()

    # Fail closed on the one combination that destroys evidence silently.
    #
    # `run` resumes from `<out>.partial.jsonl` and skips every (symbol, date) already present. With
    # a non-default checkpoint and the default output path, that resume reads the 3.0 partial file:
    # the run would emit a forecast set that is part 3.0 and part 2.5, indistinguishable from either,
    # and overwrite the evidence behind published trials 4-6 on the way. Nothing downstream could
    # detect it -- the record schema carries no per-row checkpoint -- so it has to be refused here.
    if args.checkpoint != CHECKPOINT and args.out == parser.get_default("out"):
        parser.error(
            f"--checkpoint {args.checkpoint} was given with the default --out ({args.out}). That "
            "path holds the 3.0 forecasts behind published trials 4-6, and the run would resume "
            "from their partial file and silently mix two checkpoints into one set. Pass an "
            "explicit --out, e.g. reports/short_horizon/timesfm25-forecasts.json"
        )

    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
