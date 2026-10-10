"""The NSE client: what it may ask for, how politely, and how it fails. No network is touched."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from datetime import date
from pathlib import Path
from typing import Any

import httpx
import pytest

from quant_system.shariah.filings.models import IndustryGroup
from quant_system.shariah.filings.nse_client import (
    MAX_RESPONSE_BYTES,
    FilingsBlocked,
    FilingsError,
    FilingsNotFound,
    FilingsRefused,
    FilingsUnavailable,
    HttpxTransport,
    InvalidSymbol,
    NseFilingsClient,
    TransportError,
    TransportResponse,
)

INDUSTRY_URL = "https://nsearchives.nseindia.com/content/indices/ind_niftytotalmarket_list.csv"
INDUSTRY_CSV = (
    Path(__file__).resolve().parent.parent
    / "fixtures"
    / "shariah_filings"
    / "industry_list_sample.csv"
)
LIST = "https://www.nseindia.com/api/corporates-financial-results"
ARCHIVE = "https://nsearchives.nseindia.com/corporate/xbrl/"
Q2 = ARCHIVE + "INDAS_112733_1265368_10102024065944.xml"
Q2_STANDALONE = ARCHIVE + "INDAS_112731_1265360_10102024065500.xml"
MAR = ARCHIVE + "INDAS_104001_1100000_20052024060000.xml"


class FakeClock:
    """A clock that only moves when the fake sleep is called."""

    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


class FakeTransport:
    def __init__(self, handler: Callable[[str], TransportResponse | Exception]) -> None:
        self.handler = handler
        self.urls: list[str] = []
        self.headers: list[Mapping[str, str]] = []
        self.max_bytes: list[int] = []

    def get(
        self, url: str, headers: Mapping[str, str], timeout: float, max_bytes: int
    ) -> TransportResponse:
        self.urls.append(url)
        self.headers.append(headers)
        self.max_bytes.append(max_bytes)
        outcome = self.handler(url)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def ok(body: bytes, **headers: str) -> TransportResponse:
    return TransportResponse(200, headers, body)


def listing_row(**changes: Any) -> dict[str, Any]:
    row: dict[str, Any] = {
        "symbol": "TCS",
        "companyName": "Tata Consultancy Services Limited",
        "isin": "INE467B01029",
        "toDate": "30-Sep-2024",
        "fromDate": "01-Jul-2024",
        "relatingTo": "Second Quarter",
        "period": "Quarterly",
        "consolidated": "Consolidated",
        "audited": "Audited",
        "indAs": "Ind-AS New",
        "bank": "N",
        "filingDate": "10-Oct-2024 18:59",
        "xbrl": Q2,
        "resultDetailedDataLink": None,
    }
    row.update(changes)
    return row


def make_client(
    handler: Callable[[str], TransportResponse | Exception], pause: float = 1.2
) -> tuple[NseFilingsClient, FakeTransport, FakeClock]:
    transport = FakeTransport(handler)
    clock = FakeClock()
    client = NseFilingsClient(transport, clock.sleep, clock.monotonic, pause)
    return client, transport, clock


def by_period(quarterly: list[dict[str, Any]], half: list[dict[str, Any]]) -> Callable[[str], Any]:
    def handler(url: str) -> TransportResponse:
        rows = half if "Half-Yearly" in url else quarterly
        return ok(json.dumps(rows).encode())

    return handler


def test_list_results_merges_both_lists_and_drops_duplicates_and_rows_without_a_filing() -> None:
    quarterly = [
        listing_row(),
        listing_row(consolidated="Non-Consolidated", xbrl=Q2_STANDALONE),
        listing_row(toDate="30-Jun-2024", xbrl=ARCHIVE + "-"),
    ]
    half = [
        listing_row(relatingTo="First Half", period="Half-Yearly"),
        listing_row(toDate="31-Mar-2024", xbrl=MAR),
    ]
    client, transport, _ = make_client(by_period(quarterly, half))
    rows = client.list_results("TCS")
    assert sorted(row.xbrl_url for row in rows) == sorted([Q2, Q2_STANDALONE, MAR])
    assert transport.urls == [
        f"{LIST}?index=equities&symbol=TCS&period=Quarterly",
        f"{LIST}?index=equities&symbol=TCS&period=Half-Yearly",
    ]


def test_list_rows_are_typed() -> None:
    client, _, _ = make_client(by_period([listing_row()], []))
    row = client.list_results("TCS")[0]
    assert row.symbol == "TCS"
    assert row.period_end == date(2024, 9, 30)
    assert row.filed_on == date(2024, 10, 10)
    assert (row.consolidated, row.audited, row.ind_as, row.lender_flag) == (True, True, True, "N")
    assert row.relating_to == "Second Quarter"
    assert row.isin == "INE467B01029"
    assert row.detail_url is None


@pytest.mark.parametrize(
    ("changes", "consolidated", "audited", "ind_as", "flag"),
    [
        ({"consolidated": "Non-Consolidated"}, False, True, True, "N"),
        ({"audited": "Un-Audited"}, True, False, True, "N"),
        ({"indAs": "Ind-AS"}, True, True, True, "N"),
        ({"indAs": "Non-Ind-AS"}, True, True, False, "N"),
        ({"indAs": "NBFC-IND", "bank": "F"}, True, True, False, "F"),
        ({"bank": "B", "indAs": "Non-Ind-AS"}, True, True, False, "B"),
    ],
)
def test_listing_flags_are_read_conservatively(
    changes: dict[str, str], consolidated: bool, audited: bool, ind_as: bool, flag: str
) -> None:
    client, _, _ = make_client(by_period([listing_row(**changes)], []))
    row = client.list_results("TCS")[0]
    assert (row.consolidated, row.audited, row.ind_as, row.lender_flag) == (
        consolidated,
        audited,
        ind_as,
        flag,
    )


def test_a_detail_link_is_kept_only_when_it_is_on_nse() -> None:
    kept = (
        "https://nsearchives.nseindia.com/archives/financial_results/financial_res_TCS_99877.html"
    )
    rows = [
        listing_row(resultDetailedDataLink=kept),
        listing_row(xbrl=MAR, resultDetailedDataLink="https://evil.example/x.html"),
    ]
    client, _, _ = make_client(by_period(rows, []))
    found = {row.xbrl_url: row.detail_url for row in client.list_results("TCS")}
    assert found == {Q2: kept, MAR: None}


@pytest.mark.parametrize(
    "symbol", ["", "TCS;rm -rf", "../x", "A" * 16, "T CS", "TCS\n", "ТСS", "TCS%26"]
)
def test_a_bad_symbol_is_refused_before_any_request(symbol: str) -> None:
    client, transport, _ = make_client(by_period([], []))
    with pytest.raises(InvalidSymbol) as caught:
        client.list_results(symbol)
    assert transport.urls == []
    assert "symbol" in str(caught.value)


@pytest.mark.parametrize(
    ("symbol", "expected"),
    [("tcs", "TCS"), ("M&M", "M%26M"), ("BAJAJ-AUTO", "BAJAJ-AUTO"), ("L&TFH", "L%26TFH")],
)
def test_symbols_are_upper_cased_and_encoded_in_the_request(symbol: str, expected: str) -> None:
    client, transport, _ = make_client(by_period([], []))
    client.list_results(symbol)
    assert transport.urls[0] == f"{LIST}?index=equities&symbol={expected}&period=Quarterly"


def test_requests_look_like_a_browser_and_carry_no_cookies() -> None:
    client, transport, _ = make_client(by_period([], []))
    client.list_results("TCS")
    headers = transport.headers[0]
    assert headers["User-Agent"].startswith("Mozilla/5.0")
    assert "cookie" not in {name.lower() for name in headers}
    assert transport.max_bytes[0] == MAX_RESPONSE_BYTES == 8 * 1024 * 1024


def test_a_403_is_blocked_with_a_plain_message_and_is_not_retried() -> None:
    client, transport, clock = make_client(lambda url: TransportResponse(403, {}, b"denied"))
    with pytest.raises(FilingsBlocked) as caught:
        client.list_results("TCS")
    assert str(caught.value) == (
        "NSE is not letting QuantOS read this company's filings right now. Try again later."
    )
    assert len(transport.urls) == 1
    assert clock.sleeps == []


@pytest.mark.parametrize("status", [401, 429])
def test_other_refusals_are_also_blocked(status: int) -> None:
    client, transport, _ = make_client(lambda url: TransportResponse(status, {}, b""))
    with pytest.raises(FilingsBlocked):
        client.list_results("TCS")
    assert len(transport.urls) == 1


@pytest.mark.parametrize(
    "outcome",
    [TransportError("boom"), TransportResponse(500, {}, b""), TransportResponse(503, {}, b"")],
    ids=["no-answer", "500", "503"],
)
def test_no_answer_is_unavailable_with_a_plain_message_and_no_retry(
    outcome: TransportError | TransportResponse,
) -> None:
    client, transport, _ = make_client(lambda url: outcome)
    with pytest.raises(FilingsUnavailable) as caught:
        client.list_results("TCS")
    assert str(caught.value) == "NSE did not answer. Check your internet connection and try again."
    assert len(transport.urls) == 1


@pytest.mark.parametrize("body", [b"<html>blocked</html>", b"", b'{"data": []}', b"42"])
def test_an_answer_that_is_not_a_list_is_unreadable(body: bytes) -> None:
    client, _, _ = make_client(lambda url: ok(body))
    with pytest.raises(FilingsUnavailable) as caught:
        client.list_results("TCS")
    assert str(caught.value) == "NSE sent an answer QuantOS could not read. Try again later."


@pytest.mark.parametrize(
    "error",
    [
        FilingsBlocked(),
        FilingsUnavailable(),
        FilingsRefused("x"),
        FilingsNotFound(),
        InvalidSymbol(),
    ],
)
def test_error_messages_never_use_code_terms(error: FilingsError) -> None:
    message = str(error).lower()
    banned = ["403", "404", "http", "json", "exception", "traceback", "status", "url", "xml"]
    assert [word for word in banned if word in message] == []


def listed_client(
    handler: Callable[[str], TransportResponse | Exception],
) -> tuple[NseFilingsClient, FakeTransport, FakeClock]:
    def route(url: str) -> TransportResponse | Exception:
        if url.startswith(LIST):
            return ok(json.dumps([listing_row()]).encode())
        return handler(url)

    client, transport, clock = make_client(route)
    client.list_results("TCS")
    transport.urls.clear()
    return client, transport, clock


def test_a_listed_filing_is_fetched_as_bytes() -> None:
    client, transport, _ = listed_client(lambda url: ok(b"<xbrl/>"))
    assert client.fetch_xbrl(Q2) == b"<xbrl/>"
    assert transport.urls == [Q2]


@pytest.mark.parametrize(
    "url",
    [
        "http://nsearchives.nseindia.com/corporate/xbrl/a.xml",
        "https://evil.example/a.xml",
        "https://nsearchives.nseindia.com.evil.example/a.xml",
        "https://nsearchives.nseindia.com@evil.example/a.xml",
        "https://user@nsearchives.nseindia.com/corporate/xbrl/a.xml",
        "https://nsearchives.nseindia.com:8443/corporate/xbrl/a.xml",
        "ftp://nsearchives.nseindia.com/a.xml",
        "file:///etc/passwd",
        "//nsearchives.nseindia.com/a.xml",
        "https://www.nseindia.com/api/anything-else",
        ARCHIVE + "INDAS_999_never_listed.xml",
    ],
)
def test_only_listed_https_urls_on_the_two_nse_hosts_may_be_fetched(url: str) -> None:
    client, transport, _ = listed_client(lambda _url: ok(b"<xbrl/>"))
    with pytest.raises(FilingsRefused) as caught:
        client.fetch_xbrl(url)
    assert transport.urls == []
    assert "NSE" in str(caught.value)


def test_a_listing_row_pointing_at_another_host_is_dropped_and_cannot_be_fetched() -> None:
    evil = "https://evil.example/corporate/xbrl/x.xml"
    client, transport, _ = make_client(by_period([listing_row(xbrl=evil)], []))
    assert client.list_results("TCS") == []
    with pytest.raises(FilingsRefused):
        client.fetch_xbrl(evil)
    assert len(transport.urls) == 2


def redirect(location: str, status: int = 302) -> TransportResponse:
    return TransportResponse(status, {"location": location}, b"")


@pytest.mark.parametrize(
    "location",
    [
        "https://evil.example/a.xml",
        "https://www.nseindia.com/other",
        "http://nsearchives.nseindia.com/corporate/xbrl/a.xml",
        "https://nsearchives.nseindia.com.evil.example/a.xml",
    ],
)
def test_a_redirect_to_another_host_is_refused(location: str) -> None:
    client, transport, _ = listed_client(lambda url: redirect(location))
    with pytest.raises(FilingsRefused):
        client.fetch_xbrl(Q2)
    assert transport.urls == [Q2]


def test_a_redirect_within_the_same_host_is_followed_and_paced() -> None:
    def handler(url: str) -> TransportResponse:
        return (
            ok(b"<xbrl/>") if url.endswith("moved.xml") else redirect("/corporate/xbrl/moved.xml")
        )

    client, transport, clock = listed_client(handler)
    assert client.fetch_xbrl(Q2) == b"<xbrl/>"
    assert transport.urls == [Q2, ARCHIVE + "moved.xml"]
    assert clock.sleeps == [1.2, 1.2, 1.2]


def test_a_redirect_loop_is_stopped() -> None:
    client, transport, _ = listed_client(lambda url: redirect("/corporate/xbrl/loop.xml"))
    with pytest.raises(FilingsRefused):
        client.fetch_xbrl(Q2)
    assert len(transport.urls) <= 4


def test_a_missing_filing_is_not_found_in_plain_words() -> None:
    client, _, _ = listed_client(lambda url: TransportResponse(404, {}, b""))
    with pytest.raises(FilingsNotFound) as caught:
        client.fetch_xbrl(Q2)
    assert str(caught.value) == "NSE no longer has this filing. Try again later."


def test_a_response_over_eight_megabytes_is_refused() -> None:
    client, transport, _ = listed_client(lambda url: ok(b"a" * (MAX_RESPONSE_BYTES + 1)))
    with pytest.raises(FilingsRefused) as caught:
        client.fetch_xbrl(Q2)
    assert "too large" in str(caught.value)
    assert transport.max_bytes[-1] == MAX_RESPONSE_BYTES


def test_requests_are_paced_with_the_injected_sleep() -> None:
    client, _, clock = make_client(by_period([listing_row()], []))
    client.list_results("TCS")
    assert clock.sleeps == [1.2]
    client.fetch_xbrl(Q2)
    assert clock.sleeps == [1.2, 1.2]


def test_no_pause_is_added_when_enough_time_has_passed() -> None:
    client, _, clock = make_client(by_period([listing_row()], []))
    client.list_results("TCS")
    clock.now += 30.0
    client.fetch_xbrl(Q2)
    assert clock.sleeps == [1.2]


def test_the_pause_cannot_be_set_below_the_polite_minimum() -> None:
    client, _, clock = make_client(by_period([], []), pause=0.0)
    client.list_results("TCS")
    assert client.pause_seconds >= 1.2
    assert clock.sleeps == [client.pause_seconds]


def test_the_client_can_be_built_with_no_arguments_without_touching_the_network() -> None:
    assert NseFilingsClient().pause_seconds >= 1.2


def mock_httpx(handler: Callable[[httpx.Request], httpx.Response]) -> HttpxTransport:
    return HttpxTransport(httpx.MockTransport(handler))


def test_httpx_transport_does_not_follow_redirects_and_sends_headers() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(302, headers={"Location": "https://evil.example/"})

    response = mock_httpx(handler).get("https://www.nseindia.com/x", {"User-Agent": "UA"}, 5.0, 100)
    assert response.status == 302
    assert response.headers["location"] == "https://evil.example/"
    assert len(seen) == 1
    assert seen[0].headers["user-agent"] == "UA"


def test_httpx_transport_stops_reading_at_the_size_cap() -> None:
    transport = mock_httpx(lambda request: httpx.Response(200, content=b"a" * 5000))
    with pytest.raises(TransportError) as caught:
        transport.get("https://www.nseindia.com/x", {}, 5.0, 1000)
    assert "too large" in str(caught.value)


def test_httpx_transport_returns_the_body_within_the_cap() -> None:
    transport = mock_httpx(lambda request: httpx.Response(200, content=b"hello"))
    assert transport.get("https://www.nseindia.com/x", {}, 5.0, 1000).body == b"hello"


def test_httpx_transport_maps_timeouts_to_a_transport_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(TransportError):
        mock_httpx(handler).get("https://www.nseindia.com/x", {}, 5.0, 1000)


def test_industry_groups_are_read_from_nses_list_by_symbol() -> None:
    client, transport, _ = make_client(lambda url: ok(INDUSTRY_CSV.read_bytes()))
    groups = client.fetch_industry_groups()
    assert transport.urls == [INDUSTRY_URL]
    assert sorted(groups) == ["360ONE", "ABB", "HDFCBANK", "ITC", "M&M", "TCS"]
    assert groups["TCS"] == IndustryGroup(
        "Tata Consultancy Services Ltd.", "Information Technology", "INE467B01029"
    )
    assert groups["M&M"].industry == "Automobile and Auto Components"
    assert groups["ITC"].industry == "Fast Moving Consumer Goods"


def test_the_industry_list_is_paced_and_size_capped_like_every_other_request() -> None:
    client, transport, clock = make_client(by_period([], []))
    client.list_results("TCS")
    transport.handler = lambda url: ok(INDUSTRY_CSV.read_bytes())
    client.fetch_industry_groups()
    assert clock.sleeps == [1.2, 1.2]
    assert transport.max_bytes[-1] == MAX_RESPONSE_BYTES


def test_the_industry_list_may_start_with_a_byte_order_mark() -> None:
    client, _, _ = make_client(lambda url: ok(b"\xef\xbb\xbf" + INDUSTRY_CSV.read_bytes()))
    assert "TCS" in client.fetch_industry_groups()


def test_industry_text_is_cleaned_and_odd_symbols_are_skipped() -> None:
    body = (
        b"Company Name,Industry,Symbol,Series,ISIN Code\n"
        b"Good Ltd.,<b>Capital   Goods</b>,GOOD,EQ,INE000A01011\n"
        b"Bad Ltd.,Power,BA D,EQ,INE000A01012\n"
        b"Worse Ltd.,Power,../X,EQ,INE000A01013\n"
    )
    client, _, _ = make_client(lambda url: ok(body))
    groups = client.fetch_industry_groups()
    assert list(groups) == ["GOOD"]
    assert groups["GOOD"].industry == "Capital Goods"


@pytest.mark.parametrize(
    "body",
    [
        b"<html>blocked</html>",
        b"",
        b"Symbol,Industry\nTCS,IT\n",
        b"Company Name,Industry,Symbol,Series,ISIN Code\n",
    ],
    ids=["html", "empty", "missing-columns", "header-only"],
)
def test_an_industry_list_that_cannot_be_read_is_unavailable(body: bytes) -> None:
    client, _, _ = make_client(lambda url: ok(body))
    with pytest.raises(FilingsUnavailable) as caught:
        client.fetch_industry_groups()
    assert str(caught.value) == "NSE sent an answer QuantOS could not read. Try again later."


def test_a_blocked_industry_list_is_reported_plainly_without_retry() -> None:
    client, transport, _ = make_client(lambda url: TransportResponse(403, {}, b""))
    with pytest.raises(FilingsBlocked):
        client.fetch_industry_groups()
    assert len(transport.urls) == 1


def test_a_redirect_away_from_nse_is_refused_for_the_industry_list_too() -> None:
    client, _, _ = make_client(lambda url: redirect("https://evil.example/list.csv"))
    with pytest.raises(FilingsRefused):
        client.fetch_industry_groups()
