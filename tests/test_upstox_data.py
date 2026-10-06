"""Unit tests for Upstox API v2 market data connector."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest

from quant_system.data.market_data import AcquisitionFailureCode
from quant_system.data.upstox import UpstoxClient, UpstoxClientDependencies, UpstoxDataError
from quant_system.data.upstox_http import HttpResponse
from quant_system.data.upstox_parsing import (
    ProviderQuoteUnavailable,
    ProviderSchemaDrift,
    parse_quote_payload,
)

INFY_KEY = "NSE_EQ|INE009A01021"
RELIANCE_KEY = "NSE_EQ|INE002A01018"


def test_upstox_client_initialization_and_auth_check() -> None:
    client = UpstoxClient()
    # By default without env vars, is_authenticated is False
    assert isinstance(client.is_authenticated, bool)

    auth_client = UpstoxClient(access_token="test_mock_token")
    assert auth_client.is_authenticated is True
    assert "Bearer test_mock_token" in auth_client._get_headers()["Authorization"]


def test_upstox_parse_candles() -> None:
    client = UpstoxClient()
    mock_candles = [
        ["2025-01-02T09:15:00+05:30", 1850.50, 1860.00, 1845.00, 1855.25, 250000, 0],
        ["2025-01-03T09:15:00+05:30", 1855.00, 1875.00, 1850.00, 1870.00, 310000, 0],
    ]

    bars = client.parse_candles(symbol="INFY", candles=mock_candles)
    assert len(bars) == 2
    assert bars[0].symbol == "INFY"
    assert bars[0].open == Decimal("1850.5")
    assert bars[0].high == Decimal("1860.0")
    assert bars[0].low == Decimal("1845.0")
    assert bars[0].close == Decimal("1855.25")
    assert bars[0].volume == 250000
    assert bars[1].close == Decimal("1870.0")


def test_upstox_parse_candles_rejects_invalid_ohlc_instead_of_repairing_it() -> None:
    client = UpstoxClient()
    invalid_candles = [["2025-01-02T09:15:00+05:30", 1850.50, 1840.00, 1845.00, 1855.25, 250000, 0]]

    with pytest.raises(ValueError, match="High"):
        client.parse_candles(symbol="INFY", candles=invalid_candles)


def _without_ambient_upstox_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    """`UpstoxClient` falls back to these variables, so a test of the no-token path must clear them.

    Without this, a machine that has a real token exported turns a credential-absence test into a
    live authenticated request instead of the `PROVIDER_UNAUTHORIZED` it asserts.
    """
    for name in ("UPSTOX_ANALYTICS_TOKEN", "UPSTOX_ACCESS_TOKEN", "UPSTOX_API_KEY"):
        monkeypatch.delenv(name, raising=False)


def test_upstox_historical_request_without_token_raises_typed_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _without_ambient_upstox_credentials(monkeypatch)
    client = UpstoxClient(api_key="", access_token="")

    with pytest.raises(UpstoxDataError) as raised:
        client.fetch_historical_bars(
            instrument_key="NSE_EQ|INE009A01021",
            symbol="INFY",
        )

    assert raised.value.code == AcquisitionFailureCode.PROVIDER_UNAUTHORIZED


def test_upstox_quote_request_without_token_raises_typed_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _without_ambient_upstox_credentials(monkeypatch)
    client = UpstoxClient(api_key="", access_token="")

    with pytest.raises(UpstoxDataError) as raised:
        client.fetch_market_quote(
            instrument_key="NSE_EQ|INE009A01021",
            symbol="INFY",
        )

    assert raised.value.code == AcquisitionFailureCode.PROVIDER_UNAUTHORIZED


def test_the_client_prefers_the_token_that_survives_the_night(monkeypatch) -> None:
    """`UPSTOX_ACCESS_TOKEN` expires at 03:30 IST the morning after it is issued.

    Upstox V2 has no refresh token, so a client reading only that variable is authorised solely on
    days somebody renewed it by hand before the job ran. The 09:00 pre-open refresh would have been
    unauthorised on 2026-09-01 for exactly this reason, while the paper session that follows it --
    which already preferred the analytics token -- would have been fine. Two paths disagreeing about
    which credential to use is what left the refresh dead.

    The analytics token is issued free, one per user, for roughly a year.
    """
    from quant_system.data.upstox import UpstoxClient

    monkeypatch.setenv("UPSTOX_ANALYTICS_TOKEN", "analytics-token")
    monkeypatch.setenv("UPSTOX_ACCESS_TOKEN", "daily-token")
    assert UpstoxClient().access_token == "analytics-token"

    # Still works for anyone who only has the daily one.
    monkeypatch.delenv("UPSTOX_ANALYTICS_TOKEN")
    assert UpstoxClient().access_token == "daily-token"

    # And an explicit argument still wins over both.
    assert UpstoxClient(access_token="explicit").access_token == "explicit"


def _quote_entry(**overrides: Any) -> dict[str, Any]:
    """One `data` entry shaped like the live V2 `market-quote/quotes` reply.

    Only the fields the provider was measured to return are present: `instrument_token` (the ISIN
    form), `last_price`, `timestamp` (ISO, +05:30), `depth.buy/sell` and `ohlc`.
    """
    entry: dict[str, Any] = {
        "instrument_token": INFY_KEY,
        "last_price": 1612.4,
        "timestamp": "2026-10-01T14:05:10+05:30",
        "ohlc": {"open": 1600.0, "high": 1620.0, "low": 1598.5, "close": 1605.0},
        "depth": {
            "buy": [{"price": 1612.35, "quantity": 410}, {"price": 1612.3, "quantity": 95}],
            "sell": [{"price": 1612.45, "quantity": 220}, {"price": 1612.5, "quantity": 60}],
        },
    }
    entry.update(overrides)
    return entry


def _body(data: Any, **envelope: Any) -> bytes:
    return json.dumps({"status": "success", "data": data, **envelope}).encode("utf-8")


@dataclass(slots=True)
class _QuoteTransport:
    body: bytes
    status: int = 200
    urls: list[str] = field(default_factory=list)

    def get(
        self,
        url: str,
        *,
        headers: dict[str, str],
        timeout_seconds: float,
        max_response_bytes: int,
    ) -> HttpResponse:
        self.urls.append(url)
        return HttpResponse(status=self.status, body=self.body, headers={})


def _quote_client(transport: _QuoteTransport) -> UpstoxClient:
    return UpstoxClient(
        access_token="test-token",
        dependencies=UpstoxClientDependencies(
            transport=transport,
            clock=lambda: datetime(2026, 10, 1, 9, 0, tzinfo=UTC),
            sleeper=lambda _delay: None,
            jitter=lambda: 0.0,
        ),
    )


def test_the_real_symbol_keyed_reply_parses_to_a_quote() -> None:
    """The live reply is keyed `NSE_EQ:INFY`; the request carried `NSE_EQ|INE009A01021`."""
    body = _body({"NSE_EQ:INFY": _quote_entry()})

    quote = parse_quote_payload(body, instrument_key=INFY_KEY, symbol="INFY")

    assert quote.symbol == "INFY"
    assert quote.bid == Decimal("1612.35")
    assert quote.ask == Decimal("1612.45")
    assert quote.bid_size == 410
    assert quote.ask_size == 220
    assert quote.last_price == Decimal("1612.4")
    assert quote.timestamp == datetime(2026, 10, 1, 8, 35, 10, tzinfo=UTC)


def test_fetch_market_quote_accepts_the_real_reply_end_to_end() -> None:
    transport = _QuoteTransport(_body({"NSE_EQ:INFY": _quote_entry()}))

    quote = _quote_client(transport).fetch_market_quote(INFY_KEY, "INFY")

    assert quote.bid == Decimal("1612.35")
    assert len(transport.urls) == 1
    assert "instrument_key=NSE_EQ%7CINE009A01021" in transport.urls[0]


def test_an_instrument_keyed_reply_is_still_accepted() -> None:
    """The provider has not promised a key form, so the instrument-key form keeps working."""
    body = _body({INFY_KEY: _quote_entry()})

    quote = parse_quote_payload(body, instrument_key=INFY_KEY, symbol="INFY")

    assert quote.ask == Decimal("1612.45")


def test_a_symbol_keyed_entry_whose_token_disagrees_is_refused() -> None:
    """The label matches (`NSE_EQ:INFY`) but the entry says it is another ISIN: price the wrong
    security and the quote would be wrong in a way nothing downstream can see."""
    body = _body({"NSE_EQ:INFY": _quote_entry(instrument_token=RELIANCE_KEY)})

    with pytest.raises(ProviderSchemaDrift, match="not for the requested instrument"):
        parse_quote_payload(body, instrument_key=INFY_KEY, symbol="INFY")


def test_an_instrument_keyed_entry_whose_token_disagrees_is_refused() -> None:
    body = _body({INFY_KEY: _quote_entry(instrument_token=RELIANCE_KEY)})

    with pytest.raises(ProviderSchemaDrift, match="not for the requested instrument"):
        parse_quote_payload(body, instrument_key=INFY_KEY, symbol="INFY")


def test_a_symbol_keyed_entry_with_no_token_is_refused() -> None:
    """Found by label alone, with nothing in the entry to say which security it is."""
    entry = _quote_entry()
    del entry["instrument_token"]

    with pytest.raises(ProviderSchemaDrift, match="not for the requested instrument"):
        parse_quote_payload(_body({"NSE_EQ:INFY": entry}), instrument_key=INFY_KEY, symbol="INFY")


def test_an_instrument_keyed_entry_with_no_token_is_accepted() -> None:
    """Keyed by the very instrument key requested, so the key itself is the binding."""
    entry = _quote_entry()
    del entry["instrument_token"]

    quote = parse_quote_payload(_body({INFY_KEY: entry}), instrument_key=INFY_KEY, symbol="INFY")

    assert quote.bid == Decimal("1612.35")


def test_an_entry_under_another_label_is_found_by_its_token() -> None:
    """The caller's display symbol need not equal the provider's trading symbol."""
    body = _body({"NSE_EQ:INFOSYS-RENAMED": _quote_entry()})

    quote = parse_quote_payload(body, instrument_key=INFY_KEY, symbol="INFY")

    assert quote.symbol == "INFY"
    assert quote.last_price == Decimal("1612.4")


def test_two_unlabelled_entries_claiming_one_token_are_refused_as_ambiguous() -> None:
    body = _body({"NSE_EQ:AAA": _quote_entry(), "NSE_EQ:BBB": _quote_entry()})

    with pytest.raises(ProviderSchemaDrift, match="absent"):
        parse_quote_payload(body, instrument_key=INFY_KEY, symbol="INFY")


def test_a_reply_that_only_contains_another_instrument_is_refused() -> None:
    body = _body({"NSE_EQ:RELIANCE": _quote_entry(instrument_token=RELIANCE_KEY)})

    with pytest.raises(ProviderSchemaDrift, match="absent"):
        parse_quote_payload(body, instrument_key=INFY_KEY, symbol="INFY")


def test_the_segment_comes_from_the_requested_key_not_a_hardcoded_exchange() -> None:
    """A BSE request must not be answered by an NSE-labelled entry for the same symbol."""
    nse_entry = _quote_entry()
    bse_key = "BSE_EQ|INE009A01021"

    with pytest.raises(ProviderSchemaDrift, match="absent"):
        parse_quote_payload(
            _body({"NSE_EQ:INFY": nse_entry}), instrument_key=bse_key, symbol="INFY"
        )

    bse_entry = _quote_entry(instrument_token=bse_key)
    quote = parse_quote_payload(
        _body({"BSE_EQ:INFY": bse_entry}), instrument_key=bse_key, symbol="INFY"
    )
    assert quote.bid == Decimal("1612.35")


_AFTER_HOURS_EMPTY_LEVEL = [{"price": 0.0, "quantity": 0}]


@pytest.mark.parametrize(
    "overrides",
    [
        pytest.param(
            {
                "depth": {
                    "buy": _AFTER_HOURS_EMPTY_LEVEL,
                    "sell": [{"price": 1612.45, "quantity": 5}],
                }
            },
            id="zero-bid",
        ),
        pytest.param(
            {
                "depth": {
                    "buy": [{"price": 1612.35, "quantity": 5}],
                    "sell": _AFTER_HOURS_EMPTY_LEVEL,
                }
            },
            id="zero-ask",
        ),
        pytest.param(
            {"depth": {"buy": _AFTER_HOURS_EMPTY_LEVEL, "sell": _AFTER_HOURS_EMPTY_LEVEL}},
            id="both-sides-empty",
        ),
        pytest.param({"last_price": 0.0}, id="zero-last-price"),
        pytest.param(
            {
                "depth": {
                    "buy": [{"price": 1612.35, "quantity": 0}],
                    "sell": [{"price": 1612.45, "quantity": 5}],
                }
            },
            id="bid-priced-but-nothing-resting",
        ),
        pytest.param(
            {
                "depth": {
                    "buy": [{"price": 1612.35, "quantity": 5}],
                    "sell": [{"price": 1612.45, "quantity": 0}],
                }
            },
            id="ask-priced-but-nothing-resting",
        ),
    ],
)
def test_a_book_with_no_priced_side_is_refused_rather_than_quoted_as_zero(
    overrides: dict[str, Any],
) -> None:
    """After hours the best bid can be `{price: 0.0, quantity: 0}`. A zero bid would give a mid of
    half the ask and a 200% spread, and `Quote` has no way to say "no bid", so this fails closed --
    as unavailable, not as drift."""
    body = _body({"NSE_EQ:INFY": _quote_entry(**overrides)})

    with pytest.raises(ProviderQuoteUnavailable):
        parse_quote_payload(body, instrument_key=INFY_KEY, symbol="INFY")

    with pytest.raises(UpstoxDataError) as raised:
        _quote_client(_QuoteTransport(body)).fetch_market_quote(INFY_KEY, "INFY")

    assert raised.value.code == AcquisitionFailureCode.DATASET_EMPTY
    assert raised.value.code != AcquisitionFailureCode.PROVIDER_SCHEMA_DRIFT
    assert raised.value.retryable is True


@pytest.mark.parametrize(
    "body",
    [
        pytest.param(b"not json", id="not-json"),
        pytest.param(b"\xff\xfe", id="not-utf8"),
        pytest.param(b"[]", id="top-level-list"),
        pytest.param(b'{"status": "success"}', id="no-data"),
        pytest.param(b'{"status": "success", "data": []}', id="data-not-an-object"),
        pytest.param(b'{"status": "success", "data": {}}', id="data-empty"),
        pytest.param(_body({"NSE_EQ:INFY": []}), id="entry-not-an-object"),
        pytest.param(_body({"NSE_EQ:INFY": {"instrument_token": INFY_KEY}}), id="entry-bare"),
        pytest.param(
            _body({"NSE_EQ:INFY": _quote_entry(depth={"buy": [], "sell": []})}),
            id="empty-ladders",
        ),
        pytest.param(
            _body({"NSE_EQ:INFY": _quote_entry(depth={"sell": [{"price": 1.0, "quantity": 1}]})}),
            id="no-buy-side",
        ),
        pytest.param(_body({"NSE_EQ:INFY": _quote_entry(last_price="abc")}), id="text-price"),
        pytest.param(_body({"NSE_EQ:INFY": _quote_entry(last_price=None)}), id="null-price"),
        pytest.param(_body({"NSE_EQ:INFY": _quote_entry(last_price=True)}), id="boolean-price"),
        pytest.param(
            _body({"NSE_EQ:INFY": _quote_entry(last_price=-1612.4)}), id="negative-last-price"
        ),
        pytest.param(
            _body(
                {
                    "NSE_EQ:INFY": _quote_entry(
                        depth={
                            "buy": [{"price": -0.02, "quantity": 5}],
                            "sell": [{"price": 1612.45, "quantity": 5}],
                        }
                    )
                }
            ),
            id="negative-bid",
        ),
        pytest.param(
            _body(
                {
                    "NSE_EQ:INFY": _quote_entry(
                        depth={
                            "buy": [{"price": 1612.50, "quantity": 5}],
                            "sell": [{"price": 1612.45, "quantity": 5}],
                        }
                    )
                }
            ),
            id="crossed-book",
        ),
        pytest.param(
            _body(
                {
                    "NSE_EQ:INFY": _quote_entry(
                        depth={
                            "buy": [{"price": 1612.35, "quantity": True}],
                            "sell": [{"price": 1612.45, "quantity": 5}],
                        }
                    )
                }
            ),
            id="boolean-quantity",
        ),
        pytest.param(
            _body(
                {
                    "NSE_EQ:INFY": _quote_entry(
                        depth={
                            "buy": [{"price": 1612.35, "quantity": 2.5}],
                            "sell": [{"price": 1612.45, "quantity": 5}],
                        }
                    )
                }
            ),
            id="fractional-quantity",
        ),
        pytest.param(
            _body({"NSE_EQ:INFY": _quote_entry(timestamp="2026-10-01T14:05:10")}),
            id="timestamp-without-a-zone",
        ),
        pytest.param(_body({"NSE_EQ:INFY": _quote_entry(timestamp=1759307110)}), id="numeric-time"),
        pytest.param(_body({"NSE_EQ:INFY": _quote_entry(timestamp="soon")}), id="garbled-time"),
        pytest.param(
            b'{"status": "success", "data": {"NSE_EQ:INFY": {"last_price": NaN}}}',
            id="nan-literal",
        ),
    ],
)
def test_a_genuinely_malformed_reply_still_fails_closed_as_schema_drift(body: bytes) -> None:
    with pytest.raises(ProviderSchemaDrift):
        parse_quote_payload(body, instrument_key=INFY_KEY, symbol="INFY")

    with pytest.raises(UpstoxDataError) as raised:
        _quote_client(_QuoteTransport(body)).fetch_market_quote(INFY_KEY, "INFY")

    assert raised.value.code == AcquisitionFailureCode.PROVIDER_SCHEMA_DRIFT


def test_a_nan_price_is_schema_drift_not_an_uncaught_arithmetic_error() -> None:
    """`Quote.__post_init__` compares prices, and comparing a NaN `Decimal` raises
    `InvalidOperation` -- which is not a `ValueError` and used to escape the parser untyped."""
    body = b"".join(
        [
            b'{"status": "success", "data": {"NSE_EQ:INFY": ',
            json.dumps(_quote_entry(last_price="NaN")).encode("utf-8"),
            b"}}",
        ]
    )

    with pytest.raises(ProviderSchemaDrift):
        parse_quote_payload(body, instrument_key=INFY_KEY, symbol="INFY")
