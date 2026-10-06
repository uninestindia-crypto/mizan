"""Pure parsing and quality validation for Upstox market-data payloads."""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta, timezone
from datetime import time as wall_time
from decimal import Decimal, InvalidOperation
from typing import Any

from quant_system.core.domain import PriceBar, Quote
from quant_system.data.market_data import (
    FindingDisposition,
    FindingSeverity,
    HistoricalDailyRequest,
    PointInTimeBar,
    QualityCode,
    QualityFinding,
    SourceStatus,
)
from quant_system.data.market_data_evidence import canonical_sha256

INDIA_STANDARD_TIME = timezone(timedelta(hours=5, minutes=30))
NSE_CASH_CLOSE = wall_time(hour=15, minute=30)


class ProviderMalformedBody(ValueError):
    pass


class ProviderSchemaDrift(ValueError):
    pass


class ProviderQuoteUnavailable(Exception):
    """A well-formed quote reply that carries no priced two-sided market.

    Deliberately not a `ValueError`: `parse_quote_payload` converts every `ValueError` raised while
    reading a reply into `ProviderSchemaDrift`, and an empty side of the book after hours is not a
    change in the provider's contract. Keeping the two apart stops a closed market from looking like
    drift, which would send someone to "update the provider contract" every evening.
    """


@dataclass(frozen=True, slots=True)
class QualityBlockedError(Exception):
    findings: tuple[QualityFinding, ...]


def decode_historical_candles(body: bytes) -> list[Any]:
    """Decode the provider envelope while rejecting malformed or changed shapes."""
    if body.lstrip().startswith(b"<"):
        raise ProviderMalformedBody("provider returned HTML")
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as error:
        raise ProviderMalformedBody("provider returned malformed JSON") from error
    if not isinstance(payload, dict) or payload.get("status") != "success":
        raise ProviderSchemaDrift("provider success envelope changed")
    provider_data = payload.get("data")
    if not isinstance(provider_data, dict):
        raise ProviderSchemaDrift("provider data object is absent")
    candles = provider_data.get("candles")
    if not isinstance(candles, list):
        raise ProviderSchemaDrift("provider candles array is absent")
    return candles


def parse_candle_rows(
    candles: list[Any],
    request: HistoricalDailyRequest,
    acquired_at: datetime,
) -> tuple[tuple[PointInTimeBar, ...], tuple[QualityFinding, ...]]:
    """Parse all rows, report every quality category, and canonicalize order."""
    records: list[PointInTimeBar] = []
    quality_keys: dict[QualityCode, list[str]] = {}
    for index, row in enumerate(candles):
        try:
            record = _parse_candle_row(
                row,
                source_row_index=index,
                instrument_key=request.instrument_key,
                symbol=request.symbol,
                acquired_at=acquired_at,
            )
        except ProviderSchemaDrift:
            raise
        except ValueError as error:
            code = _quality_code_for_error(error)
            quality_keys.setdefault(code, []).append(f"row:{index}")
            continue
        records.append(record)

        if not request.from_date <= record.exchange_date <= request.to_date:
            quality_keys.setdefault(QualityCode.OUT_OF_REQUEST_RANGE, []).append(
                _record_key(record)
            )

    duplicate_keys = _duplicate_record_keys(records)
    if duplicate_keys:
        quality_keys[QualityCode.DUPLICATE_KEY] = list(duplicate_keys)
    if request.expected_sessions is not None:
        expected_sessions = set(request.expected_sessions)
        unexpected_sessions = sorted(
            {record.exchange_date for record in records} - expected_sessions
        )
        if unexpected_sessions:
            quality_keys[QualityCode.NON_SESSION_DATE] = [
                session.isoformat() for session in unexpected_sessions
            ]
    if quality_keys:
        raise QualityBlockedError(_blocking_findings(quality_keys))

    is_ascending = all(
        left.event_at < right.event_at for left, right in zip(records, records[1:], strict=False)
    )
    sorted_records = tuple(sorted(records, key=_record_order))
    if is_ascending:
        return sorted_records, ()
    return sorted_records, (_reverse_order_finding(records, sorted_records),)


def parse_compatibility_candles(
    candles: Sequence[Sequence[Any]],
    *,
    symbol: str,
    acquired_at: datetime,
) -> list[PriceBar]:
    """Parse legacy caller rows strictly without quality repair."""
    records = tuple(
        _parse_candle_row(
            row,
            source_row_index=index,
            instrument_key="NSE_EQ|UNKNOWN000000",
            symbol=symbol,
            acquired_at=acquired_at,
        )
        for index, row in enumerate(candles)
    )
    return [record.to_price_bar() for record in sorted(records, key=_record_order)]


def get_range_findings(
    request: HistoricalDailyRequest,
    records: tuple[PointInTimeBar, ...],
) -> tuple[SourceStatus, tuple[QualityFinding, ...]]:
    if request.expected_sessions is not None:
        missing_sessions = sorted(
            set(request.expected_sessions) - {record.exchange_date for record in records}
        )
        if not missing_sessions:
            return SourceStatus.COMPLETE, ()
        return SourceStatus.PARTIAL, (
            _range_unavailable_finding(
                request,
                records,
                missing_sessions=missing_sessions,
            ),
        )
    start_gap = (records[0].exchange_date - request.from_date).days
    end_gap = (request.to_date - records[-1].exchange_date).days
    if start_gap <= 7 and end_gap <= 7:
        return SourceStatus.COMPLETE, ()
    return SourceStatus.PARTIAL, (_range_unavailable_finding(request, records),)


def _range_unavailable_finding(
    request: HistoricalDailyRequest,
    records: tuple[PointInTimeBar, ...],
    *,
    missing_sessions: list[date] | None = None,
) -> QualityFinding:
    missing_keys = (
        tuple(f"missing_session:{session.isoformat()}" for session in missing_sessions)
        if missing_sessions
        else ()
    )
    return QualityFinding(
        code=QualityCode.PROVIDER_RANGE_UNAVAILABLE,
        severity=FindingSeverity.BLOCKING,
        count=max(1, len(missing_keys)),
        disposition=FindingDisposition.NONE,
        record_keys=(
            f"requested:{request.from_date.isoformat()}:{request.to_date.isoformat()}",
            f"received:{records[0].exchange_date.isoformat()}:{records[-1].exchange_date.isoformat()}",
            *missing_keys,
        ),
    )


def get_authority_findings(request: HistoricalDailyRequest) -> tuple[QualityFinding, ...]:
    findings: list[QualityFinding] = []
    if request.calendar is None or request.expected_sessions is None:
        findings.append(_unresolved_finding(QualityCode.CALENDAR_UNRESOLVED))
    if request.corporate_action_authority is None:
        findings.append(_unresolved_finding(QualityCode.CORPORATE_ACTION_AUTHORITY_UNRESOLVED))
    if request.historical_universe_authority is None:
        findings.append(_unresolved_finding(QualityCode.HISTORICAL_UNIVERSE_AUTHORITY_UNRESOLVED))
    return tuple(findings)


def parse_quote_payload(body: bytes, *, instrument_key: str, symbol: str) -> Quote:
    """Parse the V2 snapshot for one instrument without manufacturing bid/ask values.

    The request carries the instrument key (`NSE_EQ|INE009A01021`) but the provider keys `data` by
    the symbol form (`NSE_EQ:INFY`) and repeats the instrument key inside the entry as
    `instrument_token`; see `_select_quote_entry` for how an entry is chosen and bound to the request.

    Raises `ProviderSchemaDrift` for a malformed or mismatched reply and `ProviderQuoteUnavailable`
    for a well-formed one with no priced two-sided market: the `{price: 0.0, quantity: 0}` best bid
    the provider returns after hours, or a priced level with nothing resting at it. `Quote` cannot
    represent a missing side, and a zero would give a mid of half the ask, so it is refused.
    """
    try:
        payload = json.loads(body.decode("utf-8"))
        quote_data = _select_quote_entry(
            payload["data"], instrument_key=instrument_key, symbol=symbol
        )
        buy_level = quote_data["depth"]["buy"][0]
        sell_level = quote_data["depth"]["sell"][0]
        timestamp = _parse_timestamp(quote_data["timestamp"]).astimezone(UTC)
        bid = _parse_decimal(buy_level["price"], "bid")
        ask = _parse_decimal(sell_level["price"], "ask")
        bid_size = _parse_nonnegative_integer(buy_level["quantity"], "bid_size")
        ask_size = _parse_nonnegative_integer(sell_level["quantity"], "ask_size")
        last_price = _parse_decimal(quote_data["last_price"], "last_price")
    except ProviderSchemaDrift:
        raise
    except (
        KeyError,
        IndexError,
        TypeError,
        ValueError,
        RecursionError,
    ) as error:
        raise ProviderSchemaDrift("provider quote shape changed") from error
    if min(bid, ask, last_price) < 0:
        raise ProviderSchemaDrift("provider quote carries a negative price")
    if min(bid, ask, last_price) == 0 or bid_size == 0 or ask_size == 0:
        raise ProviderQuoteUnavailable("provider quote has no priced two-sided market")
    if ask < bid:
        raise ProviderSchemaDrift("provider quote is crossed")
    return Quote(
        symbol=symbol,
        timestamp=timestamp,
        bid=bid,
        ask=ask,
        bid_size=bid_size,
        ask_size=ask_size,
        last_price=last_price,
    )


def _select_quote_entry(
    provider_data: Any,
    *,
    instrument_key: str,
    symbol: str,
) -> dict[str, Any]:
    """Pick the `data` entry for `instrument_key` and refuse one that is not provably that instrument.

    Looked up by the instrument key, then by `<segment>:<symbol>` (the segment is the key's prefix,
    so `NSE_EQ|INE009A01021` + `INFY` finds `NSE_EQ:INFY`), then by the one entry whose
    `instrument_token` equals the key. The entry's own `instrument_token` is what binds it to the
    request: when present it must equal `instrument_key`, and an entry found any way other than by the
    instrument key must carry it. A symbol string alone is a label rather than an identity, since a
    symbol can be reused for another ISIN after a corporate event, and the quote would then price the
    wrong security.
    """
    if not isinstance(provider_data, dict):
        raise ProviderSchemaDrift("provider quote data object is absent")
    keyed_by_instrument = provider_data.get(instrument_key)
    entry = keyed_by_instrument
    if entry is None:
        entry = provider_data.get(f"{instrument_key.partition('|')[0]}:{symbol}")
    if entry is None:
        by_token = [
            candidate
            for candidate in provider_data.values()
            if isinstance(candidate, dict) and candidate.get("instrument_token") == instrument_key
        ]
        entry = by_token[0] if len(by_token) == 1 else None
    if not isinstance(entry, dict):
        raise ProviderSchemaDrift("provider quote entry for the requested instrument is absent")
    token = entry.get("instrument_token")
    if token != instrument_key and not (token is None and keyed_by_instrument is not None):
        raise ProviderSchemaDrift("provider quote entry is not for the requested instrument")
    return entry


def _parse_candle_row(
    row: Any,
    *,
    source_row_index: int,
    instrument_key: str,
    symbol: str,
    acquired_at: datetime,
) -> PointInTimeBar:
    if isinstance(row, (str, bytes)) or not isinstance(row, Sequence) or len(row) != 7:
        raise ProviderSchemaDrift("each V3 candle must contain exactly seven fields")
    event_local = _parse_timestamp(row[0])
    exchange_date = event_local.astimezone(INDIA_STANDARD_TIME).date()
    available_local = datetime.combine(exchange_date, NSE_CASH_CLOSE, tzinfo=INDIA_STANDARD_TIME)
    return PointInTimeBar(
        provider_instrument_id=instrument_key,
        symbol=symbol,
        exchange_date=exchange_date,
        event_at=event_local.astimezone(UTC),
        provider_at=None,
        ingested_at=acquired_at,
        available_at=available_local.astimezone(UTC),
        open=_parse_decimal(row[1], "open"),
        high=_parse_decimal(row[2], "high"),
        low=_parse_decimal(row[3], "low"),
        close=_parse_decimal(row[4], "close"),
        volume=_parse_nonnegative_integer(row[5], "volume"),
        open_interest=_parse_nonnegative_integer(row[6], "open_interest"),
        source_row_index=source_row_index,
    )


def _parse_timestamp(value: Any) -> datetime:
    if not isinstance(value, str) or len(value) > 64:
        raise ProviderSchemaDrift("candle timestamp must be a bounded ISO string")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise ValueError("invalid timestamp") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("invalid timestamp")
    return parsed


def _parse_decimal(value: Any, field_name: str) -> Decimal:
    if isinstance(value, bool) or not isinstance(value, (int, float, str, Decimal)):
        raise ProviderSchemaDrift(f"{field_name} must be numeric")
    try:
        parsed = Decimal(str(value))
    except InvalidOperation as error:
        raise ProviderSchemaDrift(f"{field_name} must be numeric") from error
    if not parsed.is_finite():
        raise ValueError(f"{field_name} must be finite")
    return parsed


def _parse_nonnegative_integer(value: Any, field_name: str) -> int:
    parsed = _parse_decimal(value, field_name)
    if parsed != parsed.to_integral_value():
        raise ValueError(f"{field_name} must be an integer")
    integer = int(parsed)
    if integer < 0:
        raise ValueError(f"{field_name} cannot be negative")
    return integer


def _quality_code_for_error(error: ValueError) -> QualityCode:
    message = str(error).lower()
    if "not available at acquisition" in message:
        return QualityCode.NOT_AVAILABLE_AT_ACQUISITION
    if "timestamp" in message:
        return QualityCode.INVALID_TIMESTAMP
    if "volume" in message or "open_interest" in message:
        return QualityCode.INVALID_VOLUME
    return QualityCode.INVALID_OHLC


def _duplicate_record_keys(records: Sequence[PointInTimeBar]) -> tuple[str, ...]:
    counts: dict[tuple[str, date], int] = {}
    for record in records:
        key = (record.provider_instrument_id, record.exchange_date)
        counts[key] = counts.get(key, 0) + 1
    return tuple(
        f"{instrument_id}:{exchange_date.isoformat()}"
        for (instrument_id, exchange_date), count in sorted(counts.items())
        if count > 1
    )


def _blocking_findings(
    quality_keys: dict[QualityCode, list[str]],
) -> tuple[QualityFinding, ...]:
    return tuple(
        QualityFinding(
            code=code,
            severity=FindingSeverity.BLOCKING,
            count=len(keys),
            disposition=FindingDisposition.REJECTED,
            record_keys=tuple(keys),
        )
        for code, keys in sorted(quality_keys.items(), key=lambda item: item[0].value)
    )


def _reverse_order_finding(
    records: Sequence[PointInTimeBar],
    sorted_records: Sequence[PointInTimeBar],
) -> QualityFinding:
    transformation_hash = canonical_sha256(
        {
            "input_order": [record.source_row_index for record in records],
            "output_order": [record.source_row_index for record in sorted_records],
            "rule": "sort by provider instrument, event time, source row index",
        }
    )
    return QualityFinding(
        code=QualityCode.REVERSE_ORDER,
        severity=FindingSeverity.WARNING,
        count=len(records),
        disposition=FindingDisposition.REPAIRED,
        record_keys=tuple(_record_key(record) for record in records),
        repair_rule="SORT_CANONICAL_EVENT_ORDER_V1",
        repair_hash=transformation_hash,
    )


def _unresolved_finding(code: QualityCode) -> QualityFinding:
    return QualityFinding(
        code=code,
        severity=FindingSeverity.BLOCKING,
        count=1,
        disposition=FindingDisposition.NONE,
    )


def _record_order(record: PointInTimeBar) -> tuple[str, datetime, int]:
    return record.provider_instrument_id, record.event_at, record.source_row_index


def _record_key(record: PointInTimeBar) -> str:
    return f"{record.provider_instrument_id}:{record.event_at.isoformat()}"
