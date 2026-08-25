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
from cached_nifty50_costs import round_trip_cost_quotes  # noqa: E402
from cached_nifty50_evidence import historical_acquisition_from_verified  # noqa: E402

from quant_system.evidence import (  # noqa: E402
    EvidenceResourceType,
    EvidenceStore,
    EvidenceStoreConfig,
)
from quant_system.modeling import build_label_dataset  # noqa: E402
from quant_system.modeling.errors import ModelingError  # noqa: E402
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


def _constituent(
    symbol: str,
    acquisition: Any,
    values: dict[date, dict[str, str]],
    calendar_version: str,
    quantity: int,
    horizon_sessions: int,
) -> tuple[Any, Any, Any]:
    """One instrument's governed feature and label datasets."""
    calendar = runner._calendar_from_acquisition(acquisition, calendar_version)
    features = build_mizan_feature_dataset(
        acquisition,
        CANDIDATE_ID,
        calendar,
        acquisition.manifest.historical_universe_authority.content_hash,
        values,
    )
    quotes = round_trip_cost_quotes(
        features, acquisition, calendar, quantity=quantity, horizon_sessions=horizon_sessions
    )
    labels = build_label_dataset(
        features, acquisition, calendar, quotes, horizon_sessions=horizon_sessions
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

    constituents: list[tuple[str, Any, Any, Any]] = []
    failures: list[tuple[str, str]] = []
    for symbol in usable:
        try:
            features, labels, calendar = _constituent(
                symbol,
                acquisitions[symbol],
                features_by_symbol[symbol],
                args.calendar_version,
                args.quantity,
                args.horizon_sessions,
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
    return run(parser.parse_args(argv))


if __name__ == "__main__":
    raise SystemExit(main())
