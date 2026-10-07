"""The XBRL reader: safe parsing, contexts found by date, numbers read exactly."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest
from test_filings_builders import TCS_FIXTURE, fact, make_filing

from quant_system.shariah.filings.xbrl import (
    MAX_XBRL_BYTES,
    Period,
    XbrlError,
    parse_decimal,
    parse_xbrl,
)

END = date(2024, 9, 30)
YEAR_TO_DATE = Period(date(2024, 4, 1), END)
QUARTER = Period(date(2024, 7, 1), END)
SHEET_DATE = Period(None, END)


def test_real_filing_year_to_date_comes_from_its_own_dates_not_the_name_FourD() -> None:
    doc = parse_xbrl(TCS_FIXTURE.read_bytes())
    # The filing declares FourD with the quarter's dates; its own reporting-period fact says April.
    assert doc.duration_periods(END) == [YEAR_TO_DATE, QUARTER]
    assert doc.read_number("RevenueFromOperations", YEAR_TO_DATE).value == Decimal(
        "1268720000000.00"
    )
    assert doc.read_number("RevenueFromOperations", QUARTER).value == Decimal("642590000000.00")
    assert doc.read_number("Assets", SHEET_DATE).value == Decimal("1611240000000.00")


@pytest.mark.parametrize("nse_quirk", [False, True])
def test_context_ids_are_never_used_to_find_periods(nse_quirk: bool) -> None:
    doc = parse_xbrl(make_filing(nse_quirk=nse_quirk))
    assert doc.duration_periods(END) == [YEAR_TO_DATE, QUARTER]
    assert doc.read_number("OtherIncome", YEAR_TO_DATE).value == Decimal("16910000000.00")
    assert doc.read_number("OtherIncome", QUARTER).value == Decimal("7290000000.00")


def test_facts_under_a_dimension_are_ignored() -> None:
    # make_filing also files a 999,999,999,999 revenue under a segment context.
    doc = parse_xbrl(make_filing())
    reading = doc.read_number("RevenueFromOperations", QUARTER)
    assert reading.value == Decimal("642590000000.00")
    assert reading.problem is None


def test_no_balance_sheet_instant_when_the_filing_has_none() -> None:
    doc = parse_xbrl(make_filing(with_balance_sheet=False))
    assert doc.has_instant(END) is False
    assert parse_xbrl(make_filing()).has_instant(END) is True
    assert parse_xbrl(make_filing()).has_instant(date(2024, 12, 31)) is False


@pytest.mark.parametrize(
    "raw",
    [
        b'<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "b">]><x/>',
        b'<?xml version="1.0"?><!DOCTYPE x SYSTEM "http://evil.example/x.dtd"><x/>',
        b'<!doctype x [<!entity a "b">]><x/>',
        b'<?xml version="1.0"?><x>&xxe;</x><!ENTITY xxe SYSTEM "file:///etc/passwd">',
        (
            b'<?xml version="1.0"?><!DOCTYPE lolz [<!ENTITY lol "lol">'
            b'<!ENTITY lol2 "&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;&lol;">]><lolz>&lol2;</lolz>'
        ),
        '<?xml version="1.0" encoding="UTF-16"?><!DOCTYPE x [<!ENTITY a "b">]><x/>'.encode(
            "utf-16"
        ),
    ],
    ids=["entity", "external-dtd", "lowercase", "xxe", "billion-laughs", "utf16-evasion"],
)
def test_doctype_and_entities_are_refused_before_parsing(raw: bytes) -> None:
    with pytest.raises(XbrlError) as caught:
        parse_xbrl(raw)
    assert "safely" in str(caught.value)


def test_oversized_input_is_refused() -> None:
    with pytest.raises(XbrlError) as caught:
        parse_xbrl(b"<x>" + b"a" * MAX_XBRL_BYTES + b"</x>")
    assert "too large" in str(caught.value)


@pytest.mark.parametrize("raw", [b"", b"not xml at all", b"<a><b></a>", b"\xff\xfe\x00bad"])
def test_malformed_input_is_a_typed_error_not_a_crash(raw: bytes) -> None:
    with pytest.raises(XbrlError):
        parse_xbrl(raw)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1611240000000.00", Decimal("1611240000000.00")),
        ("  42 ", Decimal("42")),
        ("-5.5", Decimal("-5.5")),
        ("0.00", Decimal("0.00")),
        ("", None),
        ("abc", None),
        ("1e5", None),
        ("NaN", None),
        ("Infinity", None),
        ("1,000", None),
        ("12O", None),
        ("١٢٣", None),
        ("1" * 60, None),
    ],
)
def test_parse_decimal_is_strict(text: str, expected: Decimal | None) -> None:
    result = parse_decimal(text)
    assert result == expected
    assert (result is None) == (expected is None)


def test_decimal_values_keep_their_filed_precision() -> None:
    reading = parse_xbrl(make_filing(balance={"Assets": "1611240000000.10"})).read_number(
        "Assets", SHEET_DATE
    )
    assert reading.value == Decimal("1611240000000.10")
    assert str(reading.value) == "1611240000000.10"
    assert reading.decimals == "-7"


def test_a_malformed_number_is_missing_with_a_plain_reason() -> None:
    doc = parse_xbrl(make_filing(balance={"Assets": "12O0.00"}))
    reading = doc.read_number("Assets", SHEET_DATE)
    assert reading.value is None
    assert reading.problem == "is not a valid number"


def test_conflicting_values_for_one_period_are_missing_not_guessed() -> None:
    extra = fact("OtherIncome", "Zq", "8000000000.00")
    raw = make_filing().replace(b"</xbrli:xbrl>", extra.encode() + b"</xbrli:xbrl>")
    reading = parse_xbrl(raw).read_number("OtherIncome", QUARTER)
    assert reading.value is None
    assert reading.problem == "is filed twice with different values"


def test_a_repeated_identical_value_is_fine() -> None:
    extra = fact("OtherIncome", "Zq", "7290000000.00")
    raw = make_filing().replace(b"</xbrli:xbrl>", extra.encode() + b"</xbrli:xbrl>")
    assert parse_xbrl(raw).read_number("OtherIncome", QUARTER).value == Decimal("7290000000.00")


def test_an_amount_not_in_rupees_is_not_read() -> None:
    raw = make_filing().replace(
        b'<in-bse-fin:Assets contextRef="Zb" unitRef="INR"',
        b'<in-bse-fin:Assets contextRef="Zb" unitRef="USD"',
    )
    reading = parse_xbrl(raw).read_number("Assets", SHEET_DATE)
    assert reading.value is None
    assert reading.problem == "is not filed in Indian rupees"


def test_a_nil_fact_is_missing() -> None:
    raw = make_filing().replace(
        b'<in-bse-fin:Assets contextRef="Zb" unitRef="INR" decimals="-7">1611240000000.00',
        b'<in-bse-fin:Assets xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        b'xsi:nil="true" contextRef="Zb" unitRef="INR" decimals="-7">',
    )
    assert parse_xbrl(raw).read_number("Assets", SHEET_DATE).value is None


def test_absent_tag_has_no_value_and_no_problem() -> None:
    reading = parse_xbrl(make_filing()).read_number("NotATag", SHEET_DATE)
    assert (reading.value, reading.problem) == (None, None)


def test_text_facts_and_entry_point_are_exposed() -> None:
    doc = parse_xbrl(make_filing(nature="Standalone"))
    assert doc.read_text("NatureOfReportStandaloneConsolidated") == "Standalone"
    assert doc.read_text("NotATag") is None
    assert doc.schema_ref == "Ind-AS_entry_point_2020-03-31.xsd"
    assert "Assets" in doc.tags


def test_text_values_for_a_tag_are_listed_in_filed_order() -> None:
    doc = parse_xbrl(TCS_FIXTURE.read_bytes())
    assert doc.read_texts("DescriptionOfReportableSegment") == [
        "Banking, Financial Services and Insurance",
        "Communication, Media and Technology",
        "Consumer Business",
        "Life Sciences and Healthcare",
        "Manufacturing",
        "Others",
    ]
    assert doc.read_texts("NotATag") == []


@pytest.mark.parametrize("encoding", ["cp037", "UTF-16", "iso-8859-1", "utf-7"])
def test_a_declared_encoding_other_than_utf8_is_refused(encoding: str) -> None:
    raw = f'<?xml version="1.0" encoding="{encoding}"?><x/>'.encode()
    with pytest.raises(XbrlError) as caught:
        parse_xbrl(raw)
    assert "safely" in str(caught.value)
