"""Train Mizan: one pooled cross-sectional governed model, at one multiplicity ordinal.

Every prior campaign in this repository trained one model per instrument and spent one multiplicity
ordinal per name -- 51 trials, then 50. Deflation correctly punishes that shape, because searching N
names finds the tail of a noise distribution by construction. Mizan is a single study: one model
ranking instruments against each other on the same date, costing one ordinal.

Features come from ``data/evidence/feature-store/mizan`` (built by ``build_mizan_feature_store.py``,
deduplicated, causal). Labels come from the governed cost-aware path -- real next-open execution and
real NSE statutory costs -- never from a forward close.

Constituents must be *universe-bound* governed acquisitions. An acquisition ingested without a
historical universe authority cannot produce governed labels (``modeling/labels.py`` refuses it), so
this script reports exactly which names it had to drop rather than quietly training on fewer.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import sys
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "scripts"))
sys.path.insert(0, str(ROOT_DIR / "src"))

import run_governed_ridge_training as runner  # noqa: E402
from build_mizan_feature_store import (  # noqa: E402
    authority_manifest_hash,
    code_revision,
    load_corporate_actions,
    load_validated_demerger_factors,
    raw_bar_points,
)
from cached_nifty50_costs import round_trip_cost_quotes  # noqa: E402
from cached_nifty50_evidence import historical_acquisition_from_verified  # noqa: E402

from quant_system.data.adjusted_acquisition import (  # noqa: E402
    derive_adjusted_acquisition,
    reference_from_plan,
)
from quant_system.data.adjustment_provenance import AdjustmentBasis  # noqa: E402
from quant_system.data.corporate_actions import (  # noqa: E402
    AdjustmentPlan,
    CorporateActionError,
    ValidatedFactor,
    build_adjustment_factors,
)
from quant_system.evidence import (  # noqa: E402
    EvidenceResourceType,
    EvidenceStore,
    EvidenceStoreConfig,
)
from quant_system.modeling import build_label_dataset  # noqa: E402
from quant_system.modeling.errors import ModelingError  # noqa: E402
from quant_system.modeling.evidence import (  # noqa: E402
    draft_from_feature_dataset,
    draft_from_label_dataset,
)
from quant_system.modeling.pooled import (  # noqa: E402
    build_mizan_feature_dataset,
    pool_feature_datasets,
    pool_label_datasets,
)
from quant_system.modeling.rows import (  # noqa: E402
    FEATURE_NAMES_V3,
    FEATURE_SCHEMA_ID_V3,
    FEATURE_SCHEMA_VERSION_V3,
    decimal_result,
)
from quant_system.modeling.training_evidence import run_persisted_ridge_trial  # noqa: E402
from quant_system.modeling.trials import RidgeTrialStartV1  # noqa: E402
from quant_system.modeling.validation import fold_spec_hash  # noqa: E402

CANDIDATE_ID = "cand_mizan_v1"

NSE_CORPORATE_ACTIONS_URL = "https://www.nseindia.com/api/corporates-corporateActions"
"""The endpoint the corporate-action authorities were fetched from, bound into every derivation."""


def load_feature_store(path: Path) -> dict[str, dict[date, dict[str, str]]]:
    """Feature values keyed by symbol then decision date, as canonical decimal text."""
    by_symbol: dict[str, dict[date, dict[str, str]]] = {}
    with gzip.open(path, "rt", newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            # The store writes fixed-width text; the row contract requires canonical decimals.
            values = {name: decimal_result(Decimal(row[name])) for name in FEATURE_NAMES_V3}
            by_symbol.setdefault(row["symbol"], {})[date.fromisoformat(row["date"])] = values
    return by_symbol


def governed_acquisitions(store_root: Path) -> dict[str, Any]:
    """Universe-bound acquisitions only. Anything else cannot produce governed labels."""
    store = EvidenceStore(EvidenceStoreConfig(root=store_root))
    found: dict[str, Any] = {}
    for verified in store.list_verified(EvidenceResourceType.DATASET):
        acquisition = historical_acquisition_from_verified(verified)
        manifest = acquisition.manifest
        if manifest.historical_universe_authority is None:
            continue
        incumbent = found.get(manifest.symbol)
        if incumbent is None or len(acquisition.records) > len(incumbent.records):
            found[manifest.symbol] = acquisition
    return found


def adjusted_constituent_acquisition(
    acquisition: Any,
    *,
    corporate_actions_dir: Path,
    validated: dict[date, ValidatedFactor] | None,
    total_return: bool,
    authority_hash: str,
    revision: str,
    derived_at: datetime,
) -> tuple[Any, AdjustmentPlan]:
    """The corporate-action-adjusted derivation of one raw acquisition, with honest provenance.

    This is the piece that was missing and that blocked the governed retrain. The feature store was
    rebuilt on adjusted bars while ``build_label_dataset`` still read entry and exit opens off the
    **raw** acquisition, so the model would have been fitted on corrected inputs against targets
    still containing every corporate-action break. Deriving the acquisition here puts both sides on
    one basis, and the derived manifest declares itself ADJUSTED rather than inheriting the raw
    manifest's ``RAW`` literal.

    The raw acquisition is returned to the caller untouched and is what the cost path prices.
    """
    symbol = acquisition.manifest.symbol
    actions = load_corporate_actions(corporate_actions_dir, symbol)
    bars = raw_bar_points(acquisition)
    plan = build_adjustment_factors(
        actions, bars, total_return=total_return, validated_factors=validated
    )
    reference = reference_from_plan(
        plan,
        manifest=acquisition.manifest,
        basis=AdjustmentBasis.TOTAL_RETURN if total_return else AdjustmentBasis.PRICE_RETURN,
        authority_content_hash=authority_hash,
        authority_source_url=NSE_CORPORATE_ACTIONS_URL,
        authority_publication_date=None,
        code_revision=revision,
        derived_at=derived_at,
    )
    return derive_adjusted_acquisition(acquisition, plan, reference), plan


def _constituent(
    symbol: str,
    acquisition: Any,
    values: dict[date, dict[str, str]],
    calendar_version: str,
    quantity: int,
    horizon_sessions: int,
    execution_acquisition: Any = None,
) -> tuple[Any, Any, Any]:
    """One instrument's governed feature and label datasets.

    ``acquisition`` is the series the model is *measured* on. When the caller has derived a
    corporate-action-adjusted acquisition it passes that here and the raw one as
    ``execution_acquisition``, so features, labels and P&L all sit on one basis while the costs stay
    quoted on the prices a fill actually executes at. Passing only ``acquisition`` reproduces the
    previous behaviour exactly.
    """
    execution = execution_acquisition if execution_acquisition is not None else acquisition
    calendar = runner._calendar_from_acquisition(acquisition, calendar_version)
    features = build_mizan_feature_dataset(
        acquisition,
        CANDIDATE_ID,
        calendar,
        acquisition.manifest.historical_universe_authority.content_hash,
        values,
    )
    # Costs are priced on the executable raw series. A flat DP charge and a capped brokerage do not
    # scale with a synthetic adjusted price, so quoting them on adjusted bars would misstate them.
    quotes = round_trip_cost_quotes(
        features, execution, calendar, quantity=quantity, horizon_sessions=horizon_sessions
    )
    labels = build_label_dataset(
        features,
        acquisition,
        calendar,
        quotes,
        horizon_sessions=horizon_sessions,
        execution_acquisition=execution if execution is not acquisition else None,
    )
    return features, labels, calendar


def _largest_calendar_group(
    constituents: list[tuple[str, Any, Any, Any]],
) -> tuple[Any, list[tuple[str, Any, Any, Any]], list[str]]:
    """The biggest set of constituents sharing one session calendar, plus who that excludes.

    A label is valid against the calendar it was built from: ``build_purged_fold`` checks that entry
    and exit are the next two *eligible* session opens. A union calendar would contain sessions on
    which a given name did not trade, so its labels would appear to skip an eligible open and the
    fold would be rejected -- correctly. Pooling therefore requires one shared session grid, and the
    honest way to get one is to take the largest group and name what falls outside it.
    """
    groups: dict[str, list[tuple[str, Any, Any, Any]]] = {}
    for entry in constituents:
        groups.setdefault(entry[3].reference.content_hash, []).append(entry)
    chosen = max(groups.values(), key=len)
    excluded = sorted(e[0] for g in groups.values() if g is not chosen for e in g)
    return chosen[0][3], chosen, excluded


def _publish_datasets(store: EvidenceStore, features: Any, labels: Any) -> bool:
    """Publish the pooled feature and label datasets as DATASET evidence resources.

    Why this exists
    ---------------
    Every trial records a ``dataset_id``/``dataset_hash``, and until now **nothing published the
    resource those identifiers name** -- no evidence store in this repository held a single DATASET
    resource. An independent adjudication
    (``.launch/reports/ADJUDICATION-TRAINING-PATH-20260911.md``) rated the claim that the governed
    retrain ran on corporate-action-adjusted data as ``NOT TESTED`` for exactly that reason: the
    binding was recorded but unresolvable, the MODEL manifest carries no adjustment field, and
    ``feature_schema_version`` is identical either side of the adjustment boundary, so the schema
    cannot be used to infer it either.

    Publishing the dataset makes the binding resolve. The label dataset carries
    ``source_dataset_id``, naming the acquisition the labels were measured on -- and an adjusted
    acquisition is a *separate* artifact with its own manifest hash and an ``AdjustmentReference``.
    A reader can then walk trial -> dataset -> acquisition -> adjustment method and authorities,
    instead of taking an author's word for it.

    This spends **no multiplicity ordinal**: publishing data is not a trial. Commits are idempotent,
    so re-running is safe and a dataset shared by several trials is written once.
    """
    ok = True
    for label, draft in (
        ("features", draft_from_feature_dataset(features)),
        ("labels", draft_from_label_dataset(labels)),
    ):
        try:
            result = store.commit(draft, operation_id=f"mizan-dataset-{draft.resource_id}")
        except Exception as error:  # noqa: BLE001 - reported per dataset, never aborts the run
            print(f"dataset {label:9s}: REFUSED -- {type(error).__name__}: {error}", flush=True)
            ok = False
            continue
        print(
            f"dataset {label:9s}: published {draft.resource_id} -> {result.manifest.manifest_hash}",
            flush=True,
        )
    return ok


def run(args: argparse.Namespace) -> int:
    print("=== MIZAN: pooled cross-sectional governed training ===", flush=True)
    features_by_symbol = load_feature_store(args.feature_store)
    print(f"feature store      : {len(features_by_symbol)} symbols", flush=True)

    acquisitions = governed_acquisitions(args.market_cache)
    print(f"governed (bound)   : {len(acquisitions)} acquisitions", flush=True)

    usable = sorted(set(acquisitions) & set(features_by_symbol))
    dropped_no_features = sorted(set(acquisitions) - set(features_by_symbol))
    print(f"usable constituents: {len(usable)}", flush=True)
    if dropped_no_features:
        print(f"  dropped (no features): {', '.join(dropped_no_features)}", flush=True)
    if not usable:
        print("REFUSED: no instrument has both a universe-bound acquisition and features.")
        return 2

    adjust = not args.no_adjust
    revision = code_revision()
    derived_at = datetime.now(UTC)
    authority_hash = authority_manifest_hash(args.corporate_actions_dir) or ""
    validated_by_symbol = load_validated_demerger_factors(
        None if args.no_adjust else args.validated_factors
    )
    if adjust:
        print(
            f"adjustment         : ENABLED, basis "
            f"{'TOTAL_RETURN' if not args.price_return else 'PRICE_RETURN'}, "
            f"authority {authority_hash[:12]}, revision {revision[:12]}",
            flush=True,
        )
    else:
        print("adjustment         : DISABLED -- labels measured on RAW provider bars", flush=True)

    constituents: list[tuple[str, Any, Any, Any]] = []
    failures: list[tuple[str, str]] = []
    total_factors = 0
    total_unresolved = 0
    for symbol in usable:
        raw = acquisitions[symbol]
        measured, execution = raw, None
        if adjust:
            try:
                measured, plan = adjusted_constituent_acquisition(
                    raw,
                    corporate_actions_dir=args.corporate_actions_dir,
                    validated=validated_by_symbol.get(symbol),
                    total_return=not args.price_return,
                    authority_hash=authority_hash,
                    revision=revision,
                    derived_at=derived_at,
                )
            except (CorporateActionError, ValueError) as error:
                failures.append((symbol, f"ADJUSTMENT_FAILED: {error}"))
                continue
            execution = raw
            total_factors += len(plan.factors)
            total_unresolved += len(plan.unresolved)
        try:
            features, labels, calendar = _constituent(
                symbol,
                measured,
                features_by_symbol[symbol],
                args.calendar_version,
                args.quantity,
                args.horizon_sessions,
                execution,
            )
        except (ModelingError, runner.ConfigurationRefused) as error:
            detail = error.code.value if isinstance(error, ModelingError) else str(error)
            failures.append((symbol, detail))
            continue
        constituents.append((symbol, features, labels, calendar))
        print(
            f"  {symbol:14s} features={len(features.rows):5d} labels={len(labels.rows):5d}",
            flush=True,
        )

    if adjust:
        print(
            f"\ncorporate actions  : {total_factors:,} factors applied, "
            f"{total_unresolved} unresolved (their label windows refused)",
            flush=True,
        )

    if failures:
        print(f"\nconstituents refused: {len(failures)}", flush=True)
        for symbol, detail in failures:
            print(f"  {symbol:14s} {detail}", flush=True)
    if not constituents:
        print("REFUSED: every constituent failed to produce governed labels.")
        return 2

    calendar, chosen, excluded = _largest_calendar_group(constituents)
    if excluded:
        print(
            f"\nexcluded (different session calendar): {len(excluded)} -- {', '.join(excluded)}",
            flush=True,
        )
    feature_sets = [entry[1] for entry in chosen]
    label_sets = [entry[2] for entry in chosen]

    pooled_features = pool_feature_datasets(feature_sets, candidate_id=CANDIDATE_ID)
    pooled_labels = pool_label_datasets(
        label_sets, candidate_id=CANDIDATE_ID, feature_dataset=pooled_features
    )
    sessions = len({row.decision_at for row in pooled_labels.rows})
    print(
        f"\npooled             : {len(feature_sets)} instruments, "
        f"{len(pooled_features.rows):,} feature rows, {len(pooled_labels.rows):,} label rows, "
        f"{sessions:,} decision dates",
        flush=True,
    )

    args.evidence_root.mkdir(parents=True, exist_ok=True)
    published = _publish_datasets(
        EvidenceStore(EvidenceStoreConfig(root=args.evidence_root)),
        pooled_features,
        pooled_labels,
    )
    if args.publish_datasets_only:
        print("\npublish-datasets-only: no trial run, no multiplicity ordinal spent.", flush=True)
        return 0 if published else 3

    embargo = max(args.embargo_sessions, args.horizon_sessions)
    fold = runner._fold_from_tail(
        pooled_labels,
        calendar,
        validation_sessions=args.validation_sessions,
        embargo_sessions=embargo,
        fold_id=f"fold_mizan_h{args.horizon_sessions:02d}",
        label_horizon_sessions=args.horizon_sessions,
    )
    print(
        f"fold               : train={len(fold.train_rows):,} "
        f"validation={len(fold.validation_rows):,} embargo={embargo}",
        flush=True,
    )

    trial_id = f"trial_mizan_h{args.horizon_sessions:02d}_{args.multiplicity_ordinal:03d}"
    threshold = runner.base_rate_threshold(fold)
    start = RidgeTrialStartV1(
        trial_id=trial_id,
        candidate_id=CANDIDATE_ID,
        created_at=datetime.now(UTC),
        dataset_id=pooled_labels.dataset_id,
        dataset_hash=pooled_labels.dataset_hash,
        universe_policy_hash=pooled_features.universe_authority_hash,
        l2_penalty=args.l2_penalty,
        score_threshold=threshold,
        numpy_seed=0,
        fold_spec_hashes=(fold_spec_hash(fold),),
        source_revision=runner._source_revision(ROOT_DIR),
        environment_lock_hash=runner._environment_lock_hash(ROOT_DIR),
        architecture=runner._architecture(),
        multiplicity_ordinal=args.multiplicity_ordinal,
        feature_schema_id=FEATURE_SCHEMA_ID_V3,
        feature_schema_version=FEATURE_SCHEMA_VERSION_V3,
    )
    print(f"threshold          : {threshold} (training base rate)", flush=True)
    print(f"multiplicity       : ordinal {start.multiplicity_ordinal}", flush=True)

    args.evidence_root.mkdir(parents=True, exist_ok=True)
    model_store = EvidenceStore(EvidenceStoreConfig(root=args.evidence_root))
    result = run_persisted_ridge_trial(
        model_store,
        operation_id=f"mizan-pooled-h{args.horizon_sessions:02d}-{args.multiplicity_ordinal:03d}",
        start=start,
        feature_dataset=pooled_features,
        label_dataset=pooled_labels,
        fold=fold,
        ended_at=datetime.now(UTC),
    )
    print("\nMIZAN TRIAL PUBLISHED", flush=True)
    print(f"  evidence root : {args.evidence_root}", flush=True)
    print(f"  result        : {result!r}", flush=True)
    print(
        "\nThis is a research result, not a certification. No Red Team pass, no independent "
        "Verifier pass, and promotion remains whatever the gate actually returns.",
        flush=True,
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--publish-datasets-only",
        action="store_true",
        help="Assemble and publish the pooled feature/label datasets as DATASET evidence "
        "resources, then stop. Runs no trial and spends no multiplicity ordinal. Exists to close "
        "the auditability gap the 2026-09-11 adjudication found: trials bind a dataset_id that no "
        "store ever published, so a reader cannot confirm what a model was fitted on.",
    )
    parser.add_argument(
        "--feature-store",
        type=Path,
        default=ROOT_DIR / "data/evidence/feature-store/mizan/mizan_feature_store.csv.gz",
    )
    parser.add_argument(
        "--market-cache",
        type=Path,
        default=ROOT_DIR / "data/evidence/market-cache/nifty50-current-20160822-20260821/store",
    )
    parser.add_argument(
        "--evidence-root", type=Path, default=ROOT_DIR / "data/evidence/models/mizan-v1"
    )
    parser.add_argument("--validation-sessions", type=int, default=252)
    parser.add_argument("--multiplicity-ordinal", type=int, default=1)
    parser.add_argument("--embargo-sessions", type=int, default=2)
    parser.add_argument(
        "--horizon-sessions",
        type=int,
        default=2,
        help=(
            "Sessions from decision to exit. 2 is the original one-session hold, which measures "
            "below the cost break-even; about 4 breaks even and 11 gives real margin."
        ),
    )
    parser.add_argument("--l2-penalty", default="1")
    parser.add_argument("--quantity", type=int, default=1)
    parser.add_argument("--calendar-version", default="provider-derived-v1")
    parser.add_argument(
        "--corporate-actions-dir",
        type=Path,
        default=ROOT_DIR
        / "data/evidence/market-cache/all-market-20160822-20260821/corporate-actions",
        help="Authority the label-side adjustment is derived from. Must be the same snapshot the "
        "feature store was built against, or features and labels sit on different bases.",
    )
    parser.add_argument(
        "--validated-factors",
        type=Path,
        default=ROOT_DIR / "data/authorities/nse-validated-demerger-factors.json",
        help="Independently validated demerger factors. Ratio-less actions absent from this file "
        "stay unresolved and every label window spanning one is refused.",
    )
    parser.add_argument(
        "--price-return",
        action="store_true",
        help="Adjust structural actions only, leaving dividends as price drops. The default is "
        "total return, which also removes dividends -- and which makes training returns "
        "inconsistent with both paper books, since neither credits a dividend.",
    )
    parser.add_argument(
        "--no-adjust",
        action="store_true",
        help="Measure labels on RAW provider bars, reproducing the pre-adjustment run. Diagnostic "
        "only: the feature store is built on adjusted bars, so this deliberately mismatches the "
        "two sides and exists to quantify what the adjustment changed.",
    )
    return run(parser.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
