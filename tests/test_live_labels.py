"""A price is the last close only when it is dated the last trading day, and a quiet share says when it last traded.

No test here touches the network: labels are decided from a clock and a time that the test supplies.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest

from quant_system.live import messages
from quant_system.live.entries import RawQuote, entry_from_quote
from quant_system.live.market_hours import IST, last_trading_date
from tests.live_fakes import FRESH, TCS_LISTING, FakeTransport, build, reply, tick


def ist(*moment: int) -> datetime:
    return datetime(*moment, tzinfo=IST)


SATURDAY = ist(2026, 10, 3, 10, 0)
SUNDAY = ist(2026, 10, 4, 12, 0)
MONDAY_EARLY = ist(2026, 10, 5, 8, 0)
TUESDAY_OPEN = ist(2026, 10, 6, 10, 30)
TUESDAY_EVENING = ist(2026, 10, 6, 16, 30)


@pytest.mark.parametrize(
    ("moment", "expected"),
    [
        pytest.param(TUESDAY_OPEN, date(2026, 10, 6), id="tuesday-midday"),
        pytest.param(TUESDAY_EVENING, date(2026, 10, 6), id="tuesday-evening"),
        pytest.param(ist(2026, 10, 6, 9, 15), date(2026, 10, 6), id="the-open-itself"),
        pytest.param(
            ist(2026, 10, 6, 9, 14, 59), date(2026, 10, 5), id="one-second-before-the-open"
        ),
        pytest.param(ist(2026, 10, 6, 1, 30), date(2026, 10, 5), id="small-hours"),
        pytest.param(MONDAY_EARLY, date(2026, 10, 2), id="monday-before-the-open-is-friday"),
        pytest.param(ist(2026, 10, 5, 9, 15), date(2026, 10, 5), id="monday-at-the-open"),
        pytest.param(SATURDAY, date(2026, 10, 2), id="saturday"),
        pytest.param(ist(2026, 10, 4, 23, 59), date(2026, 10, 2), id="sunday-night"),
        pytest.param(datetime(2026, 10, 6, 20, 0, tzinfo=UTC), date(2026, 10, 6), id="utc-evening"),
        pytest.param(datetime(2026, 10, 6, 5, 0), date(2026, 10, 6), id="a-clock-without-a-zone"),
    ],
)
def test_the_last_trading_date_is_the_most_recent_weekday_whose_session_has_begun(
    moment: datetime, expected: date
) -> None:
    assert last_trading_date(moment) == expected


CLOSE = messages.MARKET_CLOSED
OLDER = "This price is from {}, older than the last trading day."
LABEL_CASES = [
    pytest.param(SUNDAY, ist(2026, 10, 2, 15, 30), "LAST_CLOSE", CLOSE, id="sunday-friday-close"),
    pytest.param(
        SATURDAY, ist(2026, 10, 2, 15, 29), "LAST_CLOSE", CLOSE, id="saturday-friday-close"
    ),
    pytest.param(
        MONDAY_EARLY, ist(2026, 10, 2, 15, 30), "LAST_CLOSE", CLOSE, id="monday-early-friday-close"
    ),
    pytest.param(
        TUESDAY_EVENING, ist(2026, 10, 6, 15, 29, 58), "LAST_CLOSE", CLOSE, id="tuesday-evening"
    ),
    pytest.param(
        datetime(2026, 10, 6, 20, 0, tzinfo=UTC),
        ist(2026, 10, 6, 15, 30),
        "LAST_CLOSE",
        CLOSE,
        id="wednesday-small-hours-tuesday-close",
    ),
    pytest.param(
        SUNDAY,
        datetime(2026, 10, 2, 18, 0, tzinfo=UTC),
        "LAST_CLOSE",
        CLOSE,
        id="a-quote-written-in-utc-is-dated-by-the-india-clock",
    ),
    pytest.param(
        SUNDAY, ist(2026, 9, 4, 15, 30), "DELAYED", OLDER.format("04 Sep"), id="thirty-days-old"
    ),
    pytest.param(
        SUNDAY,
        ist(2026, 10, 1, 15, 30),
        "DELAYED",
        OLDER.format("01 Oct"),
        id="thursday-on-a-sunday",
    ),
    pytest.param(
        MONDAY_EARLY,
        ist(2026, 10, 1, 15, 30),
        "DELAYED",
        OLDER.format("01 Oct"),
        id="a-session-missed",
    ),
    pytest.param(
        TUESDAY_EVENING,
        ist(2026, 10, 5, 15, 30),
        "DELAYED",
        OLDER.format("05 Oct"),
        id="yesterdays-price-after-todays-close",
    ),
    pytest.param(
        MONDAY_EARLY,
        ist(2026, 10, 5, 8, 0),
        "DELAYED",
        "This price is dated 05 Oct, which does not match the last trading day.",
        id="dated-before-the-open-today",
    ),
    pytest.param(SUNDAY, None, "DELAYED", messages.NO_TIME, id="closed-and-no-time"),
    pytest.param(TUESDAY_OPEN, ist(2026, 10, 6, 10, 29, 45), "LIVE", None, id="open-and-fresh"),
    pytest.param(TUESDAY_OPEN, ist(2026, 10, 6, 10, 29, 1), "LIVE", None, id="open-59-seconds-old"),
    pytest.param(
        TUESDAY_OPEN,
        ist(2026, 10, 6, 10, 29, 0),
        "DELAYED",
        messages.OLD_PRICE,
        id="open-60-seconds-old",
    ),
    pytest.param(TUESDAY_OPEN, ist(2026, 10, 6, 10, 30, 4), "LIVE", None, id="4-seconds-ahead"),
    pytest.param(TUESDAY_OPEN, ist(2026, 10, 6, 10, 30, 5), "LIVE", None, id="5-seconds-ahead"),
    pytest.param(
        TUESDAY_OPEN,
        ist(2026, 10, 6, 10, 30, 6),
        "DELAYED",
        messages.CLOCK_MISMATCH,
        id="6-seconds-ahead",
    ),
    pytest.param(
        TUESDAY_OPEN,
        ist(2026, 10, 6, 10, 30, 59),
        "DELAYED",
        messages.CLOCK_MISMATCH,
        id="59-seconds-ahead",
    ),
    pytest.param(
        SATURDAY,
        ist(2026, 10, 3, 10, 1),
        "DELAYED",
        messages.CLOCK_MISMATCH,
        id="ahead-while-closed",
    ),
]


@pytest.mark.parametrize(("now", "quoted_at", "label", "message"), LABEL_CASES)
def test_a_price_is_labelled_by_its_own_date_and_by_how_far_it_is_from_the_clock(
    now: datetime, quoted_at: datetime | None, label: str, message: str | None
) -> None:
    entry = entry_from_quote(RawQuote(100.0, 1.0, quoted_at), now)
    assert (entry.label.value, entry.message) == (label, message)


def test_a_thirty_day_old_price_on_a_sunday_is_not_called_the_last_close() -> None:
    entry = entry_from_quote(RawQuote(100.0, 1.0, SUNDAY - timedelta(days=30)), SUNDAY)
    assert entry.label.value == "DELAYED"
    assert "last closing price" not in str(entry.message)


# ------------------------------------------------------------------------------ a quiet share

QUOTED = ist(2026, 10, 6, 10, 29, 45)
QUIET = [
    pytest.param(
        TUESDAY_OPEN,
        QUOTED,
        QUOTED - timedelta(minutes=10),
        ("LIVE", "2026-10-06T10:19:45+05:30", "This share last traded at 10:19."),
        id="ten-minutes-quiet-is-still-live-by-the-feed-time",
    ),
    pytest.param(
        TUESDAY_OPEN,
        QUOTED,
        QUOTED - timedelta(minutes=5, seconds=1),
        ("LIVE", "2026-10-06T10:24:44+05:30", "This share last traded at 10:24."),
        id="just-over-five-minutes",
    ),
    pytest.param(
        TUESDAY_OPEN,
        QUOTED,
        QUOTED - timedelta(minutes=5),
        ("LIVE", "2026-10-06T10:29:45+05:30", None),
        id="exactly-five-minutes-is-not-quiet",
    ),
    pytest.param(
        TUESDAY_OPEN,
        QUOTED,
        QUOTED - timedelta(seconds=40),
        ("LIVE", "2026-10-06T10:29:45+05:30", None),
        id="a-recent-trade",
    ),
    pytest.param(
        TUESDAY_OPEN,
        QUOTED,
        QUOTED + timedelta(minutes=9),
        ("LIVE", "2026-10-06T10:29:45+05:30", None),
        id="a-trade-after-the-feed-time-is-ignored",
    ),
    pytest.param(
        TUESDAY_OPEN,
        QUOTED,
        None,
        ("LIVE", "2026-10-06T10:29:45+05:30", None),
        id="no-trade-time",
    ),
    pytest.param(
        TUESDAY_OPEN,
        QUOTED,
        ist(2026, 10, 5, 15, 29, 30),
        (
            "LIVE",
            "2026-10-05T15:29:30+05:30",
            "This share last traded on 05 Oct at 15:29.",
        ),
        id="last-traded-yesterday-names-the-day",
    ),
    pytest.param(
        TUESDAY_OPEN,
        ist(2026, 10, 6, 10, 20, 0),
        ist(2026, 10, 6, 10, 0, 0),
        (
            "DELAYED",
            "2026-10-06T10:00:00+05:30",
            "This price is more than a minute old. This share last traded at 10:00.",
        ),
        id="a-delayed-quiet-price-keeps-both-messages",
    ),
    pytest.param(
        TUESDAY_EVENING,
        ist(2026, 10, 6, 15, 29, 58),
        ist(2026, 10, 6, 14, 10, 0),
        (
            "LAST_CLOSE",
            "2026-10-06T14:10:00+05:30",
            "The market is closed. This is the last closing price. This share last traded at 14:10.",
        ),
        id="the-last-close-of-a-quiet-share",
    ),
]


@pytest.mark.parametrize(("now", "quoted_at", "traded_at", "expected"), QUIET)
def test_a_quiet_share_is_not_presented_as_freshly_traded(
    now: datetime,
    quoted_at: datetime,
    traded_at: datetime | None,
    expected: tuple[str, str, str | None],
) -> None:
    entry = entry_from_quote(RawQuote(100.0, 1.0, quoted_at, traded_at), now)
    assert (entry.label.value, entry.as_of, entry.message) == expected


LAST_TRADE_MS = str(
    int(datetime(2026, 10, 6, 4, 50, tzinfo=UTC).timestamp() * 1000)
)  # 10:20 in India


def _entry(**extra: Any) -> dict[str, Any]:
    row = {**tick(TCS_LISTING, 4000.5, "2026-10-06T10:29:45.78+05:30"), **extra}
    return build(FakeTransport(reply({"NSE_EQ:TCS": row}))).quotes(["TCS"])["TCS"]


@pytest.mark.parametrize("value", [LAST_TRADE_MS, int(LAST_TRADE_MS)], ids=["text", "number"])
def test_the_last_trade_time_in_the_real_reply_is_read_as_epoch_milliseconds(value: Any) -> None:
    entry = _entry(last_trade_time=value)
    assert (entry["label"], entry["as_of"], entry["message"]) == (
        "LIVE",
        "2026-10-06T10:20:00+05:30",
        "This share last traded at 10:20.",
    )


@pytest.mark.parametrize(
    "value",
    [
        pytest.param("abc", id="not-a-number"),
        pytest.param("", id="empty"),
        pytest.param(None, id="null"),
        pytest.param(True, id="a-flag"),
        pytest.param([1], id="a-list"),
        pytest.param(-int(LAST_TRADE_MS), id="negative"),
        pytest.param(LAST_TRADE_MS[:-1], id="twelve-digits"),
        pytest.param(LAST_TRADE_MS + "0", id="fourteen-digits"),
        pytest.param(float(LAST_TRADE_MS), id="a-fraction"),
        pytest.param("١٧٩١٢٦٢٢٠٠٠٠٠", id="other-script-digits"),
        pytest.param("0", id="never-traded"),
    ],
)
def test_a_last_trade_time_that_cannot_be_read_is_ignored_and_the_price_is_still_shown(
    value: Any,
) -> None:
    entry = _entry(last_trade_time=value)
    assert (entry["label"], entry["as_of"], entry["message"], entry["last_price"]) == (
        "LIVE",
        "2026-10-06T10:29:45+05:30",
        None,
        4000.5,
    )


def test_the_real_reply_shape_is_read_as_the_label_rule_says() -> None:
    """Measured on the real feed: a fractional-second time with a zone, and an epoch-millisecond string."""
    row = {**tick(TCS_LISTING, 4000.5, FRESH), "last_trade_time": LAST_TRADE_MS}
    entry = build(FakeTransport(reply({"NSE_EQ:TCS": row}))).quotes(["TCS"])["TCS"]
    assert entry["label"] == "LIVE" and entry["as_of"].endswith("+05:30")
