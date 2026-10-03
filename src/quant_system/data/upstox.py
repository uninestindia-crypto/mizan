"""Strict read-only Upstox market-data adapter."""

from __future__ import annotations

import os
import random
import time
import urllib.parse
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

from quant_system.core.domain import PriceBar, Quote
from quant_system.data.bars import BarSeries
from quant_system.data.market_data import (
    AcquisitionFailureCode,
    HistoricalAcquisition,
    HistoricalAcquisitionFailure,
    HistoricalAcquisitionOutcome,
    HistoricalDailyRequest,
    create_dataset_manifest,
)
from quant_system.data.market_data_evidence import raw_sha256
from quant_system.data.upstox_failures import (
    create_failure,
    empty_failure,
    get_header,
    get_retry_after,
    is_transient_status,
    malformed_failure,
    map_http_failure,
    quality_failure,
    require_aware_utc,
    schema_drift_failure,
    unauthorized_failure,
)
from quant_system.data.upstox_http import (
    HttpResponse,
    HttpTransport,
    ResponseTooLarge,
    TransportConnectionError,
    TransportTimeout,
    UpstoxClientConfig,
    UrlLibHttpTransport,
)
from quant_system.data.upstox_parsing import (
    ProviderMalformedBody,
    ProviderSchemaDrift,
    QualityBlockedError,
    decode_historical_candles,
    get_authority_findings,
    get_range_findings,
    parse_candle_rows,
    parse_compatibility_candles,
    parse_quote_payload,
)


@dataclass(frozen=True, slots=True)
class UpstoxClientDependencies:
    """Injected I/O used to make provider behavior deterministic in tests."""

    transport: HttpTransport
    clock: Callable[[], datetime]
    sleeper: Callable[[float], None]
    jitter: Callable[[], float]


class UpstoxDataError(RuntimeError):
    """Compatibility exception carrying a stable provider failure code."""

    def __init__(self, failure: HistoricalAcquisitionFailure) -> None:
        self.code = failure.code
        self.retryable = failure.retryable
        self.retry_after_seconds = failure.retry_after_seconds
        super().__init__(f"{failure.code.value}: acquisition failed; {failure.recovery_action}")


class UpstoxClient:
    """Read-only Upstox V3 historical-data client with explicit failure outcomes."""

    BASE_URL = "https://api.upstox.com"
    HISTORICAL_API_VERSION = "v3"

    def __init__(
        self,
        api_key: str | None = None,
        access_token: str | None = None,
        *,
        dependencies: UpstoxClientDependencies | None = None,
        config: UpstoxClientConfig | None = None,
        allow_anonymous_history: bool = False,
    ) -> None:
        # Off by default: every governed caller still fails closed with PROVIDER_UNAUTHORIZED when no
        # token is configured. Upstox's daily historical-candle endpoint answers without a token
        # (measured 2026-10-03), which lets a first-time user download data with no account; only that
        # opt-in caller sets this.
        self.allow_anonymous_history = allow_anonymous_history
        # `api_key` remains only for source compatibility; V3 data requires a bearer token.
        self.api_key = api_key or os.getenv("UPSTOX_API_KEY", "")
        # Analytics token first, then the standard access token.
        #
        # This read `UPSTOX_ACCESS_TOKEN` alone. That token expires at 03:30 IST the morning after
        # it is issued and Upstox V2 has no refresh token, so an unattended 09:00 job was authorised
        # only on days somebody had renewed it by hand the same morning. The analytics token is
        # issued free, one per user, for roughly a year, and the paper runner already prefers it --
        # the two paths disagreeing is what left the pre-open refresh unauthorised while the session
        # that follows it was fine.
        self.access_token = (
            access_token
            or os.getenv("UPSTOX_ANALYTICS_TOKEN", "")
            or os.getenv("UPSTOX_ACCESS_TOKEN", "")
        )
        self.dependencies = dependencies or _default_dependencies()
        self.config = config or UpstoxClientConfig()

    @property
    def is_authenticated(self) -> bool:
        return bool(self.access_token)

    def _get_headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "User-Agent": "QuantOS/1.0",
        }
        if self.access_token:
            headers["Authorization"] = f"Bearer {self.access_token}"
        return headers

    def acquire_historical_daily(
        self,
        request: HistoricalDailyRequest,
    ) -> HistoricalAcquisitionOutcome:
        """Acquire and validate one NSE-equity daily range without implicit fallback."""
        acquired_at = require_aware_utc(self.dependencies.clock())
        if not self.is_authenticated and not self.allow_anonymous_history:
            return create_failure(
                AcquisitionFailureCode.PROVIDER_UNAUTHORIZED,
                acquired_at,
                retryable=False,
                recovery_action="Configure a valid UPSTOX_ACCESS_TOKEN and retry.",
            )

        response_or_failure = self._get_with_retry(
            self._historical_daily_url(request),
            acquired_at,
        )
        if isinstance(response_or_failure, HistoricalAcquisitionFailure):
            return response_or_failure
        if response_or_failure.status != 200:
            return map_http_failure(response_or_failure, acquired_at)
        return self._parse_historical_response(request, response_or_failure, acquired_at)

    def parse_candles(
        self,
        symbol: str,
        candles: Sequence[Sequence[Any]],
    ) -> list[PriceBar]:
        """Compatibility parser that now rejects invalid provider values."""
        return parse_compatibility_candles(
            candles,
            symbol=symbol,
            acquired_at=require_aware_utc(self.dependencies.clock()),
        )

    def fetch_historical_bars(
        self,
        instrument_key: str,
        symbol: str,
        interval: str = "day",
        to_date: date | None = None,
        from_date: date | None = None,
    ) -> BarSeries:
        """Compatibility adapter that raises typed failure instead of returning empty data."""
        if interval not in {"day", "days"}:
            raise ValueError("the compatibility adapter supports daily bars only")
        current_date = require_aware_utc(self.dependencies.clock()).date()
        requested_end = to_date or current_date
        requested_start = from_date or requested_end
        outcome = self.acquire_historical_daily(
            HistoricalDailyRequest(
                instrument_key=instrument_key,
                symbol=symbol,
                from_date=requested_start,
                to_date=requested_end,
            )
        )
        if isinstance(outcome, HistoricalAcquisitionFailure):
            raise UpstoxDataError(outcome)
        return BarSeries(symbol=symbol, bars=list(outcome.bars))

    def fetch_market_quote(self, instrument_key: str, symbol: str) -> Quote:
        """Fetch a V2 snapshot strictly; the governed V3 stream is a later slice."""
        detected_at = require_aware_utc(self.dependencies.clock())
        if not self.is_authenticated:
            raise UpstoxDataError(unauthorized_failure(detected_at))
        params = urllib.parse.urlencode({"instrument_key": instrument_key})
        response = self.dependencies.transport.get(
            f"{self.BASE_URL}/v2/market-quote/quotes?{params}",
            headers=self._get_headers(),
            timeout_seconds=self.config.timeout_seconds,
            max_response_bytes=self.config.max_response_bytes,
        )
        if response.status != 200:
            raise UpstoxDataError(map_http_failure(response, detected_at))
        try:
            return parse_quote_payload(response.body, instrument_key=instrument_key, symbol=symbol)
        except ProviderSchemaDrift as error:
            raise UpstoxDataError(schema_drift_failure(detected_at)) from error

    def _historical_daily_url(self, request: HistoricalDailyRequest) -> str:
        encoded_key = urllib.parse.quote(request.instrument_key, safe="")
        return (
            f"{self.BASE_URL}/{self.HISTORICAL_API_VERSION}/historical-candle/"
            f"{encoded_key}/days/1/{request.to_date.isoformat()}/{request.from_date.isoformat()}"
        )

    def _get_with_retry(
        self,
        url: str,
        detected_at: datetime,
    ) -> HttpResponse | HistoricalAcquisitionFailure:
        policy = self.config.retry_policy
        for attempt_number in range(1, policy.max_attempts + 1):
            response_or_failure = self._attempt_get(url, detected_at)
            if isinstance(response_or_failure, HistoricalAcquisitionFailure):
                if not response_or_failure.retryable or attempt_number == policy.max_attempts:
                    return response_or_failure
                self._wait_before_retry(attempt_number, None)
                continue
            if not is_transient_status(response_or_failure.status):
                return response_or_failure
            if attempt_number == policy.max_attempts:
                return response_or_failure
            self._wait_before_retry(attempt_number, get_retry_after(response_or_failure.headers))
        raise AssertionError("retry loop must return an outcome")

    def _attempt_get(
        self,
        url: str,
        detected_at: datetime,
    ) -> HttpResponse | HistoricalAcquisitionFailure:
        try:
            return self.dependencies.transport.get(
                url,
                headers=self._get_headers(),
                timeout_seconds=self.config.timeout_seconds,
                max_response_bytes=self.config.max_response_bytes,
            )
        except TransportTimeout:
            return create_failure(
                AcquisitionFailureCode.PROVIDER_TIMEOUT,
                detected_at,
                retryable=True,
                recovery_action="Retry after provider connectivity recovers.",
            )
        except TransportConnectionError:
            return create_failure(
                AcquisitionFailureCode.PROVIDER_UNAVAILABLE,
                detected_at,
                retryable=True,
                recovery_action="Retry after provider connectivity recovers.",
            )
        except ResponseTooLarge:
            return create_failure(
                AcquisitionFailureCode.PROVIDER_MALFORMED,
                detected_at,
                retryable=False,
                recovery_action="Reduce the range or inspect provider schema changes.",
            )

    def _wait_before_retry(
        self,
        attempt_number: int,
        retry_after_seconds: int | None,
    ) -> None:
        jitter = min(1.0, max(0.0, self.dependencies.jitter()))
        delay = self.config.retry_policy.delay_seconds(
            attempt_number,
            retry_after_seconds=retry_after_seconds,
            jitter=jitter,
        )
        self.dependencies.sleeper(delay)

    def _parse_historical_response(
        self,
        request: HistoricalDailyRequest,
        response: HttpResponse,
        acquired_at: datetime,
    ) -> HistoricalAcquisitionOutcome:
        try:
            candles = decode_historical_candles(response.body)
        except ProviderMalformedBody:
            return malformed_failure(acquired_at)
        except ProviderSchemaDrift:
            return schema_drift_failure(acquired_at)
        if not candles:
            return empty_failure(acquired_at)

        try:
            records, row_findings = parse_candle_rows(candles, request, acquired_at)
        except ProviderSchemaDrift:
            return schema_drift_failure(acquired_at)
        except QualityBlockedError as error:
            return quality_failure(acquired_at, error.findings)

        source_status, range_findings = get_range_findings(request, records)
        findings = (*row_findings, *range_findings, *get_authority_findings(request))
        manifest = create_dataset_manifest(
            request,
            records,
            acquired_at=acquired_at,
            raw_response_hash=raw_sha256(response.body),
            provider_request_id=get_header(response.headers, "x-request-id"),
            source_status=source_status,
            quality_findings=findings,
        )
        return HistoricalAcquisition(manifest=manifest, records=records)


def _default_dependencies() -> UpstoxClientDependencies:
    return UpstoxClientDependencies(
        transport=UrlLibHttpTransport(),
        clock=lambda: datetime.now(UTC),
        sleeper=time.sleep,
        jitter=random.random,
    )
