"""Paper books for the retail app: create, follow, stop. Never place an order anywhere.

A book's state is replayed from its saved specification each time the market data changes (see
:mod:`quant_system.lab.paper`); this module only stores specifications, caches the replay per data
build, and keeps the equity recorded for every session so a provider re-adjustment cannot quietly
rewrite a book's past.
"""

from __future__ import annotations

import json
import threading
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

from quant_system.lab import BrokerCharges, LabError
from quant_system.lab.paper import PaperSpec, evaluate_book, latest_session
from quant_system.lab.runner import MAX_STOCKS
from quant_system.lab.templates import get_template
from quant_system.market import MarketIndex
from quant_system.server.v2.auto_update import expected_session
from quant_system.server.v2.state import AppState

MAX_BOOKS = 20
# A recorded session whose replayed equity now differs by more than this was changed by a data
# re-adjustment, not by anything the book did.
REVISION_TOLERANCE = 0.01
_SPARK_POINTS = 60
# A book is measured to the NIFTY reference series' last session. If that series ends more than
# this many trading sessions before the newest prices, a new book would start in the past and its
# "tomorrow's orders" would be orders for a session that has already happened.
MAX_REFERENCE_LAG_SESSIONS = 2
HOLIDAY_FILE = Path("authorities") / "nse-trading-holidays.json"


def _human(day: date | str) -> str:
    """``5 Oct 2026``: the way the rest of the app writes a date (``%-d`` is not portable)."""
    d = day if isinstance(day, date) else date.fromisoformat(day[:10])
    return f"{d.day} {d:%b} {d.year}"


def trading_sessions_between(after: date, upto: date, holidays: frozenset[date]) -> int:
    """Weekday, non-holiday sessions in the half-open range ``(after, upto]``."""
    count = 0
    day = after + timedelta(days=1)
    while day <= upto:
        if day.weekday() < 5 and day not in holidays:
            count += 1
        day += timedelta(days=1)
    return count


def load_holidays(index: MarketIndex) -> frozenset[date]:
    """The NSE holiday list that ships beside the market data, or none when it is absent.

    Without it a market holiday looks like a missing session, which is the safe direction for the
    order check: it can only say "out of date" too early, never "current" too late.
    """
    try:
        folder = index.meta().get("data_folder")
        if not folder:
            return frozenset()
        raw = json.loads((Path(folder) / HOLIDAY_FILE).read_text(encoding="utf-8"))
        return frozenset(date.fromisoformat(str(h["date"])) for h in raw["holidays"])
    except (OSError, ValueError, KeyError, TypeError):
        return frozenset()


def order_freshness(
    *,
    as_of: str | None,
    expected: date,
    newest_data: str | None,
    holidays: frozenset[date],
    stopped: bool = False,
) -> dict[str, Any]:
    """Whether a book's "tomorrow's orders" can still be acted on.

    Orders are decided at a close and fill at the next open. They are current only when no trading
    session has happened since that close. Anyone copying them into a real account needs this
    answered before they see a quantity, so a stale answer must never look like a fresh one.
    """
    if stopped:
        return {
            "state": "STOPPED",
            "as_of": as_of,
            "expected_session": expected.isoformat(),
            "sessions_missed": 0,
            "message": "This book is stopped, so it places no more orders.",
        }
    if as_of is None:
        return {
            "state": "UNKNOWN",
            "as_of": None,
            "expected_session": expected.isoformat(),
            "sessions_missed": 0,
            "message": "This book could not be followed, so there are no orders to place.",
        }
    decided = date.fromisoformat(as_of)
    missed = trading_sessions_between(decided, expected, holidays)
    if missed == 0:
        return {
            "state": "CURRENT",
            "as_of": as_of,
            "expected_session": expected.isoformat(),
            "sessions_missed": 0,
            "message": f"Decided at the close of {_human(as_of)}. They fill at the next session's open.",
        }
    if newest_data is not None and date.fromisoformat(newest_data[:10]) < expected:
        cause = (
            f"Your market data ends on {_human(newest_data)}. Update it in Settings, then Data, "
            "before acting on anything here."
        )
    elif newest_data is not None and decided < date.fromisoformat(newest_data[:10]):
        cause = (
            f"This book is measured only to {_human(as_of)} because its NIFTY reference series "
            f"ends there while prices run to {_human(newest_data)}. Update the market data so the "
            "reference series catches up."
        )
    else:
        cause = "Update the market data before acting on anything here."
    plural = "session has" if missed == 1 else "sessions have"
    return {
        "state": "STALE",
        "as_of": as_of,
        "expected_session": expected.isoformat(),
        "sessions_missed": missed,
        "message": (
            f"These orders are out of date. They were decided at the close of {_human(as_of)}, and "
            f"{missed} trading {plural} passed since. Do not place them. {cause}"
        ),
    }


def orders_decided_at(state: dict[str, Any], as_of: str) -> list[dict[str, Any]]:
    """The orders a book decided at the close of ``as_of``.

    At the book's latest close they are the queue. At an earlier close they are the fills on the
    next session, which is what those orders became.
    """
    if as_of == state["last_session"]:
        return list(state["queued"])
    following = next((row[0] for row in state["curve"] if row[0] > as_of), None)
    if following is None:
        return []
    return [
        {
            "side": t["side"],
            "symbol": t["symbol"],
            "quantity": t["quantity"],
            "reference_price": t["price"],
        }
        for t in state["trades"]
        if t["date"] == following
    ]


def _worse_bps(side: str, yours: float, paper: float) -> float:
    """How much worse your price was than the paper fill, in basis points (negative = better)."""
    sign = 1.0 if side == "BUY" else -1.0
    return sign * (yours - paper) / paper * 10_000.0


def placement_tracking(state: dict[str, Any], placements: list[dict[str, Any]]) -> dict[str, Any]:
    """Your recorded orders against what the paper book did with the same orders.

    Only a price you typed is compared; nothing is guessed for an order you did not record.
    """
    rows: list[dict[str, Any]] = []
    for p in placements:
        decided = {(o["symbol"], o["side"]): o for o in orders_decided_at(state, p["as_of"])}
        paper = decided.get((p["symbol"], p["side"]))
        waiting = p["as_of"] == state["last_session"]
        paper_price = None if waiting or paper is None else paper["reference_price"]
        row: dict[str, Any] = {
            **p,
            "paper_quantity": None if paper is None else paper["quantity"],
            "paper_price": paper_price,
            "state": "WAITING" if waiting else ("FILLED" if paper_price is not None else "NO_FILL"),
            "worse_bps": None,
            "cost": None,
        }
        if p["status"] == "PLACED" and p["price"] is not None and paper_price:
            row["worse_bps"] = _worse_bps(p["side"], p["price"], paper_price)
            sign = 1.0 if p["side"] == "BUY" else -1.0
            row["cost"] = sign * (p["price"] - paper_price) * (p["quantity"] or 0)
        rows.append(row)
    compared = [r for r in rows if r["worse_bps"] is not None]
    engaged = {p["as_of"] for p in placements}
    unrecorded = 0
    for as_of in engaged:
        if as_of == state["last_session"]:
            continue
        recorded = {(p["symbol"], p["side"]) for p in placements if p["as_of"] == as_of}
        unrecorded += sum(
            1 for o in orders_decided_at(state, as_of) if (o["symbol"], o["side"]) not in recorded
        )
    return {
        "rows": rows,
        "placed": sum(1 for r in rows if r["status"] == "PLACED"),
        "skipped": sum(1 for r in rows if r["status"] == "SKIPPED"),
        "waiting": sum(1 for r in rows if r["state"] == "WAITING"),
        "compared": len(compared),
        "mean_worse_bps": (sum(r["worse_bps"] for r in compared) / len(compared))
        if compared
        else None,
        "total_cost": sum(r["cost"] for r in compared) if compared else None,
        "unrecorded": unrecorded,
    }


class PaperBooks:
    def __init__(
        self, state: AppState, clock: Callable[[], datetime] = lambda: datetime.now(UTC)
    ) -> None:
        self._state = state
        self._clock = clock
        self._lock = threading.Lock()
        self._cache: dict[tuple[str, str, str | None], dict[str, Any]] = {}

    def _freshness(self, index: MarketIndex, state: dict[str, Any]) -> dict[str, Any]:
        return order_freshness(
            as_of=state["last_session"],
            expected=expected_session(self._clock()),
            newest_data=index.meta().get("latest_session"),
            holidays=load_holidays(index),
            stopped=state["status"] == "STOPPED",
        )

    def _unknown_orders(self) -> dict[str, Any]:
        return order_freshness(
            as_of=None,
            expected=expected_session(self._clock()),
            newest_data=None,
            holidays=frozenset(),
        )

    def _refuse_lagging_reference(self, index: MarketIndex) -> None:
        reference = latest_session(index)
        newest = index.meta().get("latest_session")
        if not newest:
            return
        lag = trading_sessions_between(
            date.fromisoformat(reference), date.fromisoformat(newest[:10]), load_holidays(index)
        )
        if lag > MAX_REFERENCE_LAG_SESSIONS:
            raise LabError(
                f"The NIFTY reference series ends on {_human(reference)} but prices run to "
                f"{_human(newest)}. "
                "A book started now would begin in the past and its orders would be for a "
                "session that has already happened. Update the market data in Settings, then "
                "Data, and try again."
            )

    # -------------------------------------------------------------------------- creating

    def create(
        self,
        index: MarketIndex,
        *,
        name: str,
        template_id: str,
        params: dict[str, Any],
        scope: str,
        symbols: list[str],
        universe: str | None,
        capital: Decimal,
        slippage_bps: Decimal,
        broker: dict[str, Any],
    ) -> dict[str, Any]:
        clean = " ".join(name.split())
        if not 1 <= len(clean) <= 60:
            raise LabError("Give the book a name of 1 to 60 characters.")
        if sum(1 for b in self._state.paper_books() if b["stopped_session"] is None) >= MAX_BOOKS:
            raise LabError(f"You already have {MAX_BOOKS} paper books running. Stop one first.")
        self._refuse_lagging_reference(index)
        template = get_template(template_id)
        if scope not in template.scopes:
            raise LabError(f"{template.name} cannot be run on a {scope}.")
        if not Decimal("10000") <= capital <= Decimal("1000000000"):
            raise LabError("Starting money must be between ₹10,000 and ₹100 crore.")
        if scope == "stocks" and not 1 <= len(symbols) <= MAX_STOCKS:
            raise LabError(f"Choose between 1 and {MAX_STOCKS} stocks.")
        spec = PaperSpec(
            template_id=template_id,
            params=template.resolve(params),
            scope="universe" if scope == "universe" else "stocks",
            symbols=tuple(s.strip().upper() for s in symbols) if scope == "stocks" else (),
            universe=universe if scope == "universe" else None,
            capital=capital,
            slippage_bps=slippage_bps,
            start_session=latest_session(index),
        )
        # Replay once before saving: a book that cannot be followed is refused now, in words.
        evaluate_book(index, spec, _broker(broker))
        book_id = self._state.create_paper_book(clean, _spec_json(spec), broker)
        return self.detail(index, book_id)

    # ---------------------------------------------------------------------------- reading

    def summaries(self, index: MarketIndex) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for book in self._state.paper_books():
            try:
                state = self._replay(index, book)
            except LabError as err:
                out.append(_broken(book, str(err), self._unknown_orders()))
                continue
            out.append(_summary(book, state, self._freshness(index, state)))
        return out

    def detail(self, index: MarketIndex, book_id: str) -> dict[str, Any]:
        book = self._state.paper_book(book_id)
        if book is None:
            raise KeyError(book_id)
        try:
            state = self._replay(index, book)
        except LabError as err:
            broken = _broken(book, str(err), self._unknown_orders())
            name = get_template(str(book["spec"]["template_id"])).name
            return {
                **broken,
                "template": {"id": book["spec"]["template_id"], "name": name, "summary": ""},
            }
        full = {k: v for k, v in state.items() if k != "session_equity"}
        return {
            "id": book["id"],
            "name": book["name"],
            "created_at": book["created_at"],
            **full,
            "orders": self._freshness(index, state),
            "placements": self._state.placements(str(book["id"])),
            "tracking": placement_tracking(state, self._state.placements(str(book["id"]))),
        }

    def record_placement(
        self,
        index: MarketIndex,
        book_id: str,
        *,
        as_of: str,
        symbol: str,
        side: str,
        status: Literal["PLACED", "SKIPPED"],
        quantity: int | None,
        price: Decimal | None,
    ) -> dict[str, Any]:
        """Note what you did with one of this book's orders. Refused unless the book decided it."""
        book = self._state.paper_book(book_id)
        if book is None:
            raise KeyError(book_id)
        state = self._replay(index, book)
        symbol = symbol.strip().upper()
        if (symbol, side) not in {
            (o["symbol"], o["side"]) for o in orders_decided_at(state, as_of)
        }:
            raise LabError(
                f"This book did not decide to {side.lower()} {symbol} at the close of "
                f"{_human(as_of)}, so there is no order to record."
            )
        if status == "PLACED" and quantity is None:
            raise LabError("Say how many shares you placed.")
        self._state.save_placement(
            book_id, as_of, symbol, side, status, quantity if status == "PLACED" else None, price
        )
        return self.detail(index, book_id)

    def clear_placement(
        self, index: MarketIndex, book_id: str, *, as_of: str, symbol: str, side: str
    ) -> dict[str, Any]:
        if self._state.paper_book(book_id) is None:
            raise KeyError(book_id)
        self._state.clear_placement(book_id, as_of, symbol.strip().upper(), side)
        return self.detail(index, book_id)

    def inbox(self, index: MarketIndex) -> dict[str, Any]:
        """Every running book's orders that are waiting for you, with how many you have dealt with."""
        books: list[dict[str, Any]] = []
        pending_total = 0
        for book in self._state.paper_books():
            if book["stopped_session"] is not None:
                continue
            try:
                state = self._replay(index, book)
            except LabError:
                continue
            orders = self._freshness(index, state)
            if orders["state"] not in ("CURRENT", "STALE") or not state["queued"]:
                continue
            done = {
                (p["symbol"], p["side"])
                for p in self._state.placements(str(book["id"]))
                if p["as_of"] == orders["as_of"]
            }
            pending = (
                sum(1 for o in state["queued"] if (o["symbol"], o["side"]) not in done)
                if orders["state"] == "CURRENT"
                else 0
            )
            pending_total += pending
            books.append(
                {
                    "id": book["id"],
                    "name": book["name"],
                    "state": orders["state"],
                    "as_of": orders["as_of"],
                    "message": orders["message"],
                    "orders": len(state["queued"]),
                    "dealt_with": len(state["queued"]) - pending
                    if orders["state"] == "CURRENT"
                    else 0,
                    "pending": pending,
                }
            )
        return {"books": books, "pending": pending_total}

    def stop(self, index: MarketIndex, book_id: str) -> dict[str, Any]:
        book = self._state.paper_book(book_id)
        if book is None:
            raise KeyError(book_id)
        self._state.stop_paper_book(book_id, latest_session(index))
        return self.detail(index, book_id)

    # ----------------------------------------------------------------------------- replay

    def _replay(self, index: MarketIndex, book: dict[str, Any]) -> dict[str, Any]:
        built = index.meta().get("built_at", "")
        key = (str(book["id"]), built, book["stopped_session"])
        with self._lock:
            cached = self._cache.get(key)
        if cached is not None:
            return cached
        spec = _spec_from_json(book["spec"], book["stopped_session"])
        state = evaluate_book(index, spec, _broker(book["broker"]))
        state = self._check_record(str(book["id"]), state)
        with self._lock:
            self._cache = {k: v for k, v in self._cache.items() if k[0] != key[0]}
            self._cache[key] = state
        return state

    def _check_record(self, book_id: str, state: dict[str, Any]) -> dict[str, Any]:
        recorded = self._state.paper_snapshots(book_id)
        now = state["session_equity"]
        worst = 0.0
        worst_session = ""
        for session, then in recorded.items():
            if session in now and then > 0:
                drift = abs(now[session] - then) / then
                if drift > worst:
                    worst, worst_session = drift, session
        if worst > REVISION_TOLERANCE:
            state = {
                **state,
                "attention": [
                    *state["attention"],
                    f"The data provider has since re-adjusted past prices (for example after a split), "
                    f"so this book's value on {worst_session} now replays {worst:.1%} away from what "
                    "was recorded that day. The recorded values are kept; the figures below use the "
                    "adjusted prices.",
                ],
                "status": "STOPPED" if state["status"] == "STOPPED" else "ATTENTION",
            }
        self._state.record_paper_snapshots(book_id, now)
        return state


def _broker(raw: dict[str, Any]) -> BrokerCharges:
    return BrokerCharges(
        delivery_per_order=Decimal(str(raw.get("delivery_per_order", "0"))),
        intraday_per_order=Decimal(str(raw.get("intraday_per_order", "20"))),
        fno_per_order=Decimal(str(raw.get("fno_per_order", "20"))),
        dp_charge_per_sell=Decimal(str(raw.get("dp_charge_per_sell", "0"))),
    )


def _spec_json(spec: PaperSpec) -> dict[str, Any]:
    return {
        "template_id": spec.template_id,
        "params": spec.params,
        "scope": spec.scope,
        "symbols": list(spec.symbols),
        "universe": spec.universe,
        "capital": str(spec.capital),
        "slippage_bps": str(spec.slippage_bps),
        "start_session": spec.start_session,
    }


def _spec_from_json(raw: dict[str, Any], stop_session: str | None) -> PaperSpec:
    scope: Literal["stocks", "universe"] = "universe" if raw["scope"] == "universe" else "stocks"
    return PaperSpec(
        template_id=str(raw["template_id"]),
        params=dict(raw["params"]),
        scope=scope,
        symbols=tuple(raw["symbols"]),
        universe=raw["universe"],
        capital=Decimal(str(raw["capital"])),
        slippage_bps=Decimal(str(raw["slippage_bps"])),
        start_session=str(raw["start_session"]),
        stop_session=stop_session,
    )


def _sparkline(curve: list[list[Any]]) -> list[float]:
    values = [float(point[1]) for point in curve]
    if len(values) <= _SPARK_POINTS:
        return values
    step = (len(values) - 1) / (_SPARK_POINTS - 1)
    return [values[round(i * step)] for i in range(_SPARK_POINTS)]


def _summary(book: dict[str, Any], state: dict[str, Any], orders: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": book["id"],
        "name": book["name"],
        "created_at": book["created_at"],
        "status": state["status"],
        "template": state["template"]["name"],
        "scope": state["scope"],
        "start_session": state["start_session"],
        "last_session": state["last_session"],
        "sessions": state["sessions"],
        "capital": state["capital"],
        "equity": state["equity"],
        "return": state["return"],
        "benchmark_return": state["benchmark_return"],
        "excess": state["excess"],
        "queued": len(state["queued"]),
        "orders_state": orders["state"],
        "positions": len(state["positions"]),
        "attention": len(state["attention"]),
        "spark": _sparkline(state["curve"]),
        "error": None,
    }


def _broken(book: dict[str, Any], reason: str, orders: dict[str, Any]) -> dict[str, Any]:
    """A book whose replay is refused (for example its stock left the data) says why, in words."""
    spec = book["spec"]
    return {
        "id": book["id"],
        "name": book["name"],
        "created_at": book["created_at"],
        "status": "ATTENTION",
        "template": spec["template_id"],
        "scope": {"kind": spec["scope"], "symbols": spec["symbols"], "universe": spec["universe"]},
        "start_session": spec["start_session"],
        "last_session": None,
        "sessions": 0,
        "capital": float(spec["capital"]),
        "equity": float(spec["capital"]),
        "return": 0.0,
        "benchmark_return": 0.0,
        "excess": 0.0,
        "queued": 0,
        "orders_state": orders["state"],
        "orders": orders,
        "positions": 0,
        "attention": 1,
        "spark": [],
        "error": reason,
    }
