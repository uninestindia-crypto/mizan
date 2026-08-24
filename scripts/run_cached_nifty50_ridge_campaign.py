"""Run ten-year real-data ridge studies with immutable local acquisition reuse.

Both discovery and authority-bound Upstox acquisitions are committed to an ``EvidenceStore``
before feature construction. Cache hits are verified and rebuilt into governed domain objects;
corrupt cache content stops closed. The static 2026 NIFTY 50 universe means these are current-member
single-name studies, not a point-in-time historical index portfolio. Pre-2020 costs use visibly
identified research proxies and impose a ``RESEARCH_ONLY`` ceiling.
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import run_governed_ridge_training as runner  # noqa: E402
import run_universe_ridge_campaign as universe_runner  # noqa: E402
from cached_nifty50_catalog import VerifiedAcquisitionCatalog  # noqa: E402
from cached_nifty50_costs import (  # noqa: E402
    RESEARCH_COST_POLICY_HASH,
    round_trip_cost_quotes,
)
from cached_nifty50_costs import (
    research_cost_engine as research_cost_engine,
)
from cached_nifty50_evidence import (  # noqa: E402
    CachedAcquisitionQuery,
)
from cached_nifty50_evidence import (
    acquire_or_load as acquire_or_load,
)
from cached_nifty50_evidence import (
    load_cached_acquisition as load_cached_acquisition,
)
from cached_nifty50_evidence import (
    persist_verified_acquisition as persist_verified_acquisition,
)
from cached_nifty50_io import (  # noqa: E402
    CampaignOutput,
    CampaignProgress,
    UniverseSelection,
    fetch_or_load_corporate_actions,
    parse_args,
    persist_runtime_authorities,
    print_campaign_header,
    read_universe,
    record_result,
    select_constituents,
    stop_for_integrity,
)

from quant_system.data.market_data import (  # noqa: E402
    AuthorityReference,
    HistoricalAcquisition,
    HistoricalAcquisitionFailure,
    HistoricalDailyRequest,
)
from quant_system.data.upstox import UpstoxClient  # noqa: E402
from quant_system.evidence import (  # noqa: E402
    EvidenceIntegrityError,
    EvidenceStore,
    EvidenceStoreConfig,
)
from quant_system.modeling import (  # noqa: E402
    FeatureDatasetV1,
    HistoricalUniverseSnapshotV1,
    LabelDatasetV1,
    PartitionedFoldV1,
    SessionCalendarV1,
    build_feature_dataset,
    build_label_dataset,
)
from quant_system.modeling.errors import ModelingError  # noqa: E402
from quant_system.modeling.features import FEATURE_WARMUP_BARS_V1  # noqa: E402
from quant_system.modeling.training_evidence import (  # noqa: E402
    run_persisted_ridge_trial,
)
from quant_system.modeling.trials import RidgeTrialStartV1  # noqa: E402


@dataclass(frozen=True, slots=True)
class StudyContext:
    args: argparse.Namespace
    symbol: str
    instrument_key: str
    ordinal: int
    authority_members: tuple[str, ...]
    client: UpstoxClient
    cache_catalog: VerifiedAcquisitionCatalog
    model_store: EvidenceStore
    repo_root: Path


@dataclass(frozen=True, slots=True)
class GovernanceInputs:
    calendar: SessionCalendarV1
    corporate: AuthorityReference
    universe: HistoricalUniverseSnapshotV1
    corporate_cache_state: str


@dataclass(frozen=True, slots=True)
class ModelInputs:
    features: FeatureDatasetV1
    labels: LabelDatasetV1
    fold: PartitionedFoldV1


@dataclass(frozen=True, slots=True)
class CampaignContext:
    args: argparse.Namespace
    repo_root: Path
    constituents: tuple[tuple[str, str], ...]
    selection: UniverseSelection
    cache_catalog: VerifiedAcquisitionCatalog
    model_store: EvidenceStore
    client: UpstoxClient
    output: CampaignOutput


def _instrument_result(
    context: StudyContext,
    state: str,
    detail: str,
    *,
    trial_id: str | None = None,
) -> universe_runner.InstrumentResult:
    return universe_runner.InstrumentResult(
        context.symbol,
        context.instrument_key,
        state,
        detail,
        trial_id=trial_id,
    )


def _typed_failure(stage: str, failure: HistoricalAcquisitionFailure) -> None:
    print(f"TYPED_ACQUISITION_FAILURE[{stage}]={failure!r}", flush=True)


def _acquire_discovery(
    context: StudyContext,
) -> tuple[HistoricalAcquisition | None, str, universe_runner.InstrumentResult | None]:
    args = context.args
    request = HistoricalDailyRequest(
        instrument_key=context.instrument_key,
        symbol=context.symbol,
        from_date=args.from_date,
        to_date=args.to_date,
        request_id=f"campaign-discovery-{context.symbol}",
    )
    outcome, cache_state = context.cache_catalog.acquire_or_load(
        CachedAcquisitionQuery.from_request(request),
        lambda: context.client.acquire_historical_daily(request),
        operation_id=f"cache-discovery-{context.symbol.lower()}",
    )
    if isinstance(outcome, HistoricalAcquisitionFailure):
        _typed_failure("discovery", outcome)
        return (
            None,
            cache_state,
            _instrument_result(context, "ACQUISITION_FAILED", f"discovery:{outcome.code.value}"),
        )
    if len(outcome.records) < FEATURE_WARMUP_BARS_V1:
        return (
            None,
            cache_state,
            _instrument_result(context, "SKIPPED", f"only {len(outcome.records)} bars"),
        )
    return outcome, cache_state, None


def _build_governance(
    context: StudyContext,
    discovery: HistoricalAcquisition,
) -> GovernanceInputs:
    args = context.args
    calendar = runner._calendar_from_acquisition(discovery, args.calendar_version)
    first = calendar.sessions[0].exchange_date
    last = calendar.sessions[-1].exchange_date
    document, ca_state = fetch_or_load_corporate_actions(
        context.symbol, first, last, args.corporate_actions_dir
    )
    corporate = runner._corporate_action_authority(
        document=document,
        authority_id="nse-corporate-actions",
        source_url=args.corporate_authority_url,
        version=args.corporate_authority_version,
        first_session=first,
        last_session=last,
    )
    universe = runner._universe_snapshot(
        members=context.authority_members,
        authority_id=args.universe_authority_id,
        source_url=args.universe_authority_url,
        version=args.universe_authority_version,
        first_session=first,
        last_session=last,
    )
    return GovernanceInputs(calendar, corporate, universe, ca_state)


def _governed_request(
    context: StudyContext, governance: GovernanceInputs
) -> HistoricalDailyRequest:
    calendar = governance.calendar
    return HistoricalDailyRequest(
        instrument_key=context.instrument_key,
        symbol=context.symbol,
        from_date=calendar.sessions[0].exchange_date,
        to_date=calendar.sessions[-1].exchange_date,
        request_id=f"campaign-governed-{context.symbol}",
        calendar=calendar.reference,
        expected_sessions=tuple(session.exchange_date for session in calendar.sessions),
        corporate_action_authority=governance.corporate,
        historical_universe_authority=governance.universe.authority,
    )


def _acquire_governed(
    context: StudyContext,
    governance: GovernanceInputs,
) -> tuple[HistoricalAcquisition | None, str, universe_runner.InstrumentResult | None]:
    request = _governed_request(context, governance)
    outcome, cache_state = context.cache_catalog.acquire_or_load(
        CachedAcquisitionQuery.from_request(request),
        lambda: context.client.acquire_historical_daily(request),
        operation_id=f"cache-governed-{context.symbol.lower()}",
    )
    if isinstance(outcome, HistoricalAcquisitionFailure):
        _typed_failure("governed", outcome)
        result = _instrument_result(context, "ACQUISITION_FAILED", f"governed:{outcome.code.value}")
        return None, cache_state, result
    return outcome, cache_state, None


def _prepare_model_inputs(
    context: StudyContext,
    governance: GovernanceInputs,
    acquisition: HistoricalAcquisition,
) -> ModelInputs:
    args = context.args
    features = build_feature_dataset(
        acquisition,
        args.candidate_id,
        governance.calendar,
        governance.universe,
    )
    quotes = round_trip_cost_quotes(
        features,
        acquisition,
        governance.calendar,
        quantity=args.quantity,
    )
    labels = build_label_dataset(features, acquisition, governance.calendar, quotes)
    fold = runner._fold_from_tail(
        labels,
        governance.calendar,
        validation_sessions=args.validation_sessions,
        embargo_sessions=args.embargo_sessions,
        fold_id=f"fold_nifty50_10y_{context.ordinal:03d}",
    )
    return ModelInputs(features, labels, fold)


def _namespace(args: argparse.Namespace, **overrides: Any) -> argparse.Namespace:
    merged = vars(args).copy()
    merged.update(overrides)
    return argparse.Namespace(**merged)


def _trial_start(context: StudyContext, inputs: ModelInputs, trial_id: str) -> RidgeTrialStartV1:
    args = _namespace(
        context.args,
        trial_id=trial_id,
        multiplicity_ordinal=context.ordinal,
        score_threshold="auto",
    )
    return runner._trial_start(
        args,
        features=inputs.features,
        labels=inputs.labels,
        fold=inputs.fold,
        repo_root=context.repo_root,
        created_at=datetime.now(UTC),
    )


def _persist_model(context: StudyContext, inputs: ModelInputs) -> universe_runner.InstrumentResult:
    trial_id = f"trial_nifty50_10y_{context.ordinal:03d}"
    try:
        start = _trial_start(context, inputs, trial_id)
    except (ModelingError, runner.ConfigurationRefused) as error:
        detail = error.code.value if isinstance(error, ModelingError) else str(error)
        return _instrument_result(context, "TRIAL_START_REJECTED", detail)
    try:
        run_persisted_ridge_trial(
            context.model_store,
            operation_id=f"nifty50-10y-{context.symbol.lower()}-{context.ordinal:03d}",
            start=start,
            feature_dataset=inputs.features,
            label_dataset=inputs.labels,
            fold=inputs.fold,
            ended_at=datetime.now(UTC),
        )
    except ModelingError as error:
        return _instrument_result(context, "TRIAL_FAILED", error.code.value, trial_id=trial_id)
    except Exception as error:  # noqa: BLE001 - terminal failure is recorded per trial
        return _instrument_result(
            context,
            "TRIAL_CRASHED",
            f"{type(error).__name__}: {error}",
            trial_id=trial_id,
        )
    return _successful_result(context, start, trial_id)


def _successful_result(
    context: StudyContext, start: RidgeTrialStartV1, trial_id: str
) -> universe_runner.InstrumentResult:
    sharpe, accuracy, trades, dsr = universe_runner._metrics_for(
        context.args.evidence_root, trial_id
    )
    return universe_runner.InstrumentResult(
        context.symbol,
        context.instrument_key,
        "SUCCEEDED",
        f"threshold={start.score_threshold};cost_policy={RESEARCH_COST_POLICY_HASH[:12]}",
        trial_id=trial_id,
        sharpe=sharpe,
        accuracy=accuracy,
        trades=trades,
        published_dsr=dsr,
    )


def _run_one(context: StudyContext) -> universe_runner.InstrumentResult:
    discovery, discovery_state, refusal = _acquire_discovery(context)
    if refusal is not None or discovery is None:
        return refusal or _instrument_result(context, "CONFIG_REFUSED", "discovery absent")
    try:
        governance = _build_governance(context, discovery)
        governed, governed_state, refusal = _acquire_governed(context, governance)
    except runner.ConfigurationRefused as error:
        return _instrument_result(context, "CONFIG_REFUSED", str(error))
    if refusal is not None or governed is None:
        return refusal or _instrument_result(context, "CONFIG_REFUSED", "governed data absent")
    print(
        f"    data={discovery_state}/{governed_state} "
        f"corporate_actions={governance.corporate_cache_state} bars={len(governed.records)}",
        flush=True,
    )
    try:
        inputs = _prepare_model_inputs(context, governance, governed)
    except ModelingError as error:
        return _instrument_result(context, "MODELING_REJECTED", error.code.value)
    except (ValueError, runner.ConfigurationRefused) as error:
        return _instrument_result(context, "CONFIG_REFUSED", f"{type(error).__name__}: {error}")
    return _persist_model(context, inputs)


def _initialize(args: argparse.Namespace) -> CampaignContext:
    repo_root = Path(__file__).resolve().parent.parent
    runner._load_credentials_from_env_file(repo_root / ".env")
    if not os.getenv("UPSTOX_ACCESS_TOKEN"):
        print("UPSTOX_ACCESS_TOKEN is absent; the provider will return the typed outcome.")
    constituents = read_universe(args.universe_csv)
    selection = select_constituents(constituents, skip=args.skip, limit=args.limit)
    persist_runtime_authorities(args.cache_root, args.universe_csv)
    cache_store = EvidenceStore(EvidenceStoreConfig(root=args.cache_root / "store"))
    cache_catalog = VerifiedAcquisitionCatalog.open(cache_store)
    model_store = EvidenceStore(EvidenceStoreConfig(root=args.evidence_root))
    output = CampaignOutput(args, len(constituents))
    return CampaignContext(
        args,
        repo_root,
        constituents,
        selection,
        cache_catalog,
        model_store,
        UpstoxClient(),
        output,
    )


def _study_context(
    campaign: CampaignContext, symbol: str, instrument_key: str, ordinal: int
) -> StudyContext:
    return StudyContext(
        campaign.args,
        symbol,
        instrument_key,
        ordinal,
        campaign.selection.authority_members,
        campaign.client,
        campaign.cache_catalog,
        campaign.model_store,
        campaign.repo_root,
    )


def _run_or_integrity_error(
    context: StudyContext,
) -> tuple[universe_runner.InstrumentResult | None, EvidenceIntegrityError | None]:
    try:
        return _run_one(context), None
    except EvidenceIntegrityError as error:
        return None, error


def _execute(context: CampaignContext) -> int:
    args = context.args
    progress = CampaignProgress([], args.start_ordinal, len(context.selection.selected))
    for index, (symbol, instrument_key) in enumerate(context.selection.selected, start=1):
        study = _study_context(context, symbol, instrument_key, progress.ordinal)
        result, integrity_error = _run_or_integrity_error(study)
        if integrity_error is not None:
            return stop_for_integrity(context.output, progress.results, integrity_error)
        if result is None:
            raise AssertionError("study ended without a result or integrity error")
        stop_code = record_result(context.output, progress, index, result)
        if stop_code is not None:
            return stop_code
        if index < progress.total:
            time.sleep(args.sleep_seconds)
    universe_runner._report(progress.results, context.model_store)
    print("\nCampaign command ended; no promotion or certification action was taken.")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        context = _initialize(args)
    except (EvidenceIntegrityError, runner.ConfigurationRefused) as error:
        print(f"STARTUP REFUSED: {type(error).__name__}: {error}", flush=True)
        return 4
    print_campaign_header(context.output, len(context.selection.selected))
    return _execute(context)


if __name__ == "__main__":
    sys.exit(main())
