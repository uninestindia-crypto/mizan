"""Pooled cross-sectional dataset assembly for Mizan.

Every governed dataset before this one bound each feature row to a single acquisition manifest, so
a campaign over N instruments was N independent studies costing N multiplicity ordinals. Deflation
correctly punishes that: searching N names finds the tail of a noise distribution by construction.

A pooled dataset is one study. Rows from many instruments share one candidate, one universe
authority, and one *pooled source identity* -- a hash over the constituent acquisition manifests, so
the exact set of acquisitions that produced the pool stays reproducible from the dataset hash alone.
The per-row ``provider_instrument_id`` and ``symbol`` still say which instrument each row came from,
so nothing about attribution is lost.

Adoption note: ``src/quant_system/modeling/*.py`` is claimed by
``20260821-1048Z-claude-slice4-redteam-repair`` (STATUS: HANDOFF_REQUIRED). This module is a new
file that existed at no revision that record touched, and the adoption follows the precedent set by
``20260822-claude-h2-l2-repair`` for ``holdout.py``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date

from quant_system.data.market_data import PointInTimeBar
from quant_system.data.market_data_evidence import canonical_sha256, utc_text
from quant_system.modeling.errors import ModelingError, ModelingFailureCode
from quant_system.modeling.rows import (
    FEATURE_ROW_SCHEMA,
    FEATURE_SCHEMA_ID_V3,
    FEATURE_SCHEMA_VERSION_V3,
    LABEL_ROW_SCHEMA,
    FeatureDatasetV1,
    FeatureRowV1,
    LabelDatasetV1,
    LabelRowV1,
    derived_dataset_hash,
    feature_names_for,
    label_contract_version_for,
)

MIZAN_WINDOW_BARS = 51
"""Trailing bars a Mizan feature row consumes: 50 warm-up sessions plus the decision bar.

Fixed rather than expanding, for the reason recorded in
``agent_context/decisions/20260824-canonical-feature-window.md``: a window that depends on how much
history happens to be retained makes the same decision bar take different feature values in
training and in execution.
"""


def _pooled_identity(kind: str, constituents: Sequence[tuple[str, str, str]]) -> tuple[str, str]:
    """A content hash over the constituent acquisitions, and the dataset id derived from it."""
    digest = canonical_sha256(
        {
            "constituents": [
                {"dataset_hash": h, "dataset_id": i, "symbol": s}
                for s, i, h in sorted(constituents)
            ],
            "schema_id": f"quantos.mizan_pooled_{kind}",
            "schema_version": 1,
        }
    )
    return f"dset_{digest[:24]}", digest


def build_mizan_feature_dataset(
    acquisition: object,
    candidate_id: str,
    calendar: object,
    universe_authority_hash: str,
    values_by_date: Mapping[date, Mapping[str, str]],
) -> FeatureDatasetV1:
    """Wrap precomputed Mizan feature values in governed, point-in-time-checked rows.

    The values are supplied rather than computed here because two of them -- the cross-sectional
    ranks -- are not functions of one instrument's history. They rank an instrument against the rest
    of the universe on its own decision date, which is precisely the information a single-instrument
    feature kernel cannot express.

    The point-in-time guarantee is enforced here regardless: every bar in the consumed window must
    have been available by the session close that the row is dated to.
    """
    names = feature_names_for(FEATURE_SCHEMA_ID_V3, FEATURE_SCHEMA_VERSION_V3)
    manifest = acquisition.manifest  # type: ignore[attr-defined]
    records: tuple[PointInTimeBar, ...] = acquisition.records  # type: ignore[attr-defined]
    rows: list[FeatureRowV1] = []

    for ordinal in range(MIZAN_WINDOW_BARS - 1, len(records)):
        current = records[ordinal]
        values = values_by_date.get(current.exchange_date)
        if values is None:
            continue
        session = calendar.session_for_date(current.exchange_date)  # type: ignore[attr-defined]
        if session is None:
            continue
        consumed = records[ordinal - MIZAN_WINDOW_BARS + 1 : ordinal + 1]
        for record in consumed:
            if record.available_at > session.close_at:
                raise ModelingError(
                    ModelingFailureCode.POINT_IN_TIME_VIOLATION,
                    "feature input was not available by the decision time",
                )
        if tuple(values) != names:
            raise ModelingError(
                ModelingFailureCode.TRAINING_INPUT_MISMATCH,
                "supplied feature values do not match the Mizan feature family",
            )
        rows.append(
            FeatureRowV1(
                candidate_id=candidate_id,
                dataset_id=manifest.dataset_id,
                dataset_hash=manifest.manifest_hash,
                provider_instrument_id=manifest.provider_instrument_id,
                symbol=manifest.symbol,
                decision_at=session.close_at,
                information_cutoff_at=max(record.available_at for record in consumed),
                universe_authority_hash=universe_authority_hash,
                feature_schema_id=FEATURE_SCHEMA_ID_V3,
                feature_schema_version=FEATURE_SCHEMA_VERSION_V3,
                features=dict(values),
                preprocessing_input_hash=canonical_sha256(
                    {
                        "decision_at": utc_text(session.close_at),
                        "feature_schema_id": FEATURE_SCHEMA_ID_V3,
                        "feature_schema_version": FEATURE_SCHEMA_VERSION_V3,
                        "records": [record.to_canonical_dict() for record in consumed],
                    }
                ),
            )
        )

    if not rows:
        raise ModelingError(
            ModelingFailureCode.DATASET_INTEGRITY_INVALID,
            "no Mizan feature rows survived point-in-time and calendar validation",
        )
    rows.sort(key=lambda row: (row.decision_at, row.provider_instrument_id))
    return _finalize_feature_dataset(
        rows,
        candidate_id=candidate_id,
        source_dataset_id=manifest.dataset_id,
        source_dataset_hash=manifest.manifest_hash,
        calendar_hash=calendar.reference.content_hash,  # type: ignore[attr-defined]
        corporate_action_authority_hash=manifest.corporate_action_authority.content_hash,
        universe_authority_hash=universe_authority_hash,
    )


def _finalize_feature_dataset(
    rows: list[FeatureRowV1],
    *,
    candidate_id: str,
    source_dataset_id: str,
    source_dataset_hash: str,
    calendar_hash: str,
    corporate_action_authority_hash: str,
    universe_authority_hash: str,
) -> FeatureDatasetV1:
    metadata = {
        "calendar_hash": calendar_hash,
        "candidate_id": candidate_id,
        "corporate_action_authority_hash": corporate_action_authority_hash,
        "feature_schema_id": FEATURE_SCHEMA_ID_V3,
        "feature_schema_version": FEATURE_SCHEMA_VERSION_V3,
        "source_dataset_hash": source_dataset_hash,
        "source_dataset_id": source_dataset_id,
        "universe_authority_hash": universe_authority_hash,
    }
    digest = derived_dataset_hash(FEATURE_ROW_SCHEMA, metadata, tuple(rows))
    return FeatureDatasetV1(
        dataset_id=f"dset_{digest[:24]}",
        dataset_hash=digest,
        candidate_id=candidate_id,
        source_dataset_id=source_dataset_id,
        source_dataset_hash=source_dataset_hash,
        calendar_hash=calendar_hash,
        corporate_action_authority_hash=corporate_action_authority_hash,
        universe_authority_hash=universe_authority_hash,
        rows=tuple(rows),
        feature_schema_id=FEATURE_SCHEMA_ID_V3,
        feature_schema_version=FEATURE_SCHEMA_VERSION_V3,
    )


def pool_feature_datasets(
    datasets: Sequence[FeatureDatasetV1],
    *,
    candidate_id: str,
) -> FeatureDatasetV1:
    """Combine per-instrument feature datasets into one pooled cross-sectional dataset."""
    if not datasets:
        raise ModelingError(
            ModelingFailureCode.DATASET_INTEGRITY_INVALID,
            "a pooled feature dataset needs at least one constituent",
        )
    calendar_hashes = sorted({d.calendar_hash for d in datasets})
    # Each constituent binds a universe snapshot over its own first/last session, so the 50 governed
    # NIFTY acquisitions carry six distinct hashes for one membership list. Requiring a single shared
    # hash would reject a legitimate pool, so the pooled identity is derived from the constituents --
    # which records exactly which snapshots went in rather than discarding the distinction.
    universe_hash = canonical_sha256(
        {
            "constituents": sorted({d.universe_authority_hash for d in datasets}),
            "schema_id": "quantos.mizan_pooled_universe",
            "schema_version": 1,
        }
    )

    source_id, source_hash = _pooled_identity(
        "source",
        [(d.rows[0].symbol, d.source_dataset_id, d.source_dataset_hash) for d in datasets],
    )
    _, corporate_hash = _pooled_identity(
        "corporate_actions",
        [
            (d.rows[0].symbol, d.source_dataset_id, d.corporate_action_authority_hash)
            for d in datasets
        ],
    )
    calendar_hash = canonical_sha256(
        {
            "constituents": calendar_hashes,
            "schema_id": "quantos.mizan_pooled_calendar",
            "schema_version": 1,
        }
    )

    rows = [
        FeatureRowV1(
            candidate_id=row.candidate_id,
            dataset_id=source_id,
            dataset_hash=source_hash,
            provider_instrument_id=row.provider_instrument_id,
            symbol=row.symbol,
            decision_at=row.decision_at,
            information_cutoff_at=row.information_cutoff_at,
            universe_authority_hash=universe_hash,
            feature_schema_id=row.feature_schema_id,
            feature_schema_version=row.feature_schema_version,
            features=dict(row.features),
            preprocessing_input_hash=row.preprocessing_input_hash,
        )
        for dataset in datasets
        for row in dataset.rows
    ]
    rows.sort(key=lambda row: (row.decision_at, row.provider_instrument_id))
    return _finalize_feature_dataset(
        rows,
        candidate_id=candidate_id,
        source_dataset_id=source_id,
        source_dataset_hash=source_hash,
        calendar_hash=calendar_hash,
        corporate_action_authority_hash=corporate_hash,
        universe_authority_hash=universe_hash,
    )


def pool_label_datasets(
    datasets: Sequence[LabelDatasetV1],
    *,
    candidate_id: str,
    feature_dataset: FeatureDatasetV1,
) -> LabelDatasetV1:
    """Combine per-instrument label datasets, keeping every constituent cost quote hash.

    Labels stay per-instrument work: each one is priced against its own instrument's next open with
    that instrument's own statutory costs. Pooling changes which rows are evaluated together, never
    how any single row was priced.
    """
    if not datasets:
        raise ModelingError(
            ModelingFailureCode.DATASET_INTEGRITY_INVALID,
            "a pooled label dataset needs at least one constituent",
        )
    source_id, source_hash = _pooled_identity(
        "labels",
        [(d.rows[0].symbol, d.source_dataset_id, d.source_dataset_hash) for d in datasets],
    )
    horizons = {d.label_horizon_sessions for d in datasets}
    if len(horizons) != 1:
        raise ModelingError(
            ModelingFailureCode.LABEL_HORIZON_INVALID,
            "pooled constituents must share one label horizon",
        )
    horizon = horizons.pop()
    rows: list[LabelRowV1] = [row for dataset in datasets for row in dataset.rows]
    rows.sort(key=lambda row: (row.decision_at, row.symbol))
    quote_hashes = tuple(sorted({h for d in datasets for h in d.cost_quote_hashes}))

    metadata = {
        "candidate_id": candidate_id,
        "cost_quote_hashes": list(quote_hashes),
        "execution_contract_version": "next-open-v1",
        "feature_dataset_hash": feature_dataset.dataset_hash,
        "feature_dataset_id": feature_dataset.dataset_id,
        "label_contract_version": label_contract_version_for(horizon),
        "source_dataset_hash": source_hash,
        "source_dataset_id": source_id,
    }
    digest = derived_dataset_hash(LABEL_ROW_SCHEMA, metadata, tuple(rows))
    return LabelDatasetV1(
        dataset_id=f"dset_{digest[:24]}",
        dataset_hash=digest,
        candidate_id=candidate_id,
        source_dataset_id=source_id,
        source_dataset_hash=source_hash,
        feature_dataset_id=feature_dataset.dataset_id,
        feature_dataset_hash=feature_dataset.dataset_hash,
        cost_quote_hashes=quote_hashes,
        rows=tuple(rows),
        label_horizon_sessions=horizon,
    )
