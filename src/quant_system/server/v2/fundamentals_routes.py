"""HTTP routes for long-term fundamentals: facts from a company's own filings, with proof and dates.

Every route is read-only with respect to money. Nothing here recommends anything: figures are facts with their
filing, and rules of thumb say they are rules of thumb. Reading a company's results from NSE is started by a button
in the app, runs in the background, and is polite (one request at a time, a pause between requests).

Errors use the app's plain error format. This module imports nothing from ``router.py`` at the top of the file, so
the router can include it without a cycle: ``services()`` is fetched inside the functions that need it.
"""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Path, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from pydantic import BaseModel, Field

from quant_system.fundamentals.compare import compare
from quant_system.fundamentals.jobs import BUSY, InvalidSymbol, TooBusy
from quant_system.fundamentals.portfolio_view import portfolio_fundamentals
from quant_system.fundamentals.runtime import Runtime, default_runtime
from quant_system.fundamentals.screen import MAX_LIMIT, SORT_FIELDS, Filters, screen
from quant_system.fundamentals.service import price_book, price_for
from quant_system.fundamentals.snapshot import normalize_symbol
from quant_system.fundamentals.views import company_view
from quant_system.server.security import format_error_response

__all__ = ["router", "runtime"]

SYMBOL = r"^[A-Za-z0-9&-]{1,15}$"
NO_INDEX = "Market data is not connected yet. Open Settings, then Market data."
NO_JOB = "QuantOS has no record of that job. It may have finished a while ago."
COMPARE_COUNT = "Pick two to four stocks to compare, separated by commas, for example TCS,INFY."
BAD_REQUEST = "BAD_REQUEST"
_FIELD_MESSAGES = {
    "symbol": "Use letters and numbers only for the stock symbol, for example TCS.",
    "symbols": COMPARE_COUNT,
    "account": "Pick All accounts or one of your accounts.",
    "sort": "Pick a sort field from the list: " + ", ".join(SORT_FIELDS) + ".",
    "order": "Pick ascending (asc) or descending (desc) order.",
    "limit": f"Show between 1 and {MAX_LIMIT} results.",
    "sector": "Type a few letters of an industry group, for example bank.",
    "body": "That could not be read. Reload the page and try again.",
}
_ANYTHING_ELSE = "Something you entered is not right. Check it and try again."
Handler = Callable[[Request], Coroutine[Any, Any, Response]]


def _sentence(error: RequestValidationError) -> str:
    first = error.errors()[0] if error.errors() else {}
    field = next((p for p in reversed(first.get("loc", ())) if isinstance(p, str)), "")
    return _FIELD_MESSAGES.get(field) or (
        "Check the number you typed for " + field.replace("_", " ") + "."
        if field
        else _ANYTHING_ELSE
    )


def _refused(request: Request, error: RequestValidationError) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    body = format_error_response(BAD_REQUEST, _sentence(error), request_id=request_id)
    return JSONResponse(status_code=422, content=body)


class FundamentalsRoute(APIRoute):
    """A route that answers a request the schema refused with one plain sentence and HTTP 422."""

    def get_route_handler(self) -> Handler:
        original = super().get_route_handler()

        async def handler(request: Request) -> Response:
            try:
                return await original(request)
            except RequestValidationError as error:
                return _refused(request, error)

        return handler


router = APIRouter(tags=["Fundamentals"], route_class=FundamentalsRoute)


def runtime() -> Runtime:
    """The running app's store, service and job runner. Tests replace this with `app.dependency_overrides`."""
    return default_runtime()


Live = Annotated[Runtime, Depends(runtime)]


def _fail(
    status: int, code: str, message: str, details: dict[str, Any] | None = None
) -> JSONResponse:
    return JSONResponse(status_code=status, content=format_error_response(code, message, details))


def _index() -> Any | None:
    """The market index when it is ready, else None. Fundamentals still work without it, minus price figures."""
    from quant_system.server.v2.router import services

    index = services().index
    return index if index.is_ready() else None


# ------------------------------------------------------------------------------------ fetching from NSE


class FetchBody(BaseModel):
    symbol: str = Field(max_length=40)


@router.post("/fundamentals/fetch", status_code=202, response_model=None)
def fetch_company(body: FetchBody, live: Live) -> Any:
    """Read one company's latest quarterly results from NSE, in the background."""
    try:
        return JSONResponse(status_code=202, content={"job_id": live.jobs.start(body.symbol)})
    except InvalidSymbol as error:
        return _fail(422, "INVALID_SYMBOL", error.message)
    except TooBusy:
        return _fail(429, "TOO_BUSY", BUSY)


@router.get("/fundamentals/jobs/{job_id}", response_model=None)
def fetch_job(job_id: str, live: Live) -> Any:
    found = live.jobs.get(job_id)
    return found if found is not None else _fail(404, "NOT_FOUND", NO_JOB)


@router.delete("/fundamentals/jobs/{job_id}", response_model=None)
def cancel_fetch_job(job_id: str, live: Live) -> Any:
    """Stop reading. Filings already read are kept."""
    if not live.jobs.cancel(job_id):
        return _fail(404, "NOT_FOUND", NO_JOB)
    return {"cancelled": True}


# --------------------------------------------------------------------------------------- compare and screen


@router.get("/fundamentals/compare", response_model=None)
def compare_companies(live: Live, symbols: Annotated[str, Query(max_length=120)]) -> Any:
    """Two to four companies side by side, only on a comparable basis."""
    names = [normalize_symbol(part.strip()) for part in symbols.split(",") if part.strip()]
    wanted = list(dict.fromkeys(name for name in names if name))
    if (
        len(wanted) != len([p for p in symbols.split(",") if p.strip()])
        or not 2 <= len(wanted) <= 4
    ):
        return _fail(422, BAD_REQUEST, COMPARE_COUNT)
    index = _index()
    return compare([live.service.analyse(s, price_for(index, s)) for s in wanted])


@router.get("/fundamentals/screen", response_model=None)
def screen_companies(
    live: Live,
    min_profitable_quarters: Annotated[int | None, Query(ge=0, le=8)] = None,
    min_roe_pct: Annotated[Decimal | None, Query(ge=-1000, le=1000)] = None,
    max_debt_to_equity: Annotated[Decimal | None, Query(ge=0, le=1000)] = None,
    min_interest_cover: Annotated[Decimal | None, Query(ge=-1000, le=100000)] = None,
    min_ttm_profit_growth_pct: Annotated[Decimal | None, Query(ge=-100, le=100000)] = None,
    max_pe: Annotated[Decimal | None, Query(gt=0, le=100000)] = None,
    sector: Annotated[str | None, Query(min_length=2, max_length=40)] = None,
    sort: Annotated[str, Query(pattern="^(" + "|".join(SORT_FIELDS) + ")$")] = "symbol",
    order: Annotated[str, Query(pattern="^(asc|desc)$")] = "asc",
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = 25,
) -> Any:
    """The companies that meet the filters you chose. These are filters you chose, not a recommendation."""
    filters = Filters(
        min_profitable_quarters,
        min_roe_pct,
        max_debt_to_equity,
        min_interest_cover,
        min_ttm_profit_growth_pct,
        max_pe,
        sector,
    )
    index = _index()
    prices = price_book(index) if index is not None else (lambda symbol: None)
    answer = screen(live.service.analyse_all(prices), filters, sort, order, limit)
    answer["data_dates"]["snapshot_built_on"] = live.service.store.coverage()["snapshot_built_on"]
    return answer


# ---------------------------------------------------------------------------------------------- portfolio


@router.get("/portfolio/fundamentals", response_model=None)
def portfolio_fundamentals_view(
    live: Live, account: Annotated[str, Query(pattern=r"^(all|\d{1,9})$")] = "all"
) -> Any:
    """Fundamentals for the holdings in view (all accounts, or one), with weights from the portfolio's valuation."""
    from quant_system.server.v2.portfolio import portfolio_summary
    from quant_system.server.v2.portfolio_accounts import positions
    from quant_system.server.v2.router import _broker, _scope, _today, services

    svc = services()
    accounts = svc.state.accounts()
    chosen, name = _scope(accounts, account)
    scope = {"account": "all" if chosen is None else chosen, "name": name}
    mine = [h for h in svc.state.holdings() if chosen is None or h.account_id == chosen]
    if not mine:
        return portfolio_fundamentals([], {}, scope)
    index = _index()
    if index is None:
        return _fail(409, "INDEX_NOT_READY", NO_INDEX)
    summary = portfolio_summary(index, mine, _broker(svc.state.settings()), _today())
    rows = positions(summary["holdings"])
    found = {
        str(p["symbol"]): live.service.analyse(str(p["symbol"]), price_for(index, str(p["symbol"])))
        for p in rows
    }
    return portfolio_fundamentals(rows, found, scope)


# ------------------------------------------------------------------------------------------ one company


@router.get("/fundamentals/{symbol}", response_model=None)
def company(live: Live, symbol: Annotated[str, Path(pattern=SYMBOL)]) -> Any:
    """Facts from one company's own filings: figures, ratios, a scorecard of rules of thumb, and the proof."""
    return company_view(live.service.analyse(symbol, price_for(_index(), symbol.upper())))
