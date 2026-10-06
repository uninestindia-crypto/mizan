"""Unit tests for Upstox API v2 market data connector."""

from decimal import Decimal

import pytest

from quant_system.data.market_data import AcquisitionFailureCode
from quant_system.data.upstox import UpstoxClient, UpstoxDataError


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


def test_upstox_historical_request_without_token_raises_typed_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # `access_token=""` falls back to the environment. With a real token set (a cloud session, a
    # developer shell) this test used to make a live provider request instead of testing "no token".
    monkeypatch.delenv("UPSTOX_ANALYTICS_TOKEN", raising=False)
    monkeypatch.delenv("UPSTOX_ACCESS_TOKEN", raising=False)
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
    monkeypatch.delenv("UPSTOX_ANALYTICS_TOKEN", raising=False)
    monkeypatch.delenv("UPSTOX_ACCESS_TOKEN", raising=False)
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


# --------------------------------------------------------------------------------------------------
# The single-quote parse, against the shape the provider really returns
#
# Measured 2026-10-06 against the live `v2/market-quote/quotes` endpoint with a valid analytics
# token: the request carries the instrument key (`NSE_EQ|INE009A01021`), HTTP 200, `status:
# success`, and `data` is keyed by the **symbol** form (`NSE_EQ:INFY`). Each entry repeats the
# instrument key in its own `instrument_token`. `parse_quote_payload` looked up only the key form,
# so against the real feed `fetch_market_quote` always raised PROVIDER_SCHEMA_DRIFT. No test parsed
# a quote body at all, which is how that survived: the success path was never exercised. The paper
# session has its own parser that handles both forms and was never affected.
#
# The numbers below are invented. Only the shape is the provider's.
# --------------------------------------------------------------------------------------------------

import json  # noqa: E402
from datetime import UTC, datetime  # noqa: E402
from typing import Any  # noqa: E402

from quant_system.data.upstox import UpstoxClientDependencies  # noqa: E402
from quant_system.data.upstox_http import HttpResponse  # noqa: E402

INFY_KEY = "NSE_EQ|INE009A01021"


def _entry(**overrides: Any) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "instrument_token": INFY_KEY,
        "symbol": "INFY",
        "last_price": 1500.5,
        "timestamp": "2026-10-06T10:15:30.250+05:30",
        "depth": {
            "buy": [{"quantity": 120, "price": 1500.4, "orders": 3}],
            "sell": [{"quantity": 80, "price": 1500.6, "orders": 2}],
        },
    }
    entry.update(overrides)
    return entry


class _OneReply:
    def __init__(self, body: dict[str, Any]) -> None:
        self.body = body

    def get(self, url: str, **_kwargs: Any) -> HttpResponse:
        assert "market-quote/quotes" in url
        return HttpResponse(status=200, body=json.dumps(self.body).encode(), headers={})


def _client(body: dict[str, Any]) -> UpstoxClient:
    return UpstoxClient(
        access_token="test_mock_token",
        dependencies=UpstoxClientDependencies(
            transport=_OneReply(body),
            clock=lambda: datetime(2026, 10, 6, 5, 0, tzinfo=UTC),
            sleeper=lambda _seconds: None,
            jitter=lambda: 0.0,
        ),
    )


def _quote(body: dict[str, Any]) -> Any:
    return _client(body).fetch_market_quote(INFY_KEY, "INFY")


def test_a_quote_keyed_by_symbol_as_the_real_provider_returns_it_is_parsed() -> None:
    quote = _quote({"status": "success", "data": {"NSE_EQ:INFY": _entry()}})

    assert quote.symbol == "INFY"
    assert quote.bid == Decimal("1500.4")
    assert quote.ask == Decimal("1500.6")
    assert quote.bid_size == 120
    assert quote.ask_size == 80
    assert quote.last_price == Decimal("1500.5")
    assert quote.timestamp == datetime(2026, 10, 6, 4, 45, 30, 250000, tzinfo=UTC)


def test_a_quote_keyed_by_instrument_key_is_still_parsed() -> None:
    """The provider is free to key either way and has not promised which."""
    quote = _quote({"status": "success", "data": {INFY_KEY: _entry()}})

    assert quote.bid == Decimal("1500.4")


def test_an_entry_whose_own_instrument_token_is_a_different_instrument_is_refused() -> None:
    """Bind the data, not the label: a quote under INFY's key that says it is TCS must not pass."""
    body = {
        "status": "success",
        "data": {"NSE_EQ:INFY": _entry(instrument_token="NSE_EQ|INE467B01029")},
    }

    with pytest.raises(UpstoxDataError) as raised:
        _quote(body)

    assert raised.value.code == AcquisitionFailureCode.PROVIDER_SCHEMA_DRIFT


def test_a_reply_with_no_entry_for_the_instrument_is_refused() -> None:
    body = {
        "status": "success",
        "data": {"NSE_EQ:TCS": _entry(instrument_token="NSE_EQ|INE467B01029")},
    }

    with pytest.raises(UpstoxDataError) as raised:
        _quote(body)

    assert raised.value.code == AcquisitionFailureCode.PROVIDER_SCHEMA_DRIFT


@pytest.mark.parametrize(
    "depth",
    [
        {
            "buy": [{"quantity": 0, "price": 0.0, "orders": 0}],
            "sell": [{"quantity": 80, "price": 1500.6}],
        },
        {
            "buy": [{"quantity": 120, "price": 1500.4}],
            "sell": [{"quantity": 0, "price": 0.0, "orders": 0}],
        },
        {"buy": [{"quantity": 0, "price": 1500.4}], "sell": [{"quantity": 80, "price": 1500.6}]},
        {"buy": [{"quantity": 120, "price": 1500.4}], "sell": [{"quantity": 0, "price": 1500.6}]},
    ],
    ids=[
        "no-bid-resting",
        "no-ask-resting",
        "priced-bid-zero-quantity",
        "priced-ask-zero-quantity",
    ],
)
def test_a_side_with_nothing_resting_is_not_manufactured_into_a_zero_price(
    depth: dict[str, Any],
) -> None:
    """Seen live after the close: the best bid level was price 0.0, quantity 0.

    That is the absence of a bid, not a bid of zero. It is refused rather than turned into a
    two-sided quote with a price nobody offered, and it is not mislabelled schema drift.
    """
    body = {"status": "success", "data": {"NSE_EQ:INFY": _entry(depth=depth)}}

    with pytest.raises(UpstoxDataError) as raised:
        _quote(body)

    assert raised.value.code == AcquisitionFailureCode.DATASET_EMPTY


@pytest.mark.parametrize(
    "body",
    [
        {"status": "success", "data": {}},
        {"status": "success"},
        {"status": "success", "data": {"NSE_EQ:INFY": {"instrument_token": INFY_KEY}}},
        {"status": "success", "data": {"NSE_EQ:INFY": _entry(timestamp="not a time")}},
    ],
    ids=["empty-data", "no-data", "no-fields", "bad-timestamp"],
)
def test_a_malformed_reply_still_fails_closed_as_schema_drift(body: dict[str, Any]) -> None:
    with pytest.raises(UpstoxDataError) as raised:
        _quote(body)

    assert raised.value.code == AcquisitionFailureCode.PROVIDER_SCHEMA_DRIFT


def test_an_entry_keyed_by_neither_form_is_found_by_its_own_instrument_token() -> None:
    """The caller's label need not equal the provider's trading symbol (`M&M`, `BAJAJ-AUTO`)."""
    quote = _quote({"status": "success", "data": {"NSE_EQ:SOME-OTHER-LABEL": _entry()}})

    assert quote.bid == Decimal("1500.4")


def test_two_entries_claiming_the_instrument_are_refused_as_ambiguous() -> None:
    body = {"status": "success", "data": {"NSE_EQ:A": _entry(), "NSE_EQ:B": _entry()}}

    with pytest.raises(UpstoxDataError) as raised:
        _quote(body)

    assert raised.value.code == AcquisitionFailureCode.PROVIDER_SCHEMA_DRIFT


def test_a_crossed_book_is_a_typed_failure_not_a_raw_value_error() -> None:
    depth = {
        "buy": [{"quantity": 10, "price": 1500.9, "orders": 1}],
        "sell": [{"quantity": 10, "price": 1500.1, "orders": 1}],
    }

    with pytest.raises(UpstoxDataError) as raised:
        _quote({"status": "success", "data": {"NSE_EQ:INFY": _entry(depth=depth)}})

    assert raised.value.code == AcquisitionFailureCode.PROVIDER_SCHEMA_DRIFT


def test_an_entry_with_no_instrument_token_is_found_by_the_symbol_form_of_its_key() -> None:
    """With no token to match on, the symbol-form key is the only way to find it."""
    entry = _entry()
    del entry["instrument_token"]

    quote = _quote({"status": "success", "data": {"NSE_EQ:INFY": entry}})

    assert quote.bid == Decimal("1500.4")
