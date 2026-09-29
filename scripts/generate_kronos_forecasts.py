"""Generate Kronos zero-shot forecasts for short-horizon trial 10.

The declaration is ``reports/kronos_trial/TRIAL-LEDGER.md``, frozen before any real forecast
existed. This script implements that declaration and nothing else: one model, hold 3, a fixed
window, fixed sampling. Anything it would need to choose is chosen there.

Run with the **isolated native-ARM64 interpreter**, never the QuantOS one::

    D:/quant_system_workspaces/scratch/kronos-trial-20260928/venv/Scripts/python.exe \
        scripts/generate_kronos_forecasts.py forecast --dry-run
    ... generate_kronos_forecasts.py probe --dates <count from the dry run>
    ... generate_kronos_forecasts.py forecast --model base --samples 5

Why a separate interpreter
--------------------------
``torch`` is not a QuantOS dependency and must not become one for a research trial. The QuantOS
data loaders it borrows need only the standard library and numpy, so they import there unchanged.
The scorer, ``scripts/run_kronos_trial.py``, runs in the QuantOS environment and reads only this
script's JSON output.

What is forecast, and what is *not* leaked
------------------------------------------
For a decision at session ``k`` the model sees the trailing 512 corporate-action-adjusted daily bars
ending at ``k``: open, high, low, close and volume. Kronos derives ``amount`` itself. It gets no
price from after the close of ``k``. Its four future timestamps are the next four session dates of
the store's calendar. NSE publishes its trading calendar in advance, so knowing which days trade is
not information about prices.

The label measures the open of ``k+1`` to the open of ``k+4``, and Kronos forecasts whole bars, so
the prediction spans exactly that::

    predicted_return = predicted_open[k+4] / predicted_open[k+1] - 1

Both opens are model outputs. The TimesFM arm could only forecast closes and had to use a
close-to-close proxy for the same label; this arm does not.

Only decisions on or after 2024-07-01 are forecast. The Kronos paper states its pre-training data
"extends up to June 2024" and lists India among its exchanges, so any earlier target may have been
memorised.
"""

from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import platform
import sys
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta, timezone
from datetime import time as clock
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "scripts"))
sys.path.insert(0, str(ROOT_DIR / "src"))

IST = timezone(timedelta(hours=5, minutes=30))
WORKSPACE = Path("D:/quant_system_workspaces/scratch/kronos-trial-20260928")

TOKENIZER_REPO = "NeoQuasar/Kronos-Tokenizer-base"
MODEL_REPOS = {"base": "NeoQuasar/Kronos-base", "small": "NeoQuasar/Kronos-small"}
KRONOS_CODE_COMMIT = "67b630e67f6a18c9e9be918d9b4337c960db1e9a"

CONTEXT = 512
"""Trailing bars per forecast: Kronos-small's and Kronos-base's own maximum context."""

STEPS = 4
"""Forecast bars k+1 .. k+4. Hold 3 exits at the open of k+4."""

WINDOW_START = date(2024, 7, 1)
"""First decision date. Kronos's pre-training data 'extends up to June 2024' (arXiv 2508.02739)."""

TEMPERATURE = 1.0
TOP_P = 0.9
TOP_K = 0
SEED_BASE = 20260929

PAUSE_FROM = clock(8, 45)
PAUSE_UNTIL = clock(16, 30)
"""Weekday hours the forecast yields the machine to the paper books: before the 09:00 session,
through the 15:30 close and past the 16:00 XS run."""

NIGHT_BUDGET_HOURS = 14.0
PREFERENCE = (("base", 5), ("base", 1), ("small", 5), ("small", 1))
"""The declared compute rule: the first configuration whose projected run fits one night."""


@dataclass(frozen=True, slots=True)
class Bar:
    on: date
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True, slots=True)
class PlannedDate:
    """One decision date: the names that can be forecast on it, and the four sessions after it."""

    on: date
    symbols: tuple[str, ...]
    future: tuple[date, ...]


def predicted_return(opens: Sequence[float]) -> float:
    """Open of k+1 to open of k+4, from the forecast bars. Refuses a path it cannot price."""
    if len(opens) < STEPS:
        raise ValueError(f"need {STEPS} forecast opens, got {len(opens)}")
    entry, exit_ = float(opens[0]), float(opens[STEPS - 1])
    if not entry > 0 or not exit_ > 0:
        raise ValueError(f"non-positive forecast open: entry {entry}, exit {exit_}")
    return exit_ / entry - 1.0


def date_seed(on: date) -> int:
    """The sampling seed for one decision date, so a resumed run redraws nothing differently."""
    return SEED_BASE + on.toordinal()


def in_market_hours(now: datetime) -> bool:
    """Weekday 08:45-16:30 IST, when the paper books need the machine."""
    local = now.astimezone(IST)
    return local.weekday() < 5 and PAUSE_FROM <= local.time() < PAUSE_UNTIL


def pause_reason(now: datetime, on_ac: bool | None) -> str | None:
    """Why the forecast must wait, or None when it may run.

    An unknown power state does not pause: the check exists to protect a battery, and a machine
    that cannot report one is not running on it.
    """
    if in_market_hours(now):
        return "market hours (weekdays 08:45-16:30 IST belong to the paper books)"
    if on_ac is False:
        return "on battery"
    return None


def plan_dates(
    bars_by_symbol: Mapping[str, Sequence[Bar]],
    *,
    start: date = WINDOW_START,
    context: int = CONTEXT,
    steps: int = STEPS,
) -> list[PlannedDate]:
    """Every decision date on or after ``start`` with ``steps`` later sessions in the calendar.

    The calendar is the union of the subset's session dates. A name is forecast on a date only if
    it has a bar that day and at least ``context`` bars up to and including it.
    """
    calendar = sorted({bar.on for bars in bars_by_symbol.values() for bar in bars})
    positions = {
        symbol: {bar.on: index for index, bar in enumerate(bars)}
        for symbol, bars in bars_by_symbol.items()
    }
    planned: list[PlannedDate] = []
    for index, on in enumerate(calendar):
        if on < start or index + steps >= len(calendar):
            continue
        symbols = tuple(
            symbol
            for symbol in sorted(bars_by_symbol)
            if (position := positions[symbol].get(on)) is not None and position + 1 >= context
        )
        if symbols:
            planned.append(PlannedDate(on, symbols, tuple(calendar[index + 1 : index + 1 + steps])))
    return planned


def read_checkpoint(path: Path) -> tuple[list[dict[str, Any]], set[tuple[str, str]]]:
    """Records already written, tolerating a torn final line from an interrupted write."""
    records: list[dict[str, Any]] = []
    done: set[tuple[str, str]] = set()
    if not path.is_file():
        return records, done
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        records.append(item)
        done.add((item["on"], item["symbol"]))
    return records, done


def choose_configuration(
    seconds_per_date: Mapping[tuple[str, int], float], dates: int
) -> tuple[str, int, float]:
    """The declared rule: first configuration in ``PREFERENCE`` projected to fit one night.

    Returns (model, samples, projected hours). If none fits, the smallest configuration is used and
    simply runs across more nights -- names, dates and context are never cut to make it fit.
    """
    for model, samples in PREFERENCE:
        hours = seconds_per_date[(model, samples)] * dates / 3600.0
        if hours <= NIGHT_BUDGET_HOURS:
            return model, samples, hours
    model, samples = PREFERENCE[-1]
    return model, samples, seconds_per_date[(model, samples)] * dates / 3600.0


def on_ac_power() -> bool | None:
    """True on mains, False on battery, None where Windows cannot say."""
    if sys.platform != "win32":
        return None

    class _PowerStatus(ctypes.Structure):
        _fields_ = [
            ("ACLineStatus", ctypes.c_ubyte),
            ("BatteryFlag", ctypes.c_ubyte),
            ("BatteryLifePercent", ctypes.c_ubyte),
            ("SystemStatusFlag", ctypes.c_ubyte),
            ("BatteryLifeTime", ctypes.c_ulong),
            ("BatteryFullLifeTime", ctypes.c_ulong),
        ]

    status = _PowerStatus()
    windll = getattr(ctypes, "windll", None)
    if windll is None or not windll.kernel32.GetSystemPowerStatus(ctypes.byref(status)):
        return None
    if status.ACLineStatus == 1:
        return True
    if status.ACLineStatus == 0:
        return False
    return None


def hold_awake(active: bool) -> None:
    """Ask Windows not to idle-sleep while forecasting; release the request while paused."""
    windll = getattr(ctypes, "windll", None)
    if sys.platform != "win32" or windll is None:
        return
    continuous, system_required = 0x80000000, 0x00000001
    windll.kernel32.SetThreadExecutionState(continuous | system_required if active else continuous)


def log(message: str) -> None:
    print(f"{datetime.now(IST):%Y-%m-%d %H:%M:%S IST} | {message}", flush=True)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_bars(args: argparse.Namespace) -> dict[str, list[Bar]]:
    """Adjusted daily OHLCV for the declared subset, from the path trials 1-9 used.

    The subset selector and the adjustment are imported, not reimplemented. Adjusted and total
    return, exactly as the TimesFM generator read closes, so the model sees the series the label is
    measured on.
    """
    import train_mizan
    from build_mizan_feature_store import (
        adjusted_bar_points,
        load_corporate_actions,
        load_validated_demerger_factors,
    )
    from run_short_horizon_experiment import turnover_ranked, universe_bound

    loaded = train_mizan.governed_acquisitions(args.market_cache)
    symbols = turnover_ranked(args.universe, universe_bound(loaded))[: args.subset_size]
    validated = load_validated_demerger_factors(args.validated_factors)
    out: dict[str, list[Bar]] = {}
    for symbol in symbols:
        bars, _plan = adjusted_bar_points(
            loaded[symbol],
            load_corporate_actions(args.corporate_actions_dir, symbol),
            total_return=True,
            validated_factors=validated.get(symbol),
        )
        out[symbol] = [
            Bar(
                bar.on,
                float(bar.open),
                float(bar.high),
                float(bar.low),
                float(bar.close),
                float(bar.volume),
            )
            for bar in bars
            if bar.open > 0 and bar.high > 0 and bar.low > 0 and bar.close > 0 and bar.volume >= 0
        ]
    return out


def pinned_revisions(weights_dir: Path) -> dict[str, Any]:
    """What was downloaded: Hub revision and SHA-256 per repository, written at download time."""
    return dict(json.loads((weights_dir / "pinned-revisions.json").read_text(encoding="utf-8")))


def verified_weights(weights_dir: Path, repo: str) -> Path:
    """The local copy of ``repo``, refused unless its weights match the pinned SHA-256.

    Loaded from plain folders rather than the Hub cache: the cache needs symlinks, which this
    Windows account may not create, and a folder read offline cannot silently fetch a newer
    revision.
    """
    record = pinned_revisions(weights_dir)[repo]
    folder = weights_dir / repo.split("/")[1]
    actual = sha256_file(folder / "model.safetensors")
    if actual != record["model_safetensors_sha256"]:
        raise RuntimeError(f"{repo}: weights SHA-256 {actual} differs from the pinned download")
    return folder


def build_predictor(model_key: str, *, weights_dir: Path, kronos_src: Path) -> Any:
    """Kronos's own predictor on the CPU, from the pinned, verified local weights."""
    sys.path.insert(0, str(kronos_src))
    from model import Kronos, KronosPredictor, KronosTokenizer  # type: ignore[import-not-found]

    tokenizer = KronosTokenizer.from_pretrained(str(verified_weights(weights_dir, TOKENIZER_REPO)))
    model = Kronos.from_pretrained(str(verified_weights(weights_dir, MODEL_REPOS[model_key])))
    tokenizer.eval()
    model.eval()
    return KronosPredictor(model, tokenizer, device="cpu", max_context=CONTEXT)


def torch_and_pandas() -> tuple[Any, Any]:
    """The two heavy imports, in one place. They exist only in the isolated interpreter."""
    import pandas  # type: ignore[import-untyped]
    import torch  # type: ignore[import-not-found]

    return torch, pandas


def forecast_batch(
    predictor: Any,
    windows: Sequence[Sequence[Bar]],
    futures: Sequence[Sequence[date]],
    *,
    samples: int,
    seed: int,
) -> list[tuple[list[float], list[float]]]:
    """(forecast opens, forecast closes) for each window, one seeded batch."""
    torch, pandas = torch_and_pandas()
    frames = [
        pandas.DataFrame(
            {
                "open": [bar.open for bar in window],
                "high": [bar.high for bar in window],
                "low": [bar.low for bar in window],
                "close": [bar.close for bar in window],
                "volume": [bar.volume for bar in window],
            }
        )
        for window in windows
    ]
    x_stamps = [pandas.Series(pandas.to_datetime([bar.on for bar in window])) for window in windows]
    y_stamps = [pandas.Series(pandas.to_datetime(list(future))) for future in futures]
    torch.manual_seed(seed)
    with torch.no_grad():
        outputs = predictor.predict_batch(
            frames,
            x_stamps,
            y_stamps,
            pred_len=STEPS,
            T=TEMPERATURE,
            top_k=TOP_K,
            top_p=TOP_P,
            sample_count=samples,
            verbose=False,
        )
    if len(outputs) != len(windows):
        raise RuntimeError(f"predictor returned {len(outputs)} paths for {len(windows)} windows")
    return [
        ([float(v) for v in out["open"].tolist()], [float(v) for v in out["close"].tolist()])
        for out in outputs
    ]


def environment_record(kronos_src: Path) -> dict[str, Any]:
    import numpy

    torch, pandas = torch_and_pandas()
    return {
        "python": sys.version.split()[0],
        "machine": platform.machine(),
        "torch": str(torch.__version__),
        "numpy": numpy.__version__,
        "pandas": str(pandas.__version__),
        "torch_threads": int(torch.get_num_threads()),
        "kronos_code_commit": KRONOS_CODE_COMMIT,
        "kronos_code_sha256": {
            name: sha256_file(kronos_src / "model" / name)
            for name in ("__init__.py", "kronos.py", "module.py")
        },
    }


def run_forecast(args: argparse.Namespace) -> int:
    log("loading the declared subset ...")
    bars_by_symbol = load_bars(args)
    planned = plan_dates(bars_by_symbol)
    total = sum(len(item.symbols) for item in planned)
    log(
        f"subset {len(bars_by_symbol)} names; {len(planned)} decision dates from "
        f"{planned[0].on if planned else '-'} to {planned[-1].on if planned else '-'}; "
        f"{total:,} forecasts"
    )
    if args.dry_run:
        return 0
    if args.model is None or args.samples is None:
        raise SystemExit("--model and --samples are fixed by Amendment 1 of the ledger; pass both")

    out: Path = args.out
    checkpoint = out.with_suffix(".partial.jsonl")
    records, done = read_checkpoint(checkpoint)
    if records:
        log(f"resumed {len(records):,} forecasts from {checkpoint.name}")
    predictor = build_predictor(
        args.model, weights_dir=args.weights_dir, kronos_src=args.kronos_src
    )
    index_of = {
        symbol: {bar.on: i for i, bar in enumerate(bars)} for symbol, bars in bars_by_symbol.items()
    }
    started = time.perf_counter()
    computed = 0
    paused_for: str | None = None
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    with checkpoint.open("a", encoding="utf-8") as handle:
        for number, item in enumerate(planned, 1):
            todo = [s for s in item.symbols if (item.on.isoformat(), s) not in done]
            if not todo:
                continue
            while (reason := pause_reason(datetime.now(UTC), on_ac_power())) is not None:
                if reason != paused_for:
                    log(f"pausing: {reason}")
                    hold_awake(False)
                    paused_for = reason
                time.sleep(args.pause_poll_seconds)
            if paused_for is not None or computed == 0:
                hold_awake(True)
                if paused_for is not None:
                    log("resuming")
                paused_for = None
            windows = []
            for symbol in todo:
                end = index_of[symbol][item.on]
                windows.append(bars_by_symbol[symbol][end + 1 - CONTEXT : end + 1])
            paths = forecast_batch(
                predictor,
                windows,
                [item.future] * len(todo),
                samples=args.samples,
                seed=date_seed(item.on),
            )
            for symbol, window, (opens, closes) in zip(todo, windows, paths, strict=True):
                value = predicted_return(opens)
                record = {
                    "on": item.on.isoformat(),
                    "symbol": symbol,
                    "last_close": window[-1].close,
                    "predicted_open": opens,
                    "predicted_close": closes,
                    "predicted_return": value,
                    "predicted_return_by_hold": {"3": value},
                }
                records.append(record)
                handle.write(json.dumps(record) + "\n")
            handle.flush()
            computed += len(todo)
            if number % 10 == 0:
                elapsed = time.perf_counter() - started
                left = sum(len(p.symbols) for p in planned[number:])
                rate = elapsed / max(computed, 1)
                log(
                    f"{number}/{len(planned)} dates, {len(records):,} forecasts, "
                    f"{elapsed / 3600:.2f} h computing, ~{rate * left / 3600:.1f} h left"
                )
    hold_awake(False)
    pinned = pinned_revisions(args.weights_dir)
    payload = {
        "generated_at": datetime.now(UTC).isoformat(),
        "declaration": "reports/kronos_trial/TRIAL-LEDGER.md",
        "model_repo": MODEL_REPOS[args.model],
        "model_revision": pinned[MODEL_REPOS[args.model]]["revision"],
        "model_sha256": pinned[MODEL_REPOS[args.model]]["model_safetensors_sha256"],
        "tokenizer_repo": TOKENIZER_REPO,
        "tokenizer_revision": pinned[TOKENIZER_REPO]["revision"],
        "tokenizer_sha256": pinned[TOKENIZER_REPO]["model_safetensors_sha256"],
        "samples": args.samples,
        "temperature": TEMPERATURE,
        "top_p": TOP_P,
        "top_k": TOP_K,
        "seed_rule": f"{SEED_BASE} + decision_date.toordinal(), one batch per date",
        "context_length": CONTEXT,
        "forecast_steps": STEPS,
        "window_start": WINDOW_START.isoformat(),
        "prediction_basis": "predicted_open[k+4] / predicted_open[k+1] - 1; hold 3",
        "series_basis": "corporate-action adjusted, total return, OHLCV",
        "environment": environment_record(args.kronos_src),
        "symbols": sorted(bars_by_symbol),
        "decision_dates": len(planned),
        "forecast_count": len(records),
        "compute_seconds_this_invocation": round(time.perf_counter() - started, 1),
        "forecasts": records,
    }
    out.write_text(json.dumps(payload), encoding="utf-8")
    log(f"written {out} ({len(records):,} forecasts)")
    return 0


def synthetic_windows(names: int, seed: int = 7) -> tuple[list[list[Bar]], list[date]]:
    """Random-walk bars for the timing probe. No market data is read."""
    import numpy

    generator = numpy.random.default_rng(seed)
    days: list[date] = []
    day = date(2020, 1, 1)
    while len(days) < CONTEXT + STEPS:
        if day.weekday() < 5:
            days.append(day)
        day += timedelta(days=1)
    windows: list[list[Bar]] = []
    for _ in range(names):
        closes = 100.0 * numpy.exp(numpy.cumsum(generator.normal(0.0, 0.02, CONTEXT)))
        opens = closes * numpy.exp(generator.normal(0.0, 0.005, CONTEXT))
        highs = numpy.maximum(opens, closes) * 1.01
        lows = numpy.minimum(opens, closes) * 0.99
        volumes = generator.lognormal(12.0, 0.5, CONTEXT)
        windows.append(
            [
                Bar(
                    days[i],
                    float(opens[i]),
                    float(highs[i]),
                    float(lows[i]),
                    float(closes[i]),
                    float(volumes[i]),
                )
                for i in range(CONTEXT)
            ]
        )
    return windows, days[CONTEXT:]


def run_probe(args: argparse.Namespace) -> int:
    windows, future = synthetic_windows(args.names)
    timings: dict[tuple[str, int], float] = {}
    measurements: list[dict[str, Any]] = []
    for model_key in ("base", "small"):
        predictor = build_predictor(
            model_key, weights_dir=args.weights_dir, kronos_src=args.kronos_src
        )
        for samples in (5, 1):
            forecast_batch(predictor, windows, [future] * len(windows), samples=samples, seed=1)
            seconds: list[float] = []
            for repeat in range(args.repeats):
                began = time.perf_counter()
                forecast_batch(
                    predictor, windows, [future] * len(windows), samples=samples, seed=2 + repeat
                )
                seconds.append(time.perf_counter() - began)
            per_date = sum(seconds) / len(seconds)
            timings[(model_key, samples)] = per_date
            hours = per_date * args.dates / 3600.0
            measurements.append(
                {
                    "model": model_key,
                    "samples": samples,
                    "names_per_batch": len(windows),
                    "seconds_per_date": round(per_date, 3),
                    "repeats": [round(value, 3) for value in seconds],
                    "projected_hours": round(hours, 2),
                }
            )
            log(f"{model_key} S={samples}: {per_date:.2f} s per date -> {hours:.1f} h")
    model_key, samples, hours = choose_configuration(timings, args.dates)
    payload = {
        "measured_at": datetime.now(UTC).isoformat(),
        "data": "synthetic random-walk bars only; no market data was read",
        "decision_dates": args.dates,
        "rule": f"first of {list(PREFERENCE)} projected <= {NIGHT_BUDGET_HOURS} h",
        "measurements": measurements,
        "chosen": {"model": model_key, "samples": samples, "projected_hours": round(hours, 2)},
        "environment": environment_record(args.kronos_src),
        "pinned_weights": pinned_revisions(args.weights_dir),
    }
    args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    log(f"chosen: {model_key} S={samples} ({hours:.1f} h); written {args.out}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    # Nothing here may reach the network: the weights are pinned local copies, verified by hash.
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ.setdefault("HF_HOME", str(WORKSPACE / "hf-home"))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kronos-src", type=Path, default=WORKSPACE / "kronos-src")
    parser.add_argument("--weights-dir", type=Path, default=WORKSPACE / "weights")
    commands = parser.add_subparsers(dest="command", required=True)

    probe = commands.add_parser("probe", help="time each configuration on synthetic bars")
    probe.add_argument("--dates", type=int, required=True)
    probe.add_argument("--names", type=int, default=45)
    probe.add_argument("--repeats", type=int, default=3)
    probe.add_argument(
        "--out", type=Path, default=ROOT_DIR / "reports/kronos_trial/kronos-probe.json"
    )

    forecast = commands.add_parser("forecast", help="the trial's forecasts")
    forecast.add_argument("--model", choices=sorted(MODEL_REPOS), default=None)
    forecast.add_argument("--samples", type=int, choices=(1, 5), default=None)
    forecast.add_argument("--dry-run", action="store_true")
    forecast.add_argument("--pause-poll-seconds", type=float, default=300.0)
    forecast.add_argument(
        "--market-cache",
        type=Path,
        default=ROOT_DIR / "data/evidence/market-cache/nifty50-current-20160822-20260821/store",
    )
    forecast.add_argument(
        "--universe",
        type=Path,
        default=ROOT_DIR / "data/authorities/nse-research-universe-liquid-10y.csv",
    )
    forecast.add_argument(
        "--corporate-actions-dir",
        type=Path,
        default=ROOT_DIR
        / "data/evidence/market-cache/all-market-20160822-20260821/corporate-actions",
    )
    forecast.add_argument(
        "--validated-factors",
        type=Path,
        default=ROOT_DIR / "data/authorities/nse-validated-demerger-factors.json",
    )
    forecast.add_argument("--subset-size", type=int, default=50)
    forecast.add_argument(
        "--out", type=Path, default=ROOT_DIR / "reports/kronos_trial/kronos-forecasts.json"
    )
    args = parser.parse_args(argv)
    if args.command == "probe":
        return run_probe(args)
    return run_forecast(args)


if __name__ == "__main__":
    raise SystemExit(main())
