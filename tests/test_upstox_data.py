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


def test_upstox_historical_request_without_token_raises_typed_error() -> None:
    client = UpstoxClient(api_key="", access_token="")

    with pytest.raises(UpstoxDataError) as raised:
        client.fetch_historical_bars(
            instrument_key="NSE_EQ|INE009A01021",
            symbol="INFY",
        )

    assert raised.value.code == AcquisitionFailureCode.PROVIDER_UNAUTHORIZED


def test_upstox_quote_request_without_token_raises_typed_error() -> None:
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
