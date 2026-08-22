"""Run the governed ridge trial across a real NSE universe, one instrument at a time.

**This is not a portfolio backtest, and the distinction matters.** The governed dataset contract is
single-instrument: ``build_label_dataset`` rejects any feature row whose instrument differs from its
acquisition manifest (``modeling/labels.py:135``). So a universe run is N independent single-name
studies of the same model family, not one cross-sectional strategy. The metrics layer would support
a portfolio — ``_portfolio_period_returns`` groups decisions by ``decision_at`` and averages across
them — but nothing can currently build a multi-instrument dataset to feed it. Closing that gap means
changing ``src/quant_system/modeling/**``, which this script does not own.

Two properties keep the sweep honest:

* **One campaign, one counter.** Every trial is written to the same ``EvidenceStore``, so the store
  assigns consecutive multiplicity ordinals across the whole sweep. Searching fifty names cannot be
  disguised as fifty independent first attempts.
* **One pre-declared rule.** Every instrument uses ``--score-threshold auto`` — the training
  partition's own base rate. No name gets a hand-picked threshold.

At the end, ``campaign_deflated_sharpe_ratios`` re-deflates every published model against the final
attempt count, because each model's stored figure was deflated against its own ordinal while the
campaign was still open and therefore flatters every early attempt.

Every result is reported, including failures. Reporting the best name out of fifty would be exactly
the selection bias the deflation exists to price in.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Final

sys.path.insert(0, str(Path(__file__).resolve().parent))

import run_governed_ridge_training as runner  # noqa: E402

from quant_system.data.market_data import (  # noqa: E402
    HistoricalAcquisitionFailure,
    HistoricalDailyRequest,
)
from quant_system.data.upstox import UpstoxClient  # noqa: E402
from quant_system.evidence import EvidenceStore, EvidenceStoreConfig  # noqa: E402
from quant_system.modeling import build_feature_dataset, build_label_dataset  # noqa: E402
from quant_system.modeling.errors import ModelingError  # noqa: E402
from quant_system.modeling.features import FEATURE_WARMUP_BARS_V1  # noqa: E402
from quant_system.modeling.persisted_trials import (  # noqa: E402
    campaign_deflated_sharpe_ratios,
)
from quant_system.modeling.training_evidence import run_persisted_ridge_trial  # noqa: E402

NSE_CA_URL: Final = (
    "https://www.nseindia.com/api/corporates-corporateActions"
    "?index=equities&symbol={symbol}&from_date={start}&to_date={end}"
)
USER_AGENT: Final = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)


@dataclass(frozen=True, slots=True)
class InstrumentResult:
    symbol: str
    instrument_key: str
    state: str
    detail: str
    trial_id: str | None = None
    sharpe: str | None = None
    accuracy: str | None = None
    trades: int | None = None
    published_dsr: str | None = None


def _read_universe(csv_path: Path) -> tuple[tuple[str, str], ...]:
    """Return (symbol, instrument_key) from the real NSE constituent CSV."""
    rows = list(csv.DictReader(csv_path.read_text(encoding="utf-8-sig").splitlines()))
    members = []
    for row in rows:
        symbol = (row.get("Symbol") or "").strip()
        isin = (row.get("ISIN Code") or "").strip()
        if symbol and isin:
            members.append((symbol, f"NSE_EQ|{isin}"))
    if not members:
        raise SystemExit(f"no constituents parsed from {csv_path}")
    return tuple(sorted(set(members)))


def _fetch_corporate_actions(symbol: str, start: date, end: date, out_dir: Path) -> Path | None:
    """Fetch one symbol's real NSE corporate-actions record. Returns None if unavailable."""
    out_dir.mkdir(parents=True, exist_ok=True)
    target = out_dir / f"nse-corporate-actions-{symbol}.json"
    if target.is_file() and target.stat().st_size > 0:
        return target
    url = NSE_CA_URL.format(
        symbol=symbol, start=start.strftime("%d-%m-%Y"), end=end.strftime("%d-%m-%Y")
    )
    request = urllib.request.Request(  # noqa: S310 - fixed https NSE host
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json, text/plain, */*",
            "Referer": "https://www.nseindia.com/companies-listing/corporate-filings-actions",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:  # noqa: S310
            body = response.read()
    except (urllib.error.URLError, TimeoutError, OSError):
        return None
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, list) or not parsed:
        # An empty record is a real answer, but it cannot anchor an authority hash that is
        # meaningfully about this instrument, so the instrument is skipped rather than bound
        # to an empty document.
        return None
    target.write_bytes(body)
    return target


def _namespace(args: argparse.Namespace, **overrides: Any) -> argparse.Namespace:
    merged = vars(args).copy()
    merged.update(overrides)
    return argparse.Namespace(**merged)


def _metrics_for(
    store_root: Path, trial_id: str
) -> tuple[str | None, str | None, int | None, str | None]:
    """Read the published RIDGE metrics for one trial straight from its manifest."""
    for manifest_path in (store_root / "models").glob("*/manifest.json"):
        metadata = json.loads(manifest_path.read_text(encoding="utf-8"))["metadata"]
        if metadata.get("trial_id") != trial_id:
            continue
        for report in metadata.get("strategy_reports", []):
            if report.get("strategy_id") == "RIDGE":
                metrics = report["metrics"]
                return (
                    metrics.get("sharpe_ratio"),
                    metrics.get("accuracy"),
                    metrics.get("trade_count"),
                    metadata.get("deflated_sharpe_ratio"),
                )
    return (None, None, None, None)


def _run_one(  # noqa: C901 - one linear pipeline; each failure mode is reported, not raised
    args: argparse.Namespace,
    *,
    symbol: str,
    instrument_key: str,
    ordinal: int,
    members: tuple[str, ...],
    client: UpstoxClient,
    store: EvidenceStore,
    repo_root: Path,
) -> InstrumentResult:
    trial_id = f"trial_uni_{ordinal:03d}"
    base = HistoricalDailyRequest(
        instrument_key=instrument_key,
        symbol=symbol,
        from_date=args.from_date,
        to_date=args.to_date,
        request_id=f"campaign-{symbol}",
    )
    discovery = client.acquire_historical_daily(base)
    if isinstance(discovery, HistoricalAcquisitionFailure):
        return InstrumentResult(symbol, instrument_key, "ACQUISITION_FAILED", discovery.code.value)
    if len(discovery.records) < FEATURE_WARMUP_BARS_V1:
        return InstrumentResult(
            symbol, instrument_key, "SKIPPED", f"only {len(discovery.records)} bars"
        )

    calendar = runner._calendar_from_acquisition(discovery, args.calendar_version)
    first = calendar.sessions[0].exchange_date
    last = calendar.sessions[-1].exchange_date

    document = _fetch_corporate_actions(symbol, first, last, args.corporate_actions_dir)
    if document is None:
        return InstrumentResult(
            symbol, instrument_key, "SKIPPED", "no NSE corporate-actions record available"
        )

    try:
        corporate = runner._corporate_action_authority(
            document=document,
            authority_id="nse-corporate-actions",
            source_url=args.corporate_authority_url,
            version=args.corporate_authority_version,
            first_session=first,
            last_session=last,
        )
        universe = runner._universe_snapshot(
            members=members,
            authority_id=args.universe_authority_id,
            source_url=args.universe_authority_url,
            version=args.universe_authority_version,
            first_session=first,
            last_session=last,
        )
    except runner.ConfigurationRefused as error:
        return InstrumentResult(symbol, instrument_key, "CONFIG_REFUSED", str(error))

    governed = client.acquire_historical_daily(
        HistoricalDailyRequest(
            instrument_key=instrument_key,
            symbol=symbol,
            from_date=first,
            to_date=last,
            request_id=f"campaign-{symbol}",
            calendar=calendar.reference,
            expected_sessions=tuple(s.exchange_date for s in calendar.sessions),
            corporate_action_authority=corporate,
            historical_universe_authority=universe.authority,
        )
    )
    if isinstance(governed, HistoricalAcquisitionFailure):
        return InstrumentResult(symbol, instrument_key, "ACQUISITION_FAILED", governed.code.value)

    try:
        features = build_feature_dataset(governed, args.candidate_id, calendar, universe)
        quotes = runner._round_trip_cost_quotes(
            features, governed, calendar, quantity=args.quantity
        )
        labels = build_label_dataset(features, governed, calendar, quotes)
        fold = runner._fold_from_tail(
            labels,
            calendar,
            validation_sessions=args.validation_sessions,
            embargo_sessions=args.embargo_sessions,
            fold_id=f"fold_uni_{ordinal:03d}",
        )
    except ModelingError as error:
        return InstrumentResult(symbol, instrument_key, "MODELING_REJECTED", error.code.value)
    except runner.ConfigurationRefused as error:
        return InstrumentResult(symbol, instrument_key, "CONFIG_REFUSED", str(error))

    try:
        start = runner._trial_start(
            _namespace(
                args, trial_id=trial_id, multiplicity_ordinal=ordinal, score_threshold="auto"
            ),
            features=features,
            labels=labels,
            fold=fold,
            repo_root=repo_root,
            created_at=datetime.now(UTC),
        )
    except (ModelingError, runner.ConfigurationRefused) as error:
        code = error.code.value if isinstance(error, ModelingError) else str(error)
        return InstrumentResult(symbol, instrument_key, "TRIAL_START_REJECTED", code)
    try:
        run_persisted_ridge_trial(
            store,
            operation_id=f"campaign-{symbol}-{ordinal:03d}",
            start=start,
            feature_dataset=features,
            label_dataset=labels,
            fold=fold,
            ended_at=datetime.now(UTC),
        )
    except ModelingError as error:
        return InstrumentResult(
            symbol, instrument_key, "TRIAL_FAILED", error.code.value, trial_id=trial_id
        )
    except Exception as error:  # noqa: BLE001 - see below; one instrument must not end the sweep
        # evaluate_governed_ridge_fold can raise a bare ValueError out of
        # analytics/multiplicity.py:_validate_dsr_inputs when a two-point return series lands on
        # the kurtosis >= skewness**2 + 1 boundary. That is an untyped escape from a governed
        # evaluation, not a ModelingError, so it is caught here and reported per instrument.
        # run_persisted_ridge_trial has already committed a terminal FAILED outcome by this
        # point, so the store stays consistent.
        return InstrumentResult(
            symbol,
            instrument_key,
            "TRIAL_CRASHED",
            f"{type(error).__name__}: {error}",
            trial_id=trial_id,
        )
    sharpe, accuracy, trades, dsr = _metrics_for(args.evidence_root, trial_id)
    return InstrumentResult(
        symbol,
        instrument_key,
        "SUCCEEDED",
        f"threshold={start.score_threshold}",
        trial_id=trial_id,
        sharpe=sharpe,
        accuracy=accuracy,
        trades=trades,
        published_dsr=dsr,
    )


def _report(results: list[InstrumentResult], store: EvidenceStore) -> None:
    print("\n" + "=" * 100, flush=True)
    print("UNIVERSE CAMPAIGN RESULTS - every instrument, not the best ones", flush=True)
    print("=" * 100, flush=True)
    succeeded = [r for r in results if r.state == "SUCCEEDED"]
    print(
        f"\n{'symbol':<14}{'state':<20}{'sharpe':>12}{'accuracy':>11}{'trades':>8}  detail",
        flush=True,
    )
    print("-" * 100, flush=True)
    for result in sorted(results, key=lambda r: r.symbol):
        sharpe = f"{Decimal(result.sharpe):+.4f}" if result.sharpe else ""
        accuracy = f"{Decimal(result.accuracy):.4f}" if result.accuracy else ""
        trades = str(result.trades) if result.trades is not None else ""
        print(
            f"{result.symbol:<14}{result.state:<20}{sharpe:>12}{accuracy:>11}{trades:>8}  "
            f"{result.detail[:38]}",
            flush=True,
        )

    print("\n" + "-" * 100, flush=True)
    states: dict[str, int] = {}
    for result in results:
        states[result.state] = states.get(result.state, 0) + 1
    print(f"state counts: {states}", flush=True)

    if succeeded:
        sharpes = [Decimal(r.sharpe) for r in succeeded if r.sharpe]
        positive = [s for s in sharpes if s > 0]
        print(f"\nnames with a published model : {len(succeeded)}", flush=True)
        print(f"  positive Sharpe            : {len(positive)} of {len(sharpes)}", flush=True)
        if sharpes:
            ordered = sorted(sharpes)
            print(f"  median Sharpe              : {ordered[len(ordered) // 2]:+.4f}", flush=True)
            print(f"  mean Sharpe                : {sum(sharpes) / len(sharpes):+.4f}", flush=True)
            print(
                f"  best / worst               : {max(sharpes):+.4f} / {min(sharpes):+.4f}",
                flush=True,
            )

    print("\nCampaign-wide re-deflation against the FINAL attempt count", flush=True)
    print(
        "(each stored figure was deflated against its own ordinal, so it flatters early attempts)",
        flush=True,
    )
    try:
        deflations = campaign_deflated_sharpe_ratios(store)
    except Exception as error:  # noqa: BLE001 - reporting must not mask the campaign result
        print(f"  re-deflation unavailable: {type(error).__name__}: {error}", flush=True)
        return
    for trial_id, value in sorted(deflations.items(), key=lambda kv: Decimal(kv[1]), reverse=True):
        print(f"  {trial_id:<24} campaign DSR = {Decimal(value):.6f}", flush=True)
    if deflations:
        best = max(Decimal(v) for v in deflations.values())
        print(f"\n  best campaign DSR = {best:.6f}; promotion gate requires >= 0.95", flush=True)
        print(
            f"  verdict: {'NONE PROMOTABLE' if best < Decimal('0.95') else 'REVIEW REQUIRED'}",
            flush=True,
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Governed ridge campaign across a real NSE universe."
    )
    parser.add_argument("--universe-csv", type=Path, required=True)
    parser.add_argument("--from-date", required=True, type=date.fromisoformat)
    parser.add_argument("--to-date", required=True, type=date.fromisoformat)
    parser.add_argument("--evidence-root", type=Path, required=True)
    parser.add_argument("--corporate-actions-dir", type=Path, default=Path("data/authorities"))
    parser.add_argument("--start-ordinal", type=int, required=True)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument(
        "--skip",
        type=int,
        default=0,
        help="skip the first N constituents, to resume a campaign without re-studying names",
    )
    parser.add_argument("--candidate-id", default="cand_ridge_v1")
    parser.add_argument("--l2-penalty", default="1")
    parser.add_argument("--validation-sessions", type=int, default=63)
    parser.add_argument("--embargo-sessions", type=int, default=2)
    parser.add_argument("--quantity", type=int, default=1)
    parser.add_argument("--calendar-version", default="v1")
    parser.add_argument("--corporate-authority-version", default="v1")
    parser.add_argument(
        "--corporate-authority-url",
        default="https://www.nseindia.com/companies-listing/corporate-filings-actions",
    )
    parser.add_argument("--universe-authority-id", default="nse-nifty50")
    parser.add_argument(
        "--universe-authority-url",
        default="https://www.nseindia.com/products-services/indices-nifty50-index",
    )
    parser.add_argument("--universe-authority-version", default="v1")
    parser.add_argument("--sleep-seconds", type=float, default=1.0)
    args = parser.parse_args(argv)

    repo_root = Path(__file__).resolve().parent.parent
    runner._load_credentials_from_env_file(repo_root / ".env")

    constituents = _read_universe(args.universe_csv)
    if args.skip:
        constituents = constituents[args.skip :]
    if args.limit:
        constituents = constituents[: args.limit]
    members = tuple(sorted(key for _, key in constituents))
    print(
        f"universe        : {len(constituents)} constituents from {args.universe_csv.name}",
        flush=True,
    )
    print(f"evidence store  : {args.evidence_root}", flush=True)
    print(f"start ordinal   : {args.start_ordinal}", flush=True)
    print(
        "threshold rule  : auto (training-partition base rate), uniform across all names\n",
        flush=True,
    )

    args.evidence_root.mkdir(parents=True, exist_ok=True)
    store = EvidenceStore(EvidenceStoreConfig(root=args.evidence_root))
    client = UpstoxClient()

    results: list[InstrumentResult] = []
    ordinal = args.start_ordinal
    for index, (symbol, key) in enumerate(constituents, start=1):
        result = _run_one(
            args,
            symbol=symbol,
            instrument_key=key,
            ordinal=ordinal,
            members=members,
            client=client,
            store=store,
            repo_root=repo_root,
        )
        results.append(result)
        marker = "ok " if result.state == "SUCCEEDED" else "-- "
        print(
            f"{marker}[{index:>3}/{len(constituents)}] {symbol:<14} {result.state:<20} "
            f"{result.detail[:44]}",
            flush=True,
        )
        if result.trial_id is not None:
            ordinal += 1
        time.sleep(args.sleep_seconds)

    _report(results, store)
    return 0


if __name__ == "__main__":
    sys.exit(main())
