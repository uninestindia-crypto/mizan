"""Deterministic governed-market fixtures shared by Slice 3 tests."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta, timezone
from decimal import Decimal

from quant_system.data.market_data import (
    AuthorityReference,
    HistoricalAcquisition,
    HistoricalDailyRequest,
    PointInTimeBar,
    SourceStatus,
    create_dataset_manifest,
)
from quant_system.modeling import (
    ExchangeSessionV1,
    HistoricalUniverseSnapshotV1,
    MoneyV1,
    RoundTripCostQuoteV1,
    SessionCalendarV1,
)

INSTRUMENT_KEY = "NSE_EQ|INE009A01021"
SYMBOL = "INFY"
ACQUIRED_AT = datetime(2025, 4, 1, 12, 0, tzinfo=UTC)
IST = timezone(timedelta(hours=5, minutes=30), name="Asia/Kolkata")


def business_dates(count: int, *, start: date = date(2025, 1, 2)) -> tuple[date, ...]:
    dates: list[date] = []
    current = start
    while len(dates) < count:
        if current.weekday() < 5:
            dates.append(current)
        current += timedelta(days=1)
    return tuple(dates)


def governed_calendar(count: int = 35) -> SessionCalendarV1:
    sessions = tuple(
        ExchangeSessionV1(
            exchange_date=session_date,
            open_at=datetime.combine(session_date, time(9, 15), IST),
            close_at=datetime.combine(session_date, time(15, 30), IST),
        )
        for session_date in business_dates(count)
    )
    return SessionCalendarV1.create("nse-cash", "2025-v1", sessions)


def governed_universe(
    *,
    members: tuple[str, ...] = (INSTRUMENT_KEY,),
    publication_date: date = date(2024, 12, 20),
) -> HistoricalUniverseSnapshotV1:
    return HistoricalUniverseSnapshotV1.create(
        authority_id="nifty-large-cap-history",
        source_url="https://example.test/nse/universe",
        publication_date=publication_date,
        effective_from=date(2025, 1, 1),
        effective_to=date(2025, 12, 31),
        version="2025-v1",
        provider_instrument_ids=members,
    )


def governed_acquisition(
    *,
    count: int = 35,
    calendar: SessionCalendarV1 | None = None,
    universe: HistoricalUniverseSnapshotV1 | None = None,
    corporate_authority: bool = True,
    delayed_source_index: int | None = None,
    omitted_source_indexes: frozenset[int] = frozenset(),
    open_overrides: dict[int, Decimal] | None = None,
    close_overrides: dict[int, Decimal] | None = None,
) -> HistoricalAcquisition:
    active_calendar = calendar or governed_calendar(count)
    active_universe = universe or governed_universe()
    sessions = active_calendar.sessions[:count]
    active_open_overrides = open_overrides or {}
    overrides = close_overrides or {}
    records: list[PointInTimeBar] = []
    first_feature_close = sessions[20].close_at
    for index, session in enumerate(sessions):
        if index in omitted_source_indexes:
            continue
        open_price = active_open_overrides.get(index, Decimal(100 + index))
        close_price = overrides.get(index, open_price + Decimal("0.5"))
        available_at = session.close_at
        if index == delayed_source_index:
            available_at = first_feature_close + timedelta(minutes=1)
        records.append(
            PointInTimeBar(
                provider_instrument_id=INSTRUMENT_KEY,
                symbol=SYMBOL,
                exchange_date=session.exchange_date,
                event_at=datetime.combine(session.exchange_date, time(0), IST),
                provider_at=None,
                ingested_at=ACQUIRED_AT,
                available_at=available_at,
                open=open_price,
                high=max(open_price + Decimal("2"), close_price),
                low=min(open_price - Decimal("1"), close_price),
                close=close_price,
                volume=250_000 + index,
                open_interest=0,
                source_row_index=index,
            )
        )
    corporate = _corporate_authority() if corporate_authority else None
    request = HistoricalDailyRequest(
        instrument_key=INSTRUMENT_KEY,
        symbol=SYMBOL,
        from_date=sessions[0].exchange_date,
        to_date=sessions[-1].exchange_date,
        request_id="req-modeling-fixture",
        calendar=active_calendar.reference,
        expected_sessions=tuple(session.exchange_date for session in sessions),
        corporate_action_authority=corporate,
        historical_universe_authority=active_universe.authority,
    )
    immutable_records = tuple(records)
    manifest = create_dataset_manifest(
        request,
        immutable_records,
        acquired_at=ACQUIRED_AT,
        raw_response_hash="d" * 64,
        provider_request_id="provider-modeling-fixture",
        source_status=SourceStatus.COMPLETE,
        quality_findings=(),
    )
    return HistoricalAcquisition(manifest=manifest, records=immutable_records)


def round_trip_cost_quotes(
    acquisition: HistoricalAcquisition,
    calendar: SessionCalendarV1,
    *,
    cost: Decimal,
) -> tuple[RoundTripCostQuoteV1, ...]:
    bars = {record.exchange_date: record for record in acquisition.records}
    quotes: list[RoundTripCostQuoteV1] = []
    for ordinal in range(20, len(calendar.sessions) - 2):
        entry_session = calendar.sessions[ordinal + 1]
        exit_session = calendar.sessions[ordinal + 2]
        if entry_session.exchange_date not in bars or exit_session.exchange_date not in bars:
            continue
        entry_bar = bars[entry_session.exchange_date]
        exit_bar = bars[exit_session.exchange_date]
        quotes.append(
            RoundTripCostQuoteV1(
                provider_instrument_id=entry_bar.provider_instrument_id,
                symbol=entry_bar.symbol,
                entry_at=entry_session.open_at,
                exit_at=exit_session.open_at,
                entry_price=entry_bar.open,
                exit_price=exit_bar.open,
                quantity=1,
                component_costs={"all_in": MoneyV1(cost, "INR")},
                cost_rule_ids=("nse-test-v1",),
                cost_rule_set_hash="e" * 64,
                execution_contract_version="next-open-v1",
            )
        )
    return tuple(quotes)


def _corporate_authority() -> AuthorityReference:
    return AuthorityReference(
        authority_id="nse-corporate-actions",
        source_url="https://example.test/nse/corporate-actions",
        publication_date=date(2024, 12, 20),
        effective_from=date(2025, 1, 1),
        effective_to=date(2025, 12, 31),
        version="2025-v1",
        content_hash="c" * 64,
    )
