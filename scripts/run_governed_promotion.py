"""Run one governed promotion end to end over real Upstox data.

`run_persisted_promotion` (``modeling/promotion_pipeline.py``) closed Red Team finding X-1 by
giving the Slice 5 stack a caller inside ``src/``. It did not give it a *product surface*: nothing
an operator can actually run. This module is that surface, and it is the promotion analogue of
``scripts/run_governed_ridge_training.py``.

    real acquisition (train window) -> features -> labels -> purged fold
      -> run_persisted_ridge_trial        (the attempt is counted for multiplicity)
    real acquisition (full window)  -> features -> labels
      -> create_holdout_partition         (single-use unlock token)
      -> run_persisted_promotion          (holdout -> stress -> promotion, all published)

Two acquisitions, not one, and that is the point. The training window ends at ``--train-to-date``;
the holdout opens at ``--holdout-from-date``. The fit therefore stops before the holdout begins, so
the final holdout is genuinely unseen. A single acquisition would force the training fold and the
holdout to be carved from the same tail, which is look-ahead leakage of exactly the kind the
governed stack exists to prevent. This runner refuses a configuration where the windows touch.

Every computation is imported from ``run_governed_ridge_training``: acquisition, the session
calendar, the corporate-action and universe authorities, the dated NSE cost quotes, and the fold.
Nothing is recomputed here. A second cost or calendar path is the defect class this repository has
hit repeatedly, and this module does not add another one.

This runner imports no data generator, so it has no synthetic fallback to take. If the provider
refuses, its typed failure is what gets printed.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import run_governed_ridge_training as t  # noqa: E402

from quant_system.data.market_data import (  # noqa: E402
    HistoricalAcquisition,
    HistoricalDailyRequest,
)
from quant_system.data.upstox import UpstoxClient  # noqa: E402
from quant_system.evidence import EvidenceStore, EvidenceStoreConfig  # noqa: E402
from quant_system.evidence.errors import EvidenceError  # noqa: E402
from quant_system.modeling import (  # noqa: E402
    build_feature_dataset,
    build_label_dataset,
    run_persisted_ridge_trial,
)
from quant_system.modeling.authorities import SessionCalendarV1  # noqa: E402
from quant_system.modeling.errors import ModelingError  # noqa: E402
from quant_system.modeling.features import FEATURE_WARMUP_BARS_V1  # noqa: E402
from quant_system.modeling.holdout import (  # noqa: E402
    HoldoutVaultTracker,
    create_holdout_partition,
)
from quant_system.modeling.promotion import PromotionState  # noqa: E402
from quant_system.modeling.promotion_pipeline import (  # noqa: E402
    PersistedPromotionV1,
    run_persisted_promotion,
)
from quant_system.modeling.rows import (  # noqa: E402
    FeatureDatasetV1,
    LabelDatasetV1,
    RoundTripCostQuoteV1,
)


@dataclass(frozen=True, slots=True)
class _Window:
    """Everything one acquisition window produces, so nothing is acquired twice."""

    acquisition: HistoricalAcquisition
    calendar: SessionCalendarV1
    features: FeatureDatasetV1
    labels: LabelDatasetV1
    cost_quotes: tuple[RoundTripCostQuoteV1, ...]


def _acquire_window(
    client: UpstoxClient,
    args: argparse.Namespace,
    *,
    to_date: date,
    stage: str,
) -> _Window:
    """Acquire one window and build its calendar, authorities, features, labels and quotes."""
    discovery = t._acquire(
        client,
        HistoricalDailyRequest(
            instrument_key=args.instrument_key,
            symbol=args.symbol,
            from_date=args.from_date,
            to_date=to_date,
            request_id=f"{args.request_id}-{stage}",
        ),
        f"discovery/{stage}",
    )
    if args.calendar_file is not None:
        calendar = t._calendar_from_file(args.calendar_file, args.calendar_version)
    else:
        calendar = t._calendar_from_acquisition(discovery, args.calendar_version)

    first_session = calendar.sessions[0].exchange_date
    last_session = calendar.sessions[-1].exchange_date
    corporate = t._corporate_action_authority(
        document=args.corporate_actions_file,
        authority_id=args.corporate_authority_id,
        source_url=args.corporate_authority_url,
        version=args.corporate_authority_version,
        first_session=first_session,
        last_session=last_session,
    )
    universe = t._universe_snapshot(
        members=t._universe_members(args.universe_file, args.instrument_key),
        authority_id=args.universe_authority_id,
        source_url=args.universe_authority_url,
        version=args.universe_authority_version,
        first_session=first_session,
        last_session=last_session,
    )

    governed_args = argparse.Namespace(**vars(args))
    governed_args.to_date = to_date
    governed_args.request_id = f"{args.request_id}-{stage}"
    acquisition = t._acquire(
        client,
        t._governed_request(
            governed_args, calendar=calendar, corporate=corporate, universe=universe
        ),
        f"governed/{stage}",
    )
    if len(acquisition.records) < FEATURE_WARMUP_BARS_V1:
        raise t.ConfigurationRefused(
            f"the feature schema needs at least {FEATURE_WARMUP_BARS_V1} bars; "
            f"the {stage} window returned {len(acquisition.records)}"
        )

    features = build_feature_dataset(acquisition, args.candidate_id, calendar, universe)
    quotes = t._round_trip_cost_quotes(features, acquisition, calendar, quantity=args.quantity)
    labels = build_label_dataset(features, acquisition, calendar, quotes)
    t._log(
        f"[{stage}] datasets",
        f"{len(acquisition.records)} bars -> {len(features.rows)} feature rows "
        f"-> {len(labels.rows)} label rows",
    )
    return _Window(
        acquisition=acquisition,
        calendar=calendar,
        features=features,
        labels=labels,
        cost_quotes=quotes,
    )


def _refuse_leaky_windows(args: argparse.Namespace) -> None:
    """A holdout that touches the training window is not a holdout."""
    if args.train_to_date >= args.holdout_from_date:
        raise t.ConfigurationRefused(
            f"--train-to-date {args.train_to_date} must fall before --holdout-from-date "
            f"{args.holdout_from_date}; overlapping windows leak the holdout into the fit"
        )
    if args.holdout_from_date > args.to_date:
        raise t.ConfigurationRefused(
            f"--holdout-from-date {args.holdout_from_date} falls after --to-date {args.to_date}"
        )
    gap_days = (args.holdout_from_date - args.train_to_date).days
    if gap_days < args.min_holdout_gap_days:
        raise t.ConfigurationRefused(
            f"only {gap_days} calendar days separate the training window from the holdout; "
            f"at least {args.min_holdout_gap_days} are required so a label opened on the last "
            "training session has matured before the holdout opens"
        )


def _session_close_on_or_after(calendar: SessionCalendarV1, wanted: date) -> datetime:
    for session in calendar.sessions:
        if session.exchange_date >= wanted:
            return session.close_at
    raise t.ConfigurationRefused(
        f"no exchange session falls on or after --holdout-from-date {wanted}"
    )


def _report(result: PersistedPromotionV1, evidence_root: Path) -> None:
    record = result.promotion_record
    print("", flush=True)
    print("GOVERNED PROMOTION COMPLETE", flush=True)
    print(f"  verdict               : {record.verdict.value}", flush=True)
    print(
        f"  from -> to            : {record.from_state.value} -> {record.to_state.value}",
        flush=True,
    )
    print(f"  failed gates          : {list(record.failed_gate_codes) or 'none'}", flush=True)
    print(f"  holdout deflated SR   : {result.holdout_report.deflated_sharpe_ratio}", flush=True)
    print(f"  stress all passed     : {result.stress_report.all_passed}", flush=True)
    print(f"  model card issued     : {result.model_card is not None}", flush=True)
    print(f"  evidence root         : {evidence_root}", flush=True)
    print("", flush=True)
    print(
        "This is a research result, not a certification. It has had no Red Team pass and no "
        "independent Verifier pass.",
        flush=True,
    )


def _run(args: argparse.Namespace) -> int:
    repo_root = Path(__file__).resolve().parent.parent
    _refuse_leaky_windows(args)
    client = UpstoxClient()

    # ---- Training window: the fit must never see the holdout --------------------------
    t._log(
        "[1/5] training window",
        f"{args.instrument_key} {args.symbol} {args.from_date}..{args.train_to_date}",
    )
    train = _acquire_window(client, args, to_date=args.train_to_date, stage="train")
    fold = t._fold_from_tail(
        train.labels,
        train.calendar,
        validation_sessions=args.validation_sessions,
        embargo_sessions=args.embargo_sessions,
        fold_id=args.fold_id,
    )
    t._log(
        "[2/5] purged fold",
        f"train={len(fold.train_rows)} validation={len(fold.validation_rows)} "
        f"embargo={args.embargo_sessions}",
    )

    args.evidence_root.mkdir(parents=True, exist_ok=True)
    store = EvidenceStore(EvidenceStoreConfig(root=args.evidence_root))
    trial = run_persisted_ridge_trial(
        store,
        operation_id=f"{args.operation_id}-trial",
        start=t._trial_start(
            args,
            features=train.features,
            labels=train.labels,
            fold=fold,
            repo_root=repo_root,
            created_at=datetime.now(UTC),
        ),
        feature_dataset=train.features,
        label_dataset=train.labels,
        fold=fold,
        ended_at=datetime.now(UTC),
    )
    t._log(
        "[3/5] persisted trial",
        f"state={trial.outcome.state.value} model={trial.evaluation.model_id}",
    )

    # ---- Full window: the holdout is carved from data the fit never saw ---------------
    t._log(
        "[4/5] holdout window",
        f"{args.from_date}..{args.to_date}, holdout opens {args.holdout_from_date}",
    )
    full = _acquire_window(client, args, to_date=args.to_date, stage="full")
    partition, token = create_holdout_partition(
        full.labels,
        full.features,
        full.calendar,
        holdout_id=args.holdout_id,
        holdout_start=_session_close_on_or_after(full.calendar, args.holdout_from_date),
        holdout_end=full.calendar.sessions[-1].close_at,
        embargo_sessions=args.embargo_sessions,
    )
    t._log(
        "[4/5] holdout partition",
        f"discovery={partition.spec.discovery_row_count} "
        f"holdout={partition.spec.holdout_row_count}",
    )

    # ---- Governed promotion ------------------------------------------------------------
    result = run_persisted_promotion(
        store,
        operation_id=f"{args.operation_id}-promotion",
        holdout=partition,
        unlock_token=token,
        tracker=HoldoutVaultTracker(store),
        evaluation=trial.evaluation,
        feature_dataset=full.features,
        label_dataset=full.labels,
        cost_quotes=full.cost_quotes,
        calendar=full.calendar,
        multiplicity_count=args.multiplicity_count,
        from_state=PromotionState(args.from_state),
        to_state=PromotionState(args.to_state),
        evaluation_id=args.evaluation_id,
        promotion_id=args.promotion_id,
        evaluated_at=datetime.now(UTC),
    )
    t._log("[5/5] promotion", f"verdict={result.promotion_record.verdict.value}")
    _report(result, args.evidence_root)
    return t.EXIT_OK


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    promo = argparse.ArgumentParser(add_help=False)
    promo.add_argument(
        "--train-to-date",
        type=date.fromisoformat,
        required=True,
        help="last date the model may be fitted on; the holdout opens strictly after this",
    )
    promo.add_argument(
        "--holdout-from-date",
        type=date.fromisoformat,
        required=True,
        help="first date of the final holdout; must fall after --train-to-date",
    )
    promo.add_argument(
        "--min-holdout-gap-days",
        type=int,
        default=7,
        help="calendar days required between the training window and the holdout",
    )
    promo.add_argument("--holdout-id", default="holdout_001")
    promo.add_argument("--evaluation-id", default="holdout_eval_001")
    promo.add_argument("--promotion-id", default="promo_eval_001")
    promo.add_argument("--from-state", default=PromotionState.RESEARCH_ONLY.value)
    promo.add_argument("--to-state", default=PromotionState.SHADOW.value)
    promo.add_argument(
        "--multiplicity-count",
        type=int,
        default=1,
        help="total attempts this candidate family has spent; deflation depends on it",
    )
    promo_args, rest = promo.parse_known_args(list(argv) if argv is not None else None)
    merged = argparse.Namespace(**vars(t._parse_args(rest)))
    for key, value in vars(promo_args).items():
        setattr(merged, key, value)
    return merged


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    env_file = args.env_file or Path(__file__).resolve().parent.parent / ".env"
    loaded = t._load_credentials_from_env_file(env_file)
    if loaded:
        t._log("[0/5] credential", f"loaded {', '.join(loaded)} from {env_file.name}")
    if not os.getenv("UPSTOX_ACCESS_TOKEN"):
        t._log(
            "[0/5] credential", "UPSTOX_ACCESS_TOKEN is not set; the provider will be asked anyway"
        )
    try:
        return _run(args)
    except t.ConfigurationRefused as error:
        print("", flush=True)
        print(f"CONFIGURATION REFUSED: {error}", flush=True)
        return t.EXIT_CONFIG_REFUSED
    except ModelingError as error:
        print("", flush=True)
        print("GOVERNED MODELING REJECTED THE REAL DATA", flush=True)
        print(f"  code                  : {error.code.value}", flush=True)
        print(f"  detail                : {error}", flush=True)
        return t.EXIT_MODELING_REJECTED
    except EvidenceError as error:
        print("", flush=True)
        print("EVIDENCE PUBLICATION FAILED", flush=True)
        print(f"  detail                : {type(error).__name__}: {error}", flush=True)
        return t.EXIT_EVIDENCE_FAILED


if __name__ == "__main__":
    sys.exit(main())
