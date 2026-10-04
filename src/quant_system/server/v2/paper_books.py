"""Paper books for the retail app: create, follow, stop. Never place an order anywhere.

A book's state is replayed from its saved specification each time the market data changes (see
:mod:`quant_system.lab.paper`); this module only stores specifications, caches the replay per data
build, and keeps the equity recorded for every session so a provider re-adjustment cannot quietly
rewrite a book's past.
"""

from __future__ import annotations

import threading
from decimal import Decimal
from typing import Any, Literal

from quant_system.lab import BrokerCharges, LabError
from quant_system.lab.paper import PaperSpec, evaluate_book, latest_session
from quant_system.lab.runner import MAX_STOCKS
from quant_system.lab.templates import get_template
from quant_system.market import MarketIndex
from quant_system.server.v2.state import AppState

MAX_BOOKS = 20
# A recorded session whose replayed equity now differs by more than this was changed by a data
# re-adjustment, not by anything the book did.
REVISION_TOLERANCE = 0.01
_SPARK_POINTS = 60


class PaperBooks:
    def __init__(self, state: AppState) -> None:
        self._state = state
        self._lock = threading.Lock()
        self._cache: dict[tuple[str, str, str | None], dict[str, Any]] = {}

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
                out.append(_broken(book, str(err)))
                continue
            out.append(_summary(book, state))
        return out

    def detail(self, index: MarketIndex, book_id: str) -> dict[str, Any]:
        book = self._state.paper_book(book_id)
        if book is None:
            raise KeyError(book_id)
        try:
            state = self._replay(index, book)
        except LabError as err:
            broken = _broken(book, str(err))
            name = get_template(str(book["spec"]["template_id"])).name
            return {
                **broken,
                "template": {"id": book["spec"]["template_id"], "name": name, "summary": ""},
            }
        full = {k: v for k, v in state.items() if k != "session_equity"}
        return {"id": book["id"], "name": book["name"], "created_at": book["created_at"], **full}

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


def _summary(book: dict[str, Any], state: dict[str, Any]) -> dict[str, Any]:
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
        "positions": len(state["positions"]),
        "attention": len(state["attention"]),
        "spark": _sparkline(state["curve"]),
        "error": None,
    }


def _broken(book: dict[str, Any], reason: str) -> dict[str, Any]:
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
        "positions": 0,
        "attention": 1,
        "spark": [],
        "error": reason,
    }
