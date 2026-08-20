"""Executable next-session-open labels bound to immutable round-trip costs."""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime
from decimal import ROUND_HALF_EVEN, Decimal, localcontext

from quant_system.data.evidence_draft import draft_from_historical_acquisition
from quant_system.data.market_data import HistoricalAcquisition, PointInTimeBar
from quant_system.data.market_data_evidence import decimal_text
from quant_system.evidence import EvidenceIntegrityError
from quant_system.modeling.authorities import SessionCalendarV1
from quant_system.modeling.errors import ModelingError, ModelingFailureCode
from quant_system.modeling.rows import (
    EXECUTION_CONTRACT_VERSION_V1,
    LABEL_CONTRACT_VERSION_V1,
    LABEL_ROW_SCHEMA,
    FeatureDatasetV1,
    FeatureRowV1,
    LabelDatasetV1,
    LabelRowV1,
    RoundTripCostQuoteV1,
    decimal_result,
    derived_dataset_hash,
    require_feature_dataset_identity,
)


def build_label_dataset(
    feature_dataset: FeatureDatasetV1,
    acquisition: HistoricalAcquisition,
    calendar: SessionCalendarV1,
    cost_quotes: tuple[RoundTripCostQuoteV1, ...],
) -> LabelDatasetV1:
    """Build matured labels, rejecting missing eligible opens or mismatched costs."""
    _validate_sources(feature_dataset, acquisition, calendar)
    bars_by_date = {record.exchange_date: record for record in acquisition.records}
    quotes_by_key = _index_quotes(cost_quotes)
    rows: list[LabelRowV1] = []
    used_quote_hashes: list[str] = []
    for feature_row in feature_dataset.rows:
        label_and_quote = _build_label(
            feature_row,
            acquisition,
            calendar,
            bars_by_date,
            quotes_by_key,
        )
        if label_and_quote is None:
            continue
        label, quote = label_and_quote
        rows.append(label)
        used_quote_hashes.append(quote.quote_hash)
    if not rows:
        raise ModelingError(
            ModelingFailureCode.INSUFFICIENT_HISTORY,
            "no feature row has a matured two-session label horizon",
        )
    supplied_quote_hashes = Counter(quote.quote_hash for quote in cost_quotes)
    if Counter(used_quote_hashes) != supplied_quote_hashes:
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
        "label_contract_version": LABEL_CONTRACT_VERSION_V1,
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


def _build_label(
    feature_row: FeatureRowV1,
    acquisition: HistoricalAcquisition,
    calendar: SessionCalendarV1,
    bars_by_date: dict[date, PointInTimeBar],
    quotes_by_key: dict[tuple[str, datetime, datetime], RoundTripCostQuoteV1],
) -> tuple[LabelRowV1, RoundTripCostQuoteV1] | None:
    ordinal = calendar.ordinal_for_close(feature_row.decision_at)
    if ordinal is None:
        raise ModelingError(
            ModelingFailureCode.CALENDAR_AUTHORITY_MISMATCH,
            "feature decision is not a calendar session close",
            offending_record_key=feature_row.record_key,
        )
    if ordinal + 2 >= len(calendar.sessions):
        return None
    entry_session = calendar.sessions[ordinal + 1]
    exit_session = calendar.sessions[ordinal + 2]
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
    key = feature_row.provider_instrument_id, entry_session.open_at, exit_session.open_at
    quote = quotes_by_key.get(key)
    if quote is None:
        raise ModelingError(
            ModelingFailureCode.COST_QUOTE_MISSING,
            "no immutable cost quote matches the executable label",
            offending_record_key=feature_row.record_key,
        )
    _validate_quote(feature_row, entry_bar, exit_bar, quote)
    return _row_from_quote(feature_row, entry_bar, exit_bar, quote), quote


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
    quote: RoundTripCostQuoteV1,
) -> LabelRowV1:
    with localcontext() as context:
        context.prec = 50
        context.rounding = ROUND_HALF_EVEN
        entry_notional = entry_bar.open * quote.quantity
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
