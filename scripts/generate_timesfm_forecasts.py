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
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "scripts"))
sys.path.insert(0, str(ROOT_DIR / "src"))

CHECKPOINT = "google/timesfm-3.0-pytorch"
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


def run(args: argparse.Namespace) -> int:
    import numpy
    import timesfm  # type: ignore[import-not-found]

    series_by_symbol = load_series(args)
    print(f"loading      : {CHECKPOINT}", flush=True)
    model = timesfm.TimesFM3Forecaster.from_pretrained(CHECKPOINT)

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
        for (symbol, last_close), output in zip(
            keys, model.predict_batch(contexts=contexts, horizon=MAX_HORIZON), strict=True
        ):
            path = numpy.asarray(output.forecast, dtype=float)
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
        "checkpoint": CHECKPOINT,
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
    return run(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
