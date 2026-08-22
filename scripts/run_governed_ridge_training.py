"""End-to-end governed ridge training runner over real Upstox market data.

The governed training stack in ``quant_system.modeling`` is complete but has no production
caller: ``run_persisted_ridge_trial`` is reachable only from tests. This module is that caller.
It chains, in order:

    real Upstox acquisition
      -> build_feature_dataset
      -> build_label_dataset      (costs from the dated NSE statutory rule engine)
      -> build_purged_fold
      -> run_persisted_ridge_trial
      -> EvidenceStore

Three properties are deliberate and load-bearing:

1. **There is no synthetic path.** This module imports no data generator. If the provider refuses,
   the run stops at the typed failure and nothing downstream executes. A training number that this
   runner did not obtain from the provider cannot be produced by it.

2. **Nothing is fabricated to satisfy a validator.** The corporate-action authority hash is the
   SHA-256 of an operator-supplied document's real bytes. Absent that document the run is refused
   (exit 2) rather than bound to an authority that does not exist.

3. **Configuration needed only downstream is validated only downstream.** Acquisition is attempted
   before the corporate-action document is required, so the provider's real outcome is always
   observed and reported rather than pre-empted by a local configuration error.

Known limitation, stated rather than resolved: with no ``--calendar-file``, the session calendar is
derived from the exchange dates the provider actually returned. Those dates are real, but a
provider that silently omits a trading day yields a calendar agreeing with its own gap, so
completeness is not self-proving. Supply an independent NSE calendar to close this.

Exit codes:
    0  every stage completed and trial evidence was published
    2  configuration refused (missing credential or authority document)
    3  real acquisition failed; the typed provider failure is printed verbatim
    4  a governed modeling rule rejected the real data
    5  evidence publication failed
"""

from __future__ import annotations

import argparse
import hashlib
import os
import platform
import subprocess
import sys
from collections.abc import Sequence
from datetime import UTC, date, datetime, time, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Final

from quant_system.analytics.nse_rules import CostBreakdown, MarketSegment, NSERuleEngine
from quant_system.core.domain import Side
from quant_system.data.market_data import (
    AuthorityReference,
    HistoricalAcquisition,
    HistoricalAcquisitionFailure,
    HistoricalDailyRequest,
    PointInTimeBar,
)
from quant_system.data.market_data_evidence import canonical_sha256
from quant_system.data.upstox import UpstoxClient
from quant_system.evidence import EvidenceStore, EvidenceStoreConfig
from quant_system.evidence.errors import EvidenceError
from quant_system.modeling import (
    ExchangeSessionV1,
    FeatureDatasetV1,
    HistoricalUniverseSnapshotV1,
    LabelDatasetV1,
    MoneyV1,
    PartitionedFoldV1,
    RidgeTrialStartV1,
    RoundTripCostQuoteV1,
    SessionCalendarV1,
    build_feature_dataset,
    build_label_dataset,
    build_purged_fold,
    fold_spec_hash,
    run_persisted_ridge_trial,
)
from quant_system.modeling.errors import ModelingError
from quant_system.modeling.features import FEATURE_WARMUP_BARS_V1

EXIT_OK: Final = 0
EXIT_CONFIG_REFUSED: Final = 2
EXIT_ACQUISITION_FAILED: Final = 3
EXIT_MODELING_REJECTED: Final = 4
EXIT_EVIDENCE_FAILED: Final = 5

IST: Final = timezone(timedelta(hours=5, minutes=30), name="Asia/Kolkata")
NSE_OPEN: Final = time(9, 15)
NSE_CLOSE: Final = time(15, 30)
PROVIDER_DERIVED_CALENDAR_ID: Final = "nse-cash-provider-derived"
EQUITY_SEGMENT: Final = MarketSegment.EQUITY_DELIVERY

# Cost components carried onto every RoundTripCostQuoteV1, summed across both legs.
COST_COMPONENTS: Final = (
    "brokerage",
    "exchange_turnover",
    "gst",
    "sebi_charges",
    "stamp_duty",
    "stt",
)


class ConfigurationRefused(Exception):
    """Raised when the run cannot proceed without inventing evidence."""


def _log(stage: str, message: str) -> None:
    print(f"{stage:<38}: {message}", flush=True)


# --------------------------------------------------------------------------------------
# Stage 1 and 3: real acquisition
# --------------------------------------------------------------------------------------


def _print_acquisition_failure(stage: str, failure: HistoricalAcquisitionFailure) -> None:
    """Print the provider's typed failure verbatim. No interpretation, no softening."""
    print("", flush=True)
    print("ACQUISITION FAILED - no synthetic fallback exists in this runner.", flush=True)
    print(f"  stage                 : {stage}", flush=True)
    print(f"  code                  : {failure.code.value}", flush=True)
    print(f"  retryable             : {failure.retryable}", flush=True)
    print(f"  retry_after_seconds   : {failure.retry_after_seconds}", flush=True)
    print(f"  provider_status       : {failure.provider_status}", flush=True)
    print(f"  provider_code         : {failure.provider_code}", flush=True)
    print(f"  recovery_action       : {failure.recovery_action}", flush=True)
    print(f"  detected_at           : {failure.detected_at.isoformat()}", flush=True)
    for finding in failure.quality_findings:
        print(
            f"  quality_finding       : {finding.code.value} "
            f"severity={finding.severity.value} count={finding.count}",
            flush=True,
        )
    print("", flush=True)
    print(
        "STOPPING. No feature dataset, no labels, no fold, no trial, no evidence was written.",
        flush=True,
    )


def _acquire(
    client: UpstoxClient, request: HistoricalDailyRequest, stage: str
) -> HistoricalAcquisition:
    """Acquire real history, or exit with the provider's typed failure."""
    outcome = client.acquire_historical_daily(request)
    if isinstance(outcome, HistoricalAcquisitionFailure):
        _print_acquisition_failure(stage, outcome)
        raise SystemExit(EXIT_ACQUISITION_FAILED)
    return outcome


# --------------------------------------------------------------------------------------
# Stage 2: session calendar
# --------------------------------------------------------------------------------------


def _sessions_from_dates(exchange_dates: Sequence[date]) -> tuple[ExchangeSessionV1, ...]:
    return tuple(
        ExchangeSessionV1(
            exchange_date=exchange_date,
            open_at=datetime.combine(exchange_date, NSE_OPEN, IST),
            close_at=datetime.combine(exchange_date, NSE_CLOSE, IST),
        )
        for exchange_date in sorted(set(exchange_dates))
    )


def _calendar_from_file(path: Path, version: str) -> SessionCalendarV1:
    """Build the calendar from an independent NSE session list, one ISO date per line."""
    text = path.read_text(encoding="utf-8")
    exchange_dates = [
        date.fromisoformat(line.strip())
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if not exchange_dates:
        raise ConfigurationRefused(f"calendar file {path} lists no session dates")
    return SessionCalendarV1.create("nse-cash", version, _sessions_from_dates(exchange_dates))


def _calendar_from_acquisition(
    acquisition: HistoricalAcquisition, version: str
) -> SessionCalendarV1:
    """Derive the calendar from the exchange dates the provider actually returned."""
    exchange_dates = [record.exchange_date for record in acquisition.records]
    if not exchange_dates:
        raise ConfigurationRefused("provider returned no exchange dates to derive a calendar from")
    return SessionCalendarV1.create(
        PROVIDER_DERIVED_CALENDAR_ID,
        version,
        _sessions_from_dates(exchange_dates),
    )


# --------------------------------------------------------------------------------------
# Authorities: real documents only
# --------------------------------------------------------------------------------------


def _file_content_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _corporate_action_authority(
    *,
    document: Path | None,
    authority_id: str,
    source_url: str,
    version: str,
    first_session: date,
    last_session: date,
) -> AuthorityReference:
    """Bind a corporate-action authority to the real bytes of an operator-supplied document."""
    if document is None:
        raise ConfigurationRefused(
            "--corporate-actions-file is required. The governed feature builder binds every row "
            "to a corporate-action authority hash, and this runner will not emit a placeholder "
            "digest for a document that does not exist. Supply the real NSE corporate-actions "
            "file covering "
            f"{first_session.isoformat()}..{last_session.isoformat()} and re-run."
        )
    if not document.is_file():
        raise ConfigurationRefused(f"corporate-actions file not found: {document}")
    return AuthorityReference(
        authority_id=authority_id,
        source_url=source_url,
        publication_date=first_session - timedelta(days=1),
        effective_from=first_session,
        effective_to=last_session,
        version=version,
        content_hash=_file_content_hash(document),
    )


def _universe_snapshot(
    *,
    members: tuple[str, ...],
    authority_id: str,
    source_url: str,
    version: str,
    first_session: date,
    last_session: date,
) -> HistoricalUniverseSnapshotV1:
    """Content-bind the tradable set. The hash is derived from the members, never asserted."""
    return HistoricalUniverseSnapshotV1.create(
        authority_id=authority_id,
        source_url=source_url,
        publication_date=first_session - timedelta(days=1),
        effective_from=first_session,
        effective_to=last_session,
        version=version,
        provider_instrument_ids=tuple(sorted(set(members))),
    )


def _universe_members(universe_file: Path | None, instrument_key: str) -> tuple[str, ...]:
    if universe_file is None:
        return (instrument_key,)
    if not universe_file.is_file():
        raise ConfigurationRefused(f"universe file not found: {universe_file}")
    members = tuple(
        line.strip()
        for line in universe_file.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )
    if not members:
        raise ConfigurationRefused(f"universe file {universe_file} lists no instruments")
    return members


# --------------------------------------------------------------------------------------
# Stage 5 input: real statutory round-trip costs
# --------------------------------------------------------------------------------------


def _leg_costs(
    engine: NSERuleEngine, *, side: Side, quantity: int, price: Decimal, trade_date: date
) -> CostBreakdown:
    return engine.calculate_costs(
        segment=EQUITY_SEGMENT,
        side=side,
        quantity=quantity,
        price=price,
        trade_date=trade_date,
    )


def _component_amounts(entry: CostBreakdown, exit_leg: CostBreakdown) -> dict[str, MoneyV1]:
    totals = {
        "brokerage": entry.brokerage + exit_leg.brokerage,
        "exchange_turnover": entry.exchange_turnover + exit_leg.exchange_turnover,
        "gst": entry.gst + exit_leg.gst,
        "sebi_charges": entry.sebi_charges + exit_leg.sebi_charges,
        "stamp_duty": entry.stamp_duty + exit_leg.stamp_duty,
        "stt": entry.stt + exit_leg.stt,
    }
    return {name: MoneyV1(totals[name], "INR") for name in COST_COMPONENTS}


def _rule_set_hash(entry: CostBreakdown, exit_leg: CostBreakdown) -> str:
    """Hash exactly the dated rules the engine applied to these two legs."""
    return canonical_sha256(
        {
            "entry_rule_hashes": dict(entry.applied_rule_hashes),
            "entry_rule_ids": dict(entry.applied_rule_ids),
            "exit_rule_hashes": dict(exit_leg.applied_rule_hashes),
            "exit_rule_ids": dict(exit_leg.applied_rule_ids),
        }
    )


def _rule_ids(entry: CostBreakdown, exit_leg: CostBreakdown) -> tuple[str, ...]:
    return tuple(sorted({*entry.applied_rule_ids.values(), *exit_leg.applied_rule_ids.values()}))


def _cost_quote_for_legs(
    engine: NSERuleEngine,
    *,
    entry_bar: PointInTimeBar,
    exit_bar: PointInTimeBar,
    entry_at: datetime,
    exit_at: datetime,
    quantity: int,
) -> RoundTripCostQuoteV1:
    entry_costs = _leg_costs(
        engine,
        side=Side.BUY,
        quantity=quantity,
        price=entry_bar.open,
        trade_date=entry_bar.exchange_date,
    )
    exit_costs = _leg_costs(
        engine,
        side=Side.SELL,
        quantity=quantity,
        price=exit_bar.open,
        trade_date=exit_bar.exchange_date,
    )
    return RoundTripCostQuoteV1(
        provider_instrument_id=entry_bar.provider_instrument_id,
        symbol=entry_bar.symbol,
        entry_at=entry_at,
        exit_at=exit_at,
        entry_price=entry_bar.open,
        exit_price=exit_bar.open,
        quantity=quantity,
        component_costs=_component_amounts(entry_costs, exit_costs),
        cost_rule_ids=_rule_ids(entry_costs, exit_costs),
        cost_rule_set_hash=_rule_set_hash(entry_costs, exit_costs),
        execution_contract_version="next-open-v1",
    )


def _round_trip_cost_quotes(
    features: FeatureDatasetV1,
    acquisition: HistoricalAcquisition,
    calendar: SessionCalendarV1,
    *,
    quantity: int,
) -> tuple[RoundTripCostQuoteV1, ...]:
    """One quote per feature row that matures, matching the label builder's rule exactly.

    ``build_label_dataset`` rejects any quote it does not consume, so this mirrors the maturation
    test in ``labels._build_label``: skip rows without two later sessions, and skip rows whose exit
    session falls beyond the acquisition's received range.
    """
    engine = NSERuleEngine()
    bars_by_date = {record.exchange_date: record for record in acquisition.records}
    received_end = acquisition.manifest.received_end
    quotes: list[RoundTripCostQuoteV1] = []
    for feature_row in features.rows:
        ordinal = calendar.ordinal_for_close(feature_row.decision_at)
        if ordinal is None or ordinal + 2 >= len(calendar.sessions):
            continue
        entry_session = calendar.sessions[ordinal + 1]
        exit_session = calendar.sessions[ordinal + 2]
        if exit_session.exchange_date > received_end:
            continue
        entry_bar = bars_by_date.get(entry_session.exchange_date)
        exit_bar = bars_by_date.get(exit_session.exchange_date)
        if entry_bar is None or exit_bar is None:
            # The label builder raises ELIGIBLE_OPEN_MISSING here; let it own that diagnosis.
            continue
        quotes.append(
            _cost_quote_for_legs(
                engine,
                entry_bar=entry_bar,
                exit_bar=exit_bar,
                entry_at=entry_session.open_at,
                exit_at=exit_session.open_at,
                quantity=quantity,
            )
        )
    return tuple(quotes)


# --------------------------------------------------------------------------------------
# Stage 7 input: reproducibility identity
# --------------------------------------------------------------------------------------


def _source_revision(repo_root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    revision = result.stdout.strip()
    if result.returncode != 0 or not revision:
        raise ConfigurationRefused(
            "cannot resolve the source revision with 'git rev-parse HEAD'; a governed trial must "
            "record the exact revision that produced it"
        )
    return revision


def _environment_lock_hash(repo_root: Path) -> str:
    lock = repo_root / "uv.lock"
    if not lock.is_file():
        raise ConfigurationRefused(f"uv.lock not found at {lock}; the environment cannot be pinned")
    return _file_content_hash(lock)


def _architecture() -> str:
    return (
        f"{platform.system().lower()}-{platform.machine().lower()}"
        f"-cpython-{platform.python_version()}"
    )[:128]


# --------------------------------------------------------------------------------------
# Stage assembly
# --------------------------------------------------------------------------------------


def _governed_request(
    args: argparse.Namespace,
    *,
    calendar: SessionCalendarV1,
    corporate: AuthorityReference,
    universe: HistoricalUniverseSnapshotV1,
) -> HistoricalDailyRequest:
    return HistoricalDailyRequest(
        instrument_key=args.instrument_key,
        symbol=args.symbol,
        from_date=args.from_date,
        to_date=args.to_date,
        request_id=args.request_id,
        calendar=calendar.reference,
        expected_sessions=tuple(session.exchange_date for session in calendar.sessions),
        corporate_action_authority=corporate,
        historical_universe_authority=universe.authority,
    )


def _fold_from_tail(
    labels: LabelDatasetV1,
    calendar: SessionCalendarV1,
    *,
    validation_sessions: int,
    embargo_sessions: int,
    fold_id: str,
) -> PartitionedFoldV1:
    """Hold out the most recent labelled sessions as the validation block."""
    label_closes = sorted({row.decision_at for row in labels.rows})
    if len(label_closes) <= validation_sessions:
        raise ConfigurationRefused(
            f"only {len(label_closes)} labelled sessions exist; "
            f"--validation-sessions {validation_sessions} would leave no training data"
        )
    validation_closes = label_closes[-validation_sessions:]
    return build_purged_fold(
        labels.rows,
        fold_id=fold_id,
        ordinal=1,
        validation_start=validation_closes[0],
        validation_end=validation_closes[-1],
        calendar=calendar,
        embargo_sessions=embargo_sessions,
    )


def _trial_start(
    args: argparse.Namespace,
    *,
    features: FeatureDatasetV1,
    labels: LabelDatasetV1,
    fold: PartitionedFoldV1,
    repo_root: Path,
    created_at: datetime,
) -> RidgeTrialStartV1:
    return RidgeTrialStartV1(
        trial_id=args.trial_id,
        candidate_id=features.candidate_id,
        created_at=created_at,
        dataset_id=labels.dataset_id,
        dataset_hash=labels.dataset_hash,
        universe_policy_hash=features.universe_authority_hash,
        l2_penalty=args.l2_penalty,
        score_threshold=args.score_threshold,
        numpy_seed=0,
        fold_spec_hashes=(fold_spec_hash(fold),),
        source_revision=_source_revision(repo_root),
        environment_lock_hash=_environment_lock_hash(repo_root),
        architecture=_architecture(),
        multiplicity_ordinal=args.multiplicity_ordinal,
    )


def _report_success(result: object, evidence_root: Path) -> None:
    print("", flush=True)
    print("TRIAL PUBLISHED FROM REAL MARKET DATA", flush=True)
    print(f"  evidence root         : {evidence_root}", flush=True)
    print(f"  result                : {result!r}", flush=True)
    print("", flush=True)
    print(
        "This is a research result, not a certification. It has had no Red Team pass and no "
        "independent Verifier pass.",
        flush=True,
    )


def _run(args: argparse.Namespace) -> int:
    repo_root = Path(__file__).resolve().parent.parent
    client = UpstoxClient()

    # ---- Stage 1: real acquisition (discovery) --------------------------------------
    _log(
        "[1/7] real acquisition (discovery)",
        f"{args.instrument_key} {args.symbol} {args.from_date}..{args.to_date}",
    )
    discovery = _acquire(
        client,
        HistoricalDailyRequest(
            instrument_key=args.instrument_key,
            symbol=args.symbol,
            from_date=args.from_date,
            to_date=args.to_date,
            request_id=args.request_id,
        ),
        "discovery",
    )
    _log("[1/7] provider returned", f"{len(discovery.records)} real daily bars")

    # ---- Stage 2: session calendar ---------------------------------------------------
    if args.calendar_file is not None:
        calendar = _calendar_from_file(args.calendar_file, args.calendar_version)
        _log(
            "[2/7] calendar",
            f"independent, {len(calendar.sessions)} sessions from {args.calendar_file}",
        )
    else:
        calendar = _calendar_from_acquisition(discovery, args.calendar_version)
        _log(
            "[2/7] calendar",
            f"PROVIDER-DERIVED, {len(calendar.sessions)} sessions (see module docstring)",
        )
    first_session = calendar.sessions[0].exchange_date
    last_session = calendar.sessions[-1].exchange_date

    # ---- Stage 3: real acquisition (governed) ----------------------------------------
    corporate = _corporate_action_authority(
        document=args.corporate_actions_file,
        authority_id=args.corporate_authority_id,
        source_url=args.corporate_authority_url,
        version=args.corporate_authority_version,
        first_session=first_session,
        last_session=last_session,
    )
    universe = _universe_snapshot(
        members=_universe_members(args.universe_file, args.instrument_key),
        authority_id=args.universe_authority_id,
        source_url=args.universe_authority_url,
        version=args.universe_authority_version,
        first_session=first_session,
        last_session=last_session,
    )
    acquisition = _acquire(
        client,
        _governed_request(args, calendar=calendar, corporate=corporate, universe=universe),
        "governed",
    )
    _log(
        "[3/7] governed acquisition",
        f"{len(acquisition.records)} bars, status={acquisition.manifest.status.value}, "
        f"source={acquisition.manifest.source_status.value}",
    )

    # ---- Stage 4: features -----------------------------------------------------------
    if len(acquisition.records) < FEATURE_WARMUP_BARS_V1:
        raise ConfigurationRefused(
            f"the feature schema needs at least {FEATURE_WARMUP_BARS_V1} bars; "
            f"the provider returned {len(acquisition.records)}"
        )
    features = build_feature_dataset(acquisition, args.candidate_id, calendar, universe)
    _log("[4/7] feature dataset", f"{len(features.rows)} rows, id={features.dataset_id}")

    # ---- Stage 5: labels -------------------------------------------------------------
    quotes = _round_trip_cost_quotes(features, acquisition, calendar, quantity=args.quantity)
    labels = build_label_dataset(features, acquisition, calendar, quotes)
    _log("[5/7] label dataset", f"{len(labels.rows)} rows, id={labels.dataset_id}")

    # ---- Stage 6: purged fold --------------------------------------------------------
    fold = _fold_from_tail(
        labels,
        calendar,
        validation_sessions=args.validation_sessions,
        embargo_sessions=args.embargo_sessions,
        fold_id=args.fold_id,
    )
    _log(
        "[6/7] purged fold",
        f"train={len(fold.train_rows)} validation={len(fold.validation_rows)} "
        f"embargo={args.embargo_sessions}",
    )

    # ---- Stage 7: persisted trial ----------------------------------------------------
    args.evidence_root.mkdir(parents=True, exist_ok=True)
    store = EvidenceStore(EvidenceStoreConfig(root=args.evidence_root))
    created_at = datetime.now(UTC)
    start = _trial_start(
        args,
        features=features,
        labels=labels,
        fold=fold,
        repo_root=repo_root,
        created_at=created_at,
    )
    result = run_persisted_ridge_trial(
        store,
        operation_id=args.operation_id,
        start=start,
        feature_dataset=features,
        label_dataset=labels,
        fold=fold,
        ended_at=datetime.now(UTC),
    )
    _log("[7/7] persisted trial", f"trial_id={start.trial_id} state={result.outcome.state.value}")
    _report_success(result.outcome, args.evidence_root)
    return EXIT_OK


def _add_authority_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--corporate-actions-file",
        type=Path,
        default=None,
        help="real NSE corporate-actions document; its bytes are hashed as the authority",
    )
    parser.add_argument("--corporate-authority-id", default="nse-corporate-actions")
    parser.add_argument(
        "--corporate-authority-url",
        default="https://www.nseindia.com/companies-listing/corporate-filings-actions",
    )
    parser.add_argument("--corporate-authority-version", default="v1")
    parser.add_argument(
        "--universe-file",
        type=Path,
        default=None,
        help="instrument keys, one per line; defaults to the single requested instrument",
    )
    parser.add_argument("--universe-authority-id", default="nse-equity-universe")
    parser.add_argument(
        "--universe-authority-url",
        default="https://www.nseindia.com/market-data/securities-available-for-trading",
    )
    parser.add_argument("--universe-authority-version", default="v1")
    parser.add_argument(
        "--calendar-file",
        type=Path,
        default=None,
        help="independent NSE session dates, one ISO date per line; omit to derive from provider",
    )
    parser.add_argument("--calendar-version", default="v1")


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="run_governed_ridge_training",
        description="Run one governed ridge trial end to end over real Upstox data.",
    )
    parser.add_argument("--symbol", required=True, help="NSE symbol, e.g. INFY")
    parser.add_argument(
        "--instrument-key",
        required=True,
        help="Upstox NSE cash instrument key, e.g. 'NSE_EQ|INE009A01021'",
    )
    parser.add_argument("--from-date", required=True, type=date.fromisoformat)
    parser.add_argument("--to-date", required=True, type=date.fromisoformat)
    parser.add_argument("--evidence-root", type=Path, default=Path("data/evidence/real-training"))
    parser.add_argument("--candidate-id", default="cand_ridge_v1")
    parser.add_argument("--trial-id", default="trial_real_001")
    parser.add_argument("--fold-id", default="fold_real_001")
    parser.add_argument("--operation-id", default="real-governed-ridge-training")
    parser.add_argument("--request-id", default="real-governed-ridge-training")
    parser.add_argument("--l2-penalty", default="1")
    parser.add_argument("--score-threshold", default="0")
    parser.add_argument("--multiplicity-ordinal", type=int, default=1)
    parser.add_argument("--validation-sessions", type=int, default=8)
    parser.add_argument("--embargo-sessions", type=int, default=2)
    parser.add_argument("--quantity", type=int, default=1)
    parser.add_argument(
        "--env-file",
        type=Path,
        default=None,
        help="dotenv file to read UPSTOX_* credentials from; defaults to <repo root>/.env",
    )
    _add_authority_arguments(parser)
    return parser.parse_args(argv)


def _load_credentials_from_env_file(env_file: Path) -> tuple[str, ...]:
    """Load only the Upstox keys from a dotenv file into the process environment.

    This project depends on no dotenv library, and adding one would touch ``pyproject.toml`` and
    ``uv.lock`` — shared files this runner does not own — so the parse is done here.

    Two deliberate restrictions:

    * **Only ``UPSTOX_*`` keys are read.** A real ``.env`` also carries unrelated provider keys.
      This runner spawns ``git`` as a subprocess, which inherits the environment, so loading
      secrets it has no use for would widen their exposure for no benefit.
    * **An already-set variable always wins.** A value exported in the shell is never overwritten
      by the file, so the environment stays the authority and a stale file cannot silently
      shadow it.

    Returns the names loaded. Never returns, logs, or prints a value.
    """
    wanted = ("UPSTOX_ACCESS_TOKEN", "UPSTOX_API_KEY")
    if not env_file.is_file():
        return ()
    loaded: list[str] = []
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.removeprefix("export ").partition("=")
        name = name.strip()
        if name not in wanted or os.getenv(name):
            continue
        os.environ[name] = value.strip().strip("\"'")
        loaded.append(name)
    return tuple(loaded)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    env_file = args.env_file or Path(__file__).resolve().parent.parent / ".env"
    loaded = _load_credentials_from_env_file(env_file)
    if loaded:
        _log("[0/7] credential", f"loaded {', '.join(loaded)} from {env_file.name}")
    if not os.getenv("UPSTOX_ACCESS_TOKEN"):
        # Not a refusal: the provider must still be asked, so that its typed answer is what
        # gets recorded rather than this runner's guess about the answer.
        _log(
            "[0/7] credential", "UPSTOX_ACCESS_TOKEN is not set; the provider will be asked anyway"
        )
    try:
        return _run(args)
    except ConfigurationRefused as error:
        print("", flush=True)
        print(f"CONFIGURATION REFUSED: {error}", flush=True)
        return EXIT_CONFIG_REFUSED
    except ModelingError as error:
        print("", flush=True)
        print("GOVERNED MODELING REJECTED THE REAL DATA", flush=True)
        print(f"  code                  : {error.code.value}", flush=True)
        print(f"  detail                : {error}", flush=True)
        return EXIT_MODELING_REJECTED
    except EvidenceError as error:
        print("", flush=True)
        print("EVIDENCE PUBLICATION FAILED", flush=True)
        print(f"  detail                : {type(error).__name__}: {error}", flush=True)
        return EXIT_EVIDENCE_FAILED


if __name__ == "__main__":
    sys.exit(main())
