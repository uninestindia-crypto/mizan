"""Behavior tests for strict Upstox V3 daily acquisition."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from typing import Any

import pytest

from quant_system.data.market_data import (
    AcquisitionFailureCode,
    AuthorityReference,
    CalendarReference,
    DatasetStatus,
    HistoricalAcquisition,
    HistoricalAcquisitionFailure,
    HistoricalDailyRequest,
    QualityCode,
    SourceStatus,
)
from quant_system.data.upstox import UpstoxClient, UpstoxClientDependencies
from quant_system.data.upstox_http import (
    HttpResponse,
    HttpTransport,
    ResponseTooLarge,
    RetryPolicy,
    TransportConnectionError,
    TransportTimeout,
    UpstoxClientConfig,
)

FIXED_ACQUISITION_TIME = datetime(2025, 1, 4, 12, 0, tzinfo=UTC)
INFY_INSTRUMENT_KEY = "NSE_EQ|INE009A01021"


@dataclass(frozen=True, slots=True)
class CapturedRequest:
    url: str
    headers: dict[str, str]
    timeout_seconds: float
    max_response_bytes: int


@dataclass(slots=True)
class StubHttpTransport:
    response: HttpResponse | Exception
    requests: list[CapturedRequest] = field(default_factory=list)

    def get(
        self,
        url: str,
        *,
        headers: dict[str, str],
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> HttpResponse:
        self.requests.append(
            CapturedRequest(
                url=url,
                headers=headers,
                timeout_seconds=timeout_seconds,
                max_response_bytes=max_response_bytes,
            )
        )
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


@dataclass(slots=True)
class SequenceHttpTransport:
    responses: list[HttpResponse | Exception]
    requests: list[CapturedRequest] = field(default_factory=list)

    def get(
        self,
        url: str,
        *,
        headers: dict[str, str],
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> HttpResponse:
        self.requests.append(
            CapturedRequest(
                url=url,
                headers=headers,
                timeout_seconds=timeout_seconds,
                max_response_bytes=max_response_bytes,
            )
        )
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def test_acquisition_uses_v3_daily_path_and_records_point_in_time_manifest() -> None:
    transport = StubHttpTransport(
        _success_response(
            [
                ["2025-01-03T00:00:00+05:30", 1870, 1880, 1860, 1875, 310000, 0],
                ["2025-01-02T00:00:00+05:30", 1850.5, 1860, 1845, 1855.25, 250000, 0],
            ],
            request_id="provider-request-1",
        )
    )
    client = _client(transport)

    outcome = client.acquire_historical_daily(_two_day_request())

    assert isinstance(outcome, HistoricalAcquisition)
    assert transport.requests[0].url.endswith(
        "/v3/historical-candle/NSE_EQ%7CINE009A01021/days/1/2025-01-03/2025-01-02"
    )
    assert outcome.manifest.provider_request_id == "provider-request-1"
    assert outcome.manifest.source_status == SourceStatus.COMPLETE
    assert outcome.manifest.status == DatasetStatus.PARTIAL
    assert outcome.manifest.is_governed_eligible is False
    assert outcome.records[0].event_at == datetime(2025, 1, 1, 18, 30, tzinfo=UTC)
    assert outcome.records[0].available_at == datetime(2025, 1, 2, 10, 0, tzinfo=UTC)
    assert outcome.records[0].ingested_at == FIXED_ACQUISITION_TIME
    assert outcome.records[0].source_row_index == 1
    assert outcome.manifest.row_count == 2


def test_acquisition_reports_reverse_order_and_missing_authorities() -> None:
    transport = StubHttpTransport(
        _success_response(
            [
                ["2025-01-03T00:00:00+05:30", 1870, 1880, 1860, 1875, 310000, 0],
                ["2025-01-02T00:00:00+05:30", 1850.5, 1860, 1845, 1855.25, 250000, 0],
            ]
        )
    )

    outcome = _client(transport).acquire_historical_daily(_two_day_request())

    assert isinstance(outcome, HistoricalAcquisition)
    assert tuple(finding.code for finding in outcome.manifest.quality_findings) == (
        QualityCode.REVERSE_ORDER,
        QualityCode.CALENDAR_UNRESOLVED,
        QualityCode.CORPORATE_ACTION_AUTHORITY_UNRESOLVED,
        QualityCode.HISTORICAL_UNIVERSE_AUTHORITY_UNRESOLVED,
    )


def test_identical_acquisition_inputs_produce_identical_hashes() -> None:
    response = _success_response(
        [
            ["2025-01-02T00:00:00+05:30", 1850.5, 1860, 1845, 1855.25, 250000, 0],
            ["2025-01-03T00:00:00+05:30", 1870, 1880, 1860, 1875, 310000, 0],
        ]
    )
    first = _client(StubHttpTransport(response)).acquire_historical_daily(_two_day_request())
    second = _client(StubHttpTransport(response)).acquire_historical_daily(_two_day_request())

    assert isinstance(first, HistoricalAcquisition)
    assert isinstance(second, HistoricalAcquisition)
    assert first.manifest.canonical_content_hash == second.manifest.canonical_content_hash
    assert first.manifest.manifest_hash == second.manifest.manifest_hash
    assert first.manifest.dataset_id == second.manifest.dataset_id


def test_provider_row_order_changes_the_manifest_hash() -> None:
    ascending = _success_response(
        [
            ["2025-01-02T00:00:00+05:30", 1850.5, 1860, 1845, 1855.25, 250000, 0],
            ["2025-01-03T00:00:00+05:30", 1870, 1880, 1860, 1875, 310000, 0],
        ]
    )
    descending = _success_response(
        [
            ["2025-01-03T00:00:00+05:30", 1870, 1880, 1860, 1875, 310000, 0],
            ["2025-01-02T00:00:00+05:30", 1850.5, 1860, 1845, 1855.25, 250000, 0],
        ]
    )
    first = _client(StubHttpTransport(ascending)).acquire_historical_daily(_two_day_request())
    second = _client(StubHttpTransport(descending)).acquire_historical_daily(_two_day_request())

    assert isinstance(first, HistoricalAcquisition)
    assert isinstance(second, HistoricalAcquisition)
    assert first.manifest.canonical_content_hash != second.manifest.canonical_content_hash
    assert first.manifest.manifest_hash != second.manifest.manifest_hash


def test_duplicate_candle_keys_are_rejected_with_quality_evidence() -> None:
    transport = StubHttpTransport(
        _success_response(
            [
                ["2025-01-02T00:00:00+05:30", 1850, 1860, 1845, 1855, 250000, 0],
                ["2025-01-02T00:00:00+05:30", 1851, 1861, 1846, 1856, 250001, 0],
            ]
        )
    )

    outcome = _client(transport).acquire_historical_daily(_two_day_request())

    assert isinstance(outcome, HistoricalAcquisitionFailure)
    assert outcome.code == AcquisitionFailureCode.DATA_QUALITY_BLOCKED
    assert outcome.quality_findings[0].code == QualityCode.DUPLICATE_KEY


def test_two_daily_rows_for_one_exchange_date_are_rejected_as_duplicates() -> None:
    transport = StubHttpTransport(
        _success_response(
            [
                ["2025-01-02T00:00:00+05:30", 1850, 1860, 1845, 1855, 250000, 0],
                ["2025-01-02T01:00:00+05:30", 1851, 1861, 1846, 1856, 250001, 0],
            ]
        )
    )

    outcome = _client(transport).acquire_historical_daily(_two_day_request())

    assert isinstance(outcome, HistoricalAcquisitionFailure)
    assert outcome.code == AcquisitionFailureCode.DATA_QUALITY_BLOCKED
    assert outcome.quality_findings[0].code == QualityCode.DUPLICATE_KEY


def test_rows_outside_requested_range_are_rejected() -> None:
    transport = StubHttpTransport(
        _success_response(
            [
                ["2025-01-01T00:00:00+05:30", 1850, 1860, 1845, 1855, 250000, 0],
                ["2025-01-04T00:00:00+05:30", 1870, 1880, 1860, 1875, 310000, 0],
            ]
        )
    )

    outcome = _client(transport).acquire_historical_daily(_governed_request())

    assert isinstance(outcome, HistoricalAcquisitionFailure)
    assert outcome.code == AcquisitionFailureCode.DATA_QUALITY_BLOCKED
    assert outcome.quality_findings[0].code.value == "OUT_OF_REQUEST_RANGE"


def test_row_not_available_at_acquisition_is_rejected() -> None:
    transport = StubHttpTransport(
        _success_response([["2025-01-05T00:00:00+05:30", 1850, 1860, 1845, 1855, 250000, 0]])
    )
    request = _governed_request(from_date=date(2025, 1, 5), to_date=date(2025, 1, 5))

    outcome = _client(transport).acquire_historical_daily(request)

    assert isinstance(outcome, HistoricalAcquisitionFailure)
    assert outcome.code == AcquisitionFailureCode.DATA_QUALITY_BLOCKED
    assert outcome.quality_findings[0].code.value == "NOT_AVAILABLE_AT_ACQUISITION"


def test_internal_session_completeness_is_not_inferred_from_endpoints() -> None:
    transport = StubHttpTransport(
        _success_response(
            [
                ["2025-01-01T00:00:00+05:30", 1850, 1860, 1845, 1855, 250000, 0],
                ["2025-01-03T00:00:00+05:30", 1870, 1880, 1860, 1875, 310000, 0],
            ]
        )
    )
    request = _governed_request(
        from_date=date(2025, 1, 1),
        to_date=date(2025, 1, 3),
        expected_sessions=(date(2025, 1, 1), date(2025, 1, 2), date(2025, 1, 3)),
    )

    outcome = _client(transport).acquire_historical_daily(request)

    assert isinstance(outcome, HistoricalAcquisition)
    assert outcome.manifest.status == DatasetStatus.PARTIAL
    assert outcome.manifest.is_governed_eligible is False
    assert QualityCode.PROVIDER_RANGE_UNAVAILABLE in {
        finding.code for finding in outcome.manifest.quality_findings
    }


def test_exact_calendar_session_coverage_can_be_governed_eligible() -> None:
    transport = StubHttpTransport(
        _success_response(
            [
                ["2025-01-02T00:00:00+05:30", 1850, 1860, 1845, 1855, 250000, 0],
                ["2025-01-03T00:00:00+05:30", 1870, 1880, 1860, 1875, 310000, 0],
            ]
        )
    )
    request = _governed_request(
        expected_sessions=(date(2025, 1, 2), date(2025, 1, 3)),
    )

    outcome = _client(transport).acquire_historical_daily(request)

    assert isinstance(outcome, HistoricalAcquisition)
    assert outcome.manifest.status == DatasetStatus.ACCEPTED
    assert outcome.manifest.is_governed_eligible is True
    assert outcome.manifest.quality_findings == ()


def test_provider_date_not_in_versioned_calendar_is_rejected() -> None:
    transport = StubHttpTransport(
        _success_response([["2025-01-03T00:00:00+05:30", 1870, 1880, 1860, 1875, 310000, 0]])
    )
    request = _governed_request(expected_sessions=(date(2025, 1, 2),))

    outcome = _client(transport).acquire_historical_daily(request)

    assert isinstance(outcome, HistoricalAcquisitionFailure)
    assert outcome.code == AcquisitionFailureCode.DATA_QUALITY_BLOCKED
    assert outcome.quality_findings[0].code == QualityCode.NON_SESSION_DATE


@pytest.mark.parametrize(
    ("candle", "expected_code"),
    [
        (
            ["2025-01-02T00:00:00+05:30", 1850, 1800, 1845, 1855, 250000, 0],
            QualityCode.INVALID_OHLC,
        ),
        (
            ["2025-01-02T00:00:00+05:30", 1850, 1860, 1845, 1855, -1, 0],
            QualityCode.INVALID_VOLUME,
        ),
        (
            ["not-a-timestamp", 1850, 1860, 1845, 1855, 250000, 0],
            QualityCode.INVALID_TIMESTAMP,
        ),
    ],
)
# test-allow: no-assertion - checker cannot parse a multiline parametrized signature body.
def test_invalid_provider_values_are_blocked_with_specific_quality_evidence(
    candle: list[Any],
    expected_code: QualityCode,
) -> None:
    outcome = _client(StubHttpTransport(_success_response([candle]))).acquire_historical_daily(
        _two_day_request()
    )

    assert isinstance(outcome, HistoricalAcquisitionFailure)
    assert outcome.code == AcquisitionFailureCode.DATA_QUALITY_BLOCKED
    assert outcome.quality_findings[0].code == expected_code


def test_incomplete_candle_shape_is_provider_schema_drift() -> None:
    transport = StubHttpTransport(
        _success_response([["2025-01-02T00:00:00+05:30", 1850, 1860, 1845, 1855, 250000]])
    )

    outcome = _client(transport).acquire_historical_daily(_two_day_request())

    assert isinstance(outcome, HistoricalAcquisitionFailure)
    assert outcome.code == AcquisitionFailureCode.PROVIDER_SCHEMA_DRIFT


def test_html_success_body_is_provider_malformed() -> None:
    response = HttpResponse(
        status=200,
        body=b"<html><title>gateway</title></html>",
        headers={"content-type": "text/html"},
    )

    outcome = _client(StubHttpTransport(response)).acquire_historical_daily(_two_day_request())

    assert isinstance(outcome, HistoricalAcquisitionFailure)
    assert outcome.code == AcquisitionFailureCode.PROVIDER_MALFORMED


@pytest.mark.parametrize(
    ("status", "expected_code", "retryable"),
    [
        (401, AcquisitionFailureCode.PROVIDER_UNAUTHORIZED, False),
        (429, AcquisitionFailureCode.PROVIDER_RATE_LIMITED, True),
        (500, AcquisitionFailureCode.PROVIDER_UNAVAILABLE, True),
    ],
)
# test-allow: no-assertion - checker cannot parse a multiline parametrized signature body.
def test_http_failure_maps_to_typed_outcome(
    status: int,
    expected_code: AcquisitionFailureCode,
    retryable: bool,
) -> None:
    response = HttpResponse(
        status=status,
        body=json.dumps({"status": "error", "errors": [{"errorCode": "UDAPI_TEST"}]}).encode(),
        headers={"retry-after": "7"},
    )

    outcome = _client(StubHttpTransport(response)).acquire_historical_daily(_two_day_request())

    assert isinstance(outcome, HistoricalAcquisitionFailure)
    assert outcome.code == expected_code
    assert outcome.retryable is retryable
    assert outcome.provider_code == "UDAPI_TEST"
    if status == 429:
        assert outcome.retry_after_seconds == 7


def test_rate_limit_retries_once_using_capped_retry_after_then_succeeds() -> None:
    transport = SequenceHttpTransport(
        responses=[
            HttpResponse(
                status=429,
                body=b'{"status":"error"}',
                headers={"Retry-After": "7"},
            ),
            _success_response(
                [
                    [
                        "2025-01-02T00:00:00+05:30",
                        1850,
                        1860,
                        1845,
                        1855,
                        250000,
                        0,
                    ]
                ]
            ),
        ]
    )
    delays: list[float] = []

    outcome = _client(transport, max_attempts=2, sleeper=delays.append).acquire_historical_daily(
        _two_day_request()
    )

    assert isinstance(outcome, HistoricalAcquisition)
    assert len(transport.requests) == 2
    assert delays == [5.0]


def test_unauthorized_response_is_not_retried() -> None:
    transport = SequenceHttpTransport(
        responses=[
            HttpResponse(status=401, body=b'{"status":"error"}', headers={}),
            _success_response([]),
        ]
    )

    outcome = _client(transport, max_attempts=3).acquire_historical_daily(_two_day_request())

    assert isinstance(outcome, HistoricalAcquisitionFailure)
    assert outcome.code == AcquisitionFailureCode.PROVIDER_UNAUTHORIZED
    assert len(transport.requests) == 1


def test_transport_timeout_is_typed_and_retryable() -> None:
    transport = StubHttpTransport(TransportTimeout("provider deadline exceeded"))

    outcome = _client(transport).acquire_historical_daily(_two_day_request())

    assert isinstance(outcome, HistoricalAcquisitionFailure)
    assert outcome.code == AcquisitionFailureCode.PROVIDER_TIMEOUT
    assert outcome.retryable is True


def test_transport_connection_failure_is_typed_and_retryable() -> None:
    transport = StubHttpTransport(TransportConnectionError("provider connection failed"))

    outcome = _client(transport).acquire_historical_daily(_two_day_request())

    assert isinstance(outcome, HistoricalAcquisitionFailure)
    assert outcome.code == AcquisitionFailureCode.PROVIDER_UNAVAILABLE
    assert outcome.retryable is True


def test_oversized_provider_response_is_typed_and_not_retried() -> None:
    transport = SequenceHttpTransport(
        responses=[ResponseTooLarge("body limit"), _success_response([])]
    )

    outcome = _client(transport, max_attempts=3).acquire_historical_daily(_two_day_request())

    assert isinstance(outcome, HistoricalAcquisitionFailure)
    assert outcome.code == AcquisitionFailureCode.PROVIDER_MALFORMED
    assert outcome.retryable is False
    assert len(transport.requests) == 1


def test_empty_candle_response_is_not_success() -> None:
    outcome = _client(StubHttpTransport(_success_response([]))).acquire_historical_daily(
        _two_day_request()
    )

    assert isinstance(outcome, HistoricalAcquisitionFailure)
    assert outcome.code == AcquisitionFailureCode.DATASET_EMPTY


def test_short_provider_range_is_partial_research_evidence() -> None:
    response = _success_response([["2025-01-02T00:00:00+05:30", 1850, 1860, 1845, 1855, 250000, 0]])
    request = HistoricalDailyRequest(
        instrument_key=INFY_INSTRUMENT_KEY,
        symbol="INFY",
        from_date=date(2020, 1, 1),
        to_date=date(2025, 1, 3),
        request_id="req-five-years",
    )

    outcome = _client(StubHttpTransport(response)).acquire_historical_daily(request)

    assert isinstance(outcome, HistoricalAcquisition)
    assert outcome.manifest.source_status == SourceStatus.PARTIAL
    assert outcome.manifest.status == DatasetStatus.PARTIAL
    assert QualityCode.PROVIDER_RANGE_UNAVAILABLE in {
        finding.code for finding in outcome.manifest.quality_findings
    }


def test_missing_access_token_returns_unauthorized_without_transport_call() -> None:
    transport = StubHttpTransport(_success_response([]))
    client = _client(transport, access_token="")

    outcome = client.acquire_historical_daily(_two_day_request())

    assert isinstance(outcome, HistoricalAcquisitionFailure)
    assert outcome.code == AcquisitionFailureCode.PROVIDER_UNAUTHORIZED
    assert transport.requests == []


def test_request_rejects_non_nse_equity_instrument() -> None:
    with pytest.raises(ValueError, match="NSE cash equity"):
        HistoricalDailyRequest(
            instrument_key="BSE_EQ|INE009A01021",
            symbol="INFY",
            from_date=date(2025, 1, 2),
            to_date=date(2025, 1, 3),
        )


def test_request_rejects_more_than_ten_years() -> None:
    with pytest.raises(ValueError, match="ten-year"):
        HistoricalDailyRequest(
            instrument_key=INFY_INSTRUMENT_KEY,
            symbol="INFY",
            from_date=date(2015, 1, 1),
            to_date=date(2025, 1, 2),
        )


def test_historical_client_has_no_broker_order_methods() -> None:
    client = _client(StubHttpTransport(_success_response([])))

    assert not hasattr(client, "place_order")
    assert not hasattr(client, "modify_order")
    assert not hasattr(client, "cancel_order")


def _client(
    transport: HttpTransport,
    *,
    access_token: str = "test-token",
    max_attempts: int = 1,
    sleeper: Callable[[float], None] = lambda _delay: None,
) -> UpstoxClient:
    dependencies = UpstoxClientDependencies(
        transport=transport,
        clock=lambda: FIXED_ACQUISITION_TIME,
        sleeper=sleeper,
        jitter=lambda: 0.0,
    )
    return UpstoxClient(
        access_token=access_token,
        dependencies=dependencies,
        config=UpstoxClientConfig(retry_policy=RetryPolicy(max_attempts=max_attempts)),
    )


def _two_day_request() -> HistoricalDailyRequest:
    return HistoricalDailyRequest(
        instrument_key=INFY_INSTRUMENT_KEY,
        symbol="INFY",
        from_date=date(2025, 1, 2),
        to_date=date(2025, 1, 3),
        request_id="req-two-days",
    )


def _governed_request(
    *,
    from_date: date = date(2025, 1, 2),
    to_date: date = date(2025, 1, 3),
    expected_sessions: tuple[date, ...] | None = None,
) -> HistoricalDailyRequest:
    authority = AuthorityReference(
        authority_id="authority-test",
        source_url="https://example.test/authority",
        publication_date=date(2024, 12, 1),
        effective_from=date(2025, 1, 1),
        effective_to=None,
        version="v1",
        content_hash="a" * 64,
    )
    return HistoricalDailyRequest(
        instrument_key=INFY_INSTRUMENT_KEY,
        symbol="INFY",
        from_date=from_date,
        to_date=to_date,
        request_id="req-governed",
        calendar=CalendarReference(
            calendar_id="nse-cash",
            version="2025-v1",
            content_hash="b" * 64,
        ),
        expected_sessions=expected_sessions,
        corporate_action_authority=authority,
        historical_universe_authority=authority,
    )


def _success_response(
    candles: list[list[Any]],
    *,
    request_id: str | None = None,
) -> HttpResponse:
    headers = {"content-type": "application/json"}
    if request_id is not None:
        headers["x-request-id"] = request_id
    return HttpResponse(
        status=200,
        body=json.dumps({"status": "success", "data": {"candles": candles}}).encode(),
        headers=headers,
    )
