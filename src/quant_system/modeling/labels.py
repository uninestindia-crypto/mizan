"""Executable next-session-open labels bound to immutable round-trip costs."""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime
from decimal import ROUND_HALF_EVEN, Decimal, localcontext

from quant_system.data.adjustment_provenance import AdjustmentReference, spans_unresolved
from quant_system.data.evidence_draft import draft_from_historical_acquisition
from quant_system.data.market_data import HistoricalAcquisition, PointInTimeBar
from quant_system.data.market_data_evidence import decimal_text
from quant_system.evidence import EvidenceIntegrityError
from quant_system.modeling.authorities import SessionCalendarV1
from quant_system.modeling.errors import ModelingError, ModelingFailureCode
from quant_system.modeling.rows import (
    EXECUTION_CONTRACT_VERSION_V1,
    LABEL_HORIZON_SESSIONS_V1,
    LABEL_ROW_SCHEMA,
    FeatureDatasetV1,
    FeatureRowV1,
    LabelDatasetV1,
    LabelRowV1,
    RoundTripCostQuoteV1,
    decimal_result,
    derived_dataset_hash,
    label_contract_version_for,
    require_feature_dataset_identity,
)


def build_label_dataset(
    feature_dataset: FeatureDatasetV1,
    acquisition: HistoricalAcquisition,
    calendar: SessionCalendarV1,
    cost_quotes: tuple[RoundTripCostQuoteV1, ...],
    horizon_sessions: int = LABEL_HORIZON_SESSIONS_V1,
    *,
    execution_acquisition: HistoricalAcquisition | None = None,
) -> LabelDatasetV1:
    """Build matured labels, rejecting missing eligible opens or mismatched costs.

    ``horizon_sessions`` counts decision -> entry -> exit, so the default 2 holds for one session.
    The cost quotes supplied must have been priced for the same horizon; a mismatch surfaces as
    ``COST_QUOTE_MISSING`` rather than being silently repriced.

    Corporate actions, and why there are two acquisitions
    ----------------------------------------------------
    ``acquisition`` supplies the prices the **return** is measured on. ``execution_acquisition``
    supplies the prices a fill actually **executes** at, and defaults to ``acquisition`` -- which is
    exactly the previous behaviour when both are the raw provider series.

    They differ when ``acquisition`` is a corporate-action-adjusted derivation
    (``data.adjusted_acquisition.derive_adjusted_acquisition``). A 1:1 bonus halves the quote and
    doubles the share count: the raw ratio says the holder lost 50% and the holder in fact broke
    even. Measuring the label on the adjusted series gets that right. But the *costs* must not be
    quoted on adjusted prices, because NSE charges are not all ad valorem -- a flat DP charge and a
    capped brokerage do not scale with a synthetic price, so an adjusted quote would misstate them.
    So costs stay priced on raw executable opens at the raw notional, and the cost fraction and the
    gross return are both fractions of the same economic position. Nothing is counted twice.

    A window spanning a corporate action **of unknown size** is refused outright. The adjusted
    series cannot correct it -- nothing sized it -- and the raw ratio across it is a fabricated
    return. The row is dropped and its cost quote is recorded as refused rather than unused, so the
    quote-completeness guard still holds.
    """
    if horizon_sessions < LABEL_HORIZON_SESSIONS_V1:
        raise ModelingError(
            ModelingFailureCode.LABEL_HORIZON_INVALID,
            "label horizon cannot be shorter than one held session",
        )
    execution = execution_acquisition if execution_acquisition is not None else acquisition
    _validate_sources(feature_dataset, acquisition, calendar)
    _validate_execution_source(acquisition, execution)
    adjustment = acquisition.manifest.adjustment
    bars_by_date = {record.exchange_date: record for record in acquisition.records}
    execution_bars_by_date = {record.exchange_date: record for record in execution.records}
    quotes_by_key = _index_quotes(cost_quotes)
    rows: list[LabelRowV1] = []
    used_quote_hashes: list[str] = []
    refused_quote_hashes: list[str] = []
    for feature_row in feature_dataset.rows:
        outcome = _build_label(
            feature_row,
            acquisition,
            calendar,
            bars_by_date,
            execution_bars_by_date,
            quotes_by_key,
            horizon_sessions,
            adjustment,
        )
        if outcome is None:
            continue
        label, quote = outcome
        if label is None:
            refused_quote_hashes.append(quote.quote_hash)
            continue
        rows.append(label)
        used_quote_hashes.append(quote.quote_hash)
    if not rows:
        raise ModelingError(
            ModelingFailureCode.INSUFFICIENT_HISTORY,
            "no feature row has a matured two-session label horizon",
        )
    supplied_quote_hashes = Counter(quote.quote_hash for quote in cost_quotes)
    accounted = Counter(used_quote_hashes) + Counter(refused_quote_hashes)
    if accounted != supplied_quote_hashes:
        raise ModelingError(
            ModelingFailureCode.COST_QUOTE_MISMATCH,
            "cost quote set contains an unused or unmatched quote",
        )
    immutable_rows = tuple(rows)
    quote_hashes = tuple(used_quote_hashes)
    unsigned_metadata = {
        "candidate_id": feature_dataset.candidate_id,
        "cost_quote_hashes": list(quote_hashes),
        "execution_contract_version": EXECUTION_CONTRACT_VERSION_V1,
        "feature_dataset_hash": feature_dataset.dataset_hash,
        "feature_dataset_id": feature_dataset.dataset_id,
        "label_contract_version": label_contract_version_for(horizon_sessions),
        "source_dataset_hash": acquisition.manifest.manifest_hash,
        "source_dataset_id": acquisition.manifest.dataset_id,
    }
    dataset_hash = derived_dataset_hash(LABEL_ROW_SCHEMA, unsigned_metadata, immutable_rows)
    return LabelDatasetV1(
        dataset_id=f"dset_{dataset_hash[:24]}",
        dataset_hash=dataset_hash,
        candidate_id=feature_dataset.candidate_id,
        source_dataset_id=acquisition.manifest.dataset_id,
        source_dataset_hash=acquisition.manifest.manifest_hash,
        feature_dataset_id=feature_dataset.dataset_id,
        feature_dataset_hash=feature_dataset.dataset_hash,
        cost_quote_hashes=quote_hashes,
        rows=immutable_rows,
        label_horizon_sessions=horizon_sessions,
    )


def _validate_sources(
    feature_dataset: FeatureDatasetV1,
    acquisition: HistoricalAcquisition,
    calendar: SessionCalendarV1,
) -> None:
    require_feature_dataset_identity(feature_dataset)
    try:
        draft_from_historical_acquisition(acquisition)
    except EvidenceIntegrityError as error:
        raise ModelingError(
            ModelingFailureCode.DATASET_INTEGRITY_INVALID,
            str(error),
        ) from error
    manifest = acquisition.manifest
    if (
        feature_dataset.source_dataset_id != manifest.dataset_id
        or feature_dataset.source_dataset_hash != manifest.manifest_hash
    ):
        raise ModelingError(
            ModelingFailureCode.DATASET_INTEGRITY_INVALID,
            "feature dataset does not bind the supplied acquisition",
        )
    if manifest.calendar != calendar.reference or feature_dataset.calendar_hash != (
        calendar.reference.content_hash
    ):
        raise ModelingError(
            ModelingFailureCode.CALENDAR_AUTHORITY_MISMATCH,
            "label calendar does not match feature and acquisition evidence",
        )
    corporate_authority = manifest.corporate_action_authority
    universe_authority = manifest.historical_universe_authority
    if (
        corporate_authority is None
        or feature_dataset.corporate_action_authority_hash != corporate_authority.content_hash
        or universe_authority is None
        or feature_dataset.universe_authority_hash != universe_authority.content_hash
    ):
        raise ModelingError(
            ModelingFailureCode.DATASET_INTEGRITY_INVALID,
            "feature authorities do not bind the supplied acquisition",
        )
    for row in feature_dataset.rows:
        if (
            row.provider_instrument_id != manifest.provider_instrument_id
            or row.symbol != manifest.symbol
            or row.universe_authority_hash != universe_authority.content_hash
        ):
            raise ModelingError(
                ModelingFailureCode.DATASET_INTEGRITY_INVALID,
                "feature row instrument or authority does not bind the acquisition",
                offending_record_key=row.record_key,
            )


def _index_quotes(
    quotes: tuple[RoundTripCostQuoteV1, ...],
) -> dict[tuple[str, datetime, datetime], RoundTripCostQuoteV1]:
    indexed: dict[tuple[str, datetime, datetime], RoundTripCostQuoteV1] = {}
    for quote in quotes:
        key = quote.provider_instrument_id, quote.entry_at, quote.exit_at
        if key in indexed:
            raise ModelingError(
                ModelingFailureCode.COST_QUOTE_MISMATCH,
                "duplicate cost quote for one executable label",
            )
        indexed[key] = quote
    return indexed


def _validate_execution_source(
    acquisition: HistoricalAcquisition, execution: HistoricalAcquisition
) -> None:
    """The two acquisitions must be the same instrument and, when derived, actually related.

    Pairing an adjusted series for one symbol with raw bars for another would produce a return and
    a cost that describe different instruments -- the failure mode that a Red Team recheck already
    found once on this codebase, where a symbol was bound by map key rather than by each bar's own
    identity.
    """
    if execution is acquisition:
        return
    manifest, source = acquisition.manifest, execution.manifest
    if (
        manifest.symbol != source.symbol
        or manifest.provider_instrument_id != source.provider_instrument_id
    ):
        raise ModelingError(
            ModelingFailureCode.DATASET_INTEGRITY_INVALID,
            "execution acquisition is a different instrument from the measured acquisition",
        )
    adjustment = manifest.adjustment
    if adjustment is None:
        raise ModelingError(
            ModelingFailureCode.DATASET_INTEGRITY_INVALID,
            "a separate execution acquisition is only meaningful for an adjusted measured series",
        )
    if adjustment.source_manifest_hash != source.manifest_hash:
        raise ModelingError(
            ModelingFailureCode.DATASET_INTEGRITY_INVALID,
            "measured series was not derived from the supplied execution acquisition",
        )
    for record in execution.records:
        if (
            record.symbol != source.symbol
            or record.provider_instrument_id != source.provider_instrument_id
        ):
            raise ModelingError(
                ModelingFailureCode.DATASET_INTEGRITY_INVALID,
                "execution bar does not carry the acquisition's own instrument identity",
                offending_record_key=(
                    f"{record.symbol}:{record.exchange_date.isoformat()}:{record.source_row_index}"
                ),
            )


def _build_label(
    feature_row: FeatureRowV1,
    acquisition: HistoricalAcquisition,
    calendar: SessionCalendarV1,
    bars_by_date: dict[date, PointInTimeBar],
    execution_bars_by_date: dict[date, PointInTimeBar],
    quotes_by_key: dict[tuple[str, datetime, datetime], RoundTripCostQuoteV1],
    horizon_sessions: int,
    adjustment: AdjustmentReference | None,
) -> tuple[LabelRowV1 | None, RoundTripCostQuoteV1] | None:
    ordinal = calendar.ordinal_for_close(feature_row.decision_at)
    if ordinal is None:
        raise ModelingError(
            ModelingFailureCode.CALENDAR_AUTHORITY_MISMATCH,
            "feature decision is not a calendar session close",
            offending_record_key=feature_row.record_key,
        )
    if ordinal + horizon_sessions >= len(calendar.sessions):
        return None
    entry_session = calendar.sessions[ordinal + 1]
    exit_session = calendar.sessions[ordinal + horizon_sessions]
    if exit_session.exchange_date > acquisition.manifest.received_end:
        return None
    entry_bar = bars_by_date.get(entry_session.exchange_date)
    if entry_bar is None:
        raise ModelingError(
            ModelingFailureCode.ELIGIBLE_OPEN_MISSING,
            f"first eligible open is missing for {entry_session.exchange_date.isoformat()}",
            offending_record_key=feature_row.record_key,
        )
    exit_bar = bars_by_date.get(exit_session.exchange_date)
    if exit_bar is None:
        raise ModelingError(
            ModelingFailureCode.ELIGIBLE_OPEN_MISSING,
            f"following eligible open is missing for {exit_session.exchange_date.isoformat()}",
            offending_record_key=feature_row.record_key,
        )
    entry_fill = execution_bars_by_date.get(entry_session.exchange_date)
    exit_fill = execution_bars_by_date.get(exit_session.exchange_date)
    if entry_fill is None or exit_fill is None:
        raise ModelingError(
            ModelingFailureCode.ELIGIBLE_OPEN_MISSING,
            "executable open is missing from the execution acquisition",
            offending_record_key=feature_row.record_key,
        )
    key = feature_row.provider_instrument_id, entry_session.open_at, exit_session.open_at
    quote = quotes_by_key.get(key)
    if quote is None:
        raise ModelingError(
            ModelingFailureCode.COST_QUOTE_MISSING,
            "no immutable cost quote matches the executable label",
            offending_record_key=feature_row.record_key,
        )
    _validate_quote(feature_row, entry_fill, exit_fill, quote)
    if spans_unresolved(
        adjustment,
        after=entry_session.exchange_date,
        through=exit_session.exchange_date,
    ):
        # A corporate action of unknown size sits inside the holding window. The adjusted series
        # cannot correct it, because nothing sized it, and the raw ratio across it is a fabricated
        # return -- so no label is produced. The quote is returned so the caller can account for it
        # as refused rather than as silently unused.
        return None, quote
    return _row_from_quote(feature_row, entry_bar, exit_bar, entry_fill, quote), quote


def _validate_quote(
    feature_row: FeatureRowV1,
    entry_bar: PointInTimeBar,
    exit_bar: PointInTimeBar,
    quote: RoundTripCostQuoteV1,
) -> None:
    if (
        quote.symbol != feature_row.symbol
        or quote.provider_instrument_id != feature_row.provider_instrument_id
        or quote.entry_price != entry_bar.open
        or quote.exit_price != exit_bar.open
        or quote.execution_contract_version != EXECUTION_CONTRACT_VERSION_V1
    ):
        raise ModelingError(
            ModelingFailureCode.COST_QUOTE_MISMATCH,
            "cost quote does not bind the exact instrument, prices, and execution contract",
            offending_record_key=feature_row.record_key,
        )


def _row_from_quote(
    feature_row: FeatureRowV1,
    entry_bar: PointInTimeBar,
    exit_bar: PointInTimeBar,
    entry_fill: PointInTimeBar,
    quote: RoundTripCostQuoteV1,
) -> LabelRowV1:
    """One matured label.

    ``entry_bar``/``exit_bar`` are the measured series -- adjusted when one was supplied, raw
    otherwise -- and give the gross return the holder actually experienced across any corporate
    action in the window. ``entry_fill`` is the executable raw bar, and gives the rupee notional the
    quoted costs were priced against. Dividing the cost by the *adjusted* notional would rescale a
    real rupee charge by a synthetic price ratio; dividing the return by the raw prices would ignore
    the entitlement. Both fractions are of the same economic position, so nothing double-counts.
    """
    with localcontext() as context:
        context.prec = 50
        context.rounding = ROUND_HALF_EVEN
        entry_notional = entry_fill.open * quote.quantity
        gross_return = (exit_bar.open - entry_bar.open) / entry_bar.open
        total_cost = sum(
            (money.amount_decimal for money in quote.component_costs.values()),
            start=Decimal(0),
        )
        net_return = gross_return - total_cost / entry_notional
        gross_return_text = decimal_result(gross_return)
        net_return_text = decimal_result(net_return)
    return LabelRowV1(
        candidate_id=feature_row.candidate_id,
        symbol=feature_row.symbol,
        decision_at=feature_row.decision_at,
        order_at=feature_row.decision_at,
        entry_at=quote.entry_at,
        exit_at=quote.exit_at,
        entry_price=decimal_text(entry_bar.open),
        exit_price=decimal_text(exit_bar.open),
        gross_return=gross_return_text,
        component_costs=quote.component_costs,
        net_return=net_return_text,
        target="UP" if Decimal(net_return_text) > 0 else "DOWN",
        cost_rule_ids=quote.cost_rule_ids,
        execution_contract_version=quote.execution_contract_version,
    )
