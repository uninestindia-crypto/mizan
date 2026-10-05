"""HTTP API v2 for the retail frontend (``/api/v2``)."""

from __future__ import annotations

import os
import threading
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import APIRouter, FastAPI, Query, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from quant_system import __version__
from quant_system.alpha.model_catalog import (
    PROVIDERS as AI_PROVIDERS,
)
from quant_system.alpha.model_catalog import (
    ModelCatalogError,
    fetch_models,
    newest_models,
)
from quant_system.lab import (
    COSTS_COVERED_FROM,
    TEMPLATES,
    BrokerCharges,
    LabError,
    LabRequest,
    run_lab,
)
from quant_system.lab.runner import UNIVERSES
from quant_system.market import MarketIndex, SymbolNotFoundError
from quant_system.market.downloader import MarketDownload, baseline_exists
from quant_system.market.index import BENCHMARK_SYMBOL
from quant_system.market.sources import discover_caches, store_fingerprint
from quant_system.server.security import format_error_response
from quant_system.server.v2 import paths
from quant_system.server.v2.aitools import detect_cli_tools
from quant_system.server.v2.auto_update import AutoUpdater
from quant_system.server.v2.cli_bridge import (
    launch_agent_session,
    list_cli_status,
    send_job_input,
    start_agent_job,
)
from quant_system.server.v2.credentials import (
    AI_KEY_NAMES,
    CredentialError,
    CredentialStore,
    scrub_mirrored_value,
    verify_credential_connection,
    with_saved_credentials,
)
from quant_system.server.v2.jobs import IndexJob
from quant_system.server.v2.paper_books import PaperBooks
from quant_system.server.v2.portfolio import paper_books, portfolio_summary
from quant_system.server.v2.schemas import (
    CliCodeRequest,
    CliLaunchRequest,
    CostsRequest,
    CredentialTestRequest,
    DataFolderRequest,
    DownloadRequest,
    FolderPickRequest,
    HoldingRequest,
    LabRunRequest,
    OptionsPayoffRequest,
    PaperBookRequest,
    PositionSizeRequest,
    SecretRequest,
    WatchlistRequest,
)
from quant_system.server.v2.state import AppState, Settings
from quant_system.server.v2.system import FolderPickerError, pick_folder
from quant_system.server.v2.tools import (
    OptionLeg,
    ToolError,
    options_payoff,
    position_size,
    trade_costs,
)
from quant_system.server.v2.updates import UpdateChecker

router = APIRouter(prefix="/api/v2", tags=["QuantOS 2.0"])


class V2Error(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


async def v2_error_handler(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, V2Error)
    return JSONResponse(
        status_code=exc.status,
        content=format_error_response(
            code=exc.code,
            message=exc.message,
            request_id=getattr(request.state, "request_id", None),
        ),
    )


# --------------------------------------------------------------------------- services


@dataclass
class Services:
    state: AppState
    index: MarketIndex
    job: IndexJob
    credentials: CredentialStore
    download: MarketDownload
    paper: PaperBooks
    updates: UpdateChecker
    auto: AutoUpdater


_services: Services | None = None
_services_lock = threading.Lock()
_fingerprint_cache: dict[str, tuple[float, str]] = {}


def _download_snapshot(svc: Services) -> dict[str, Any]:
    """The download's progress, plus whether a quick update is possible (a baseline is on disk)."""
    return {**svc.download.snapshot(), "can_update": baseline_exists(paths.app_root() / "data")}


def _connect_downloaded_data(folder: Path) -> None:
    """After a download: use that folder and build the index, so the person lands on a working app."""
    svc = services()
    svc.state.update_settings({"data_folder": str(folder.resolve())})
    svc.job.start(folder, paths.index_dir())


def services() -> Services:
    global _services
    with _services_lock:
        if _services is None:
            state_dir = paths.state_dir()
            state = AppState(state_dir / "app.sqlite")
            index = MarketIndex(paths.index_dir())
            job = IndexJob()
            download = MarketDownload(on_done=_connect_downloaded_data)
            _services = Services(
                state=state,
                index=index,
                job=job,
                credentials=CredentialStore(),
                download=download,
                paper=PaperBooks(state),
                updates=UpdateChecker(__version__),
                auto=AutoUpdater(
                    state=state,
                    index=index,
                    job=job,
                    download=download,
                    data_dir=lambda: paths.app_root() / "data",
                ),
            )
        return _services


def reset_services() -> None:
    global _services
    with _services_lock:
        if _services is not None:
            _services.auto.stop()
        _services = None
    _fingerprint_cache.clear()


def _index() -> MarketIndex:
    index = services().index
    if not index.is_ready():
        raise V2Error(
            409, "INDEX_NOT_READY", "Market data is not connected yet. Open Settings → Data."
        )
    return index


def _data_folder(settings: Settings) -> Path | None:
    if settings.data_folder and paths.is_data_folder(Path(settings.data_folder)):
        return Path(settings.data_folder)
    return None


def _broker(settings: Settings) -> BrokerCharges:
    b = settings.broker
    return BrokerCharges(
        delivery_per_order=b.delivery_per_order,
        intraday_per_order=b.intraday_per_order,
        fno_per_order=b.fno_per_order,
        dp_charge_per_sell=b.dp_charge_per_sell,
    )


def _store_fingerprint(folder: Path) -> str:
    key = str(folder)
    cached = _fingerprint_cache.get(key)
    if cached and time.monotonic() - cached[0] < 60:
        return cached[1]
    value = store_fingerprint(discover_caches(folder / paths.MARKET_CACHE))
    _fingerprint_cache[key] = (time.monotonic(), value)
    return value


def _folder_candidates(scan: dict[str, Any]) -> list[dict[str, Any]]:
    """Quick known locations plus whatever the background search has found, fullest first."""
    merged = {str(p): n for p, n in paths.data_folder_candidates()}
    for item in scan["found"]:
        merged.setdefault(item["path"], item["datasets"])
    return [
        {"path": path, "datasets": count}
        for path, count in sorted(merged.items(), key=lambda item: -item[1])
    ]


def _today() -> date:
    return datetime.now(UTC).astimezone().date()


# ----------------------------------------------------------------------------- status


@router.get("/status")
def status() -> dict[str, Any]:
    svc = services()
    settings = svc.state.settings()
    folder = _data_folder(settings)
    index_info: dict[str, Any] = {"ready": False}
    if svc.index.is_ready():
        meta = svc.index.meta()
        built_from = meta.get("data_folder")
        matches = folder is not None and built_from == str(folder.resolve())
        stale = (
            folder is not None and matches and meta.get("fingerprint") != _store_fingerprint(folder)
        )
        index_info = {
            "ready": True,
            "latest_session": meta.get("latest_session"),
            "built_at": meta.get("built_at"),
            "symbols": int(meta.get("symbols", "0")),
            "flags": int(meta.get("flags", "0")),
            "data_folder": built_from,
            "matches_folder": matches,
            "stale": stale,
        }
    index_info["job"] = svc.job.snapshot()
    if folder is None:
        paths.data_scan.start()  # nothing connected yet: look for market data without being asked
    scan = paths.data_scan.snapshot()
    return {
        "version": __version__,
        "settings": settings.model_dump(mode="json"),
        "data_folder": {
            "path": settings.data_folder,
            "valid": folder is not None,
            "candidates": _folder_candidates(scan),
            "scan": scan["state"],
        },
        "download": _download_snapshot(svc),
        "index": index_info,
        "credentials_available": svc.credentials.available,
        "costs_covered_from": COSTS_COVERED_FROM.isoformat(),
        "lab_runs": svc.state.lab_run_count(),
    }


# ------------------------------------------------------------------------------- data


@router.post("/data/folder")
def set_data_folder(body: DataFolderRequest) -> dict[str, Any]:
    chosen = Path(body.path.strip().strip('"'))
    folder = paths.resolve_data_folder(chosen)
    if folder is None:
        raise V2Error(
            400,
            "NOT_A_DATA_FOLDER",
            f"No QuantOS market data found in {chosen}. Choose the folder that holds your market "
            "data (it contains evidence\\market-cache).",
        )
    settings = services().state.update_settings({"data_folder": str(folder)})
    return {"data_folder": settings.data_folder}


@router.post("/data/download")
def start_download(body: DownloadRequest | None = None) -> dict[str, Any]:
    """Download (or quickly update) NIFTY 500 daily prices from public sources, then connect them."""
    svc = services()
    started = svc.download.start(paths.app_root() / "data", mode=(body or DownloadRequest()).mode)
    return {"started": started, "download": _download_snapshot(svc)}


@router.get("/data/download")
def download_status() -> dict[str, Any]:
    return _download_snapshot(services())


@router.post("/data/download/cancel")
def cancel_download() -> dict[str, Any]:
    services().download.cancel()
    return _download_snapshot(services())


@router.post("/data/scan")
def scan_for_data() -> dict[str, Any]:
    """Search this PC again for market data (the search runs in the background)."""
    paths.data_scan.start(force=True)
    return paths.data_scan.snapshot()


@router.post("/system/pick-folder")
def pick_a_folder(body: FolderPickRequest) -> dict[str, Any]:
    """Show the standard Windows folder dialog. ``path`` is null when the person cancels."""
    try:
        return {"path": pick_folder(body.title, body.initial)}
    except FolderPickerError as err:
        raise V2Error(503, "FOLDER_DIALOG_UNAVAILABLE", str(err)) from err


@router.post("/data/index/build")
def build_index() -> dict[str, Any]:
    svc = services()
    folder = _data_folder(svc.state.settings())
    if folder is None:
        raise V2Error(400, "NO_DATA_FOLDER", "Choose a QuantOS data folder first.")
    started = svc.job.start(folder, paths.index_dir())
    return {"started": started, "job": svc.job.snapshot()}


@router.get("/data/index")
def index_job() -> dict[str, Any]:
    return services().job.snapshot()


# ----------------------------------------------------------------------------- market


@router.get("/market/overview")
def market_overview() -> dict[str, Any]:
    return _index().overview()


@router.get("/market/screener")
def screener(universe: str = Query("liquid", pattern="^(liquid|nifty500|all)$")) -> dict[str, Any]:
    rows = _index().snapshot(universe)
    latest = max((r["asof"] for r in rows), default=None)
    return {"universe": universe, "latest": latest, "rows": rows}


@router.get("/market/search")
def search(
    q: str = Query("", max_length=40), limit: int = Query(12, ge=1, le=50)
) -> list[dict[str, Any]]:
    return _index().search(q, limit)


@router.get("/market/bars/{symbol}")
def bars(symbol: str, start: str | None = None, end: str | None = None) -> dict[str, Any]:
    try:
        series = _index().bars(symbol, start, end)
    except SymbolNotFoundError as err:
        raise V2Error(
            404, "SYMBOL_NOT_FOUND", f"{symbol.upper()} is not in the market data."
        ) from err
    return {
        "symbol": series.symbol,
        "dates": series.dates,
        "open": series.open.tolist(),
        "high": series.high.tolist(),
        "low": series.low.tolist(),
        "close": series.close.tolist(),
        "volume": series.volume.tolist(),
    }


@router.get("/stocks/{symbol}")
def stock(symbol: str) -> dict[str, Any]:
    index = _index()
    svc = services()
    try:
        info = index.symbol_info(symbol)
    except SymbolNotFoundError as err:
        raise V2Error(
            404, "SYMBOL_NOT_FOUND", f"{symbol.upper()} is not in the market data."
        ) from err
    sym = str(info["symbol"])
    return {
        "info": info,
        "stats": index.stock_stats(sym),
        "actions": index.actions(sym),
        "flags": index.flags(sym),
        "in_watchlist": sym in svc.state.watchlist(),
        "holdings": [h.model_dump(mode="json") for h in svc.state.holdings() if h.symbol == sym],
        "benchmark": BENCHMARK_SYMBOL,
    }


# -------------------------------------------------------------------------------- lab


@router.get("/lab/templates")
def lab_templates() -> dict[str, Any]:
    return {
        "templates": [t.as_dict() for t in TEMPLATES],
        "universes": [{"id": k, "label": v} for k, v in UNIVERSES.items()],
        "costs_covered_from": COSTS_COVERED_FROM.isoformat(),
        "runs_so_far": services().state.lab_run_count(),
    }


@router.post("/lab/runs")
def create_lab_run(body: LabRunRequest) -> dict[str, Any]:
    index = _index()
    svc = services()
    settings = svc.state.settings()
    request = LabRequest(
        template_id=body.template_id,
        params=body.params,
        scope=body.scope,
        symbols=tuple(body.symbols),
        universe=body.universe,
        start=body.start,
        end=body.end,
        capital=body.capital or settings.money.capital,
        slippage_bps=body.slippage_bps,
    )
    try:
        result = run_lab(index, request, _broker(settings), prior_trials=svc.state.lab_run_count())
    except LabError as err:
        raise V2Error(400, "LAB_REFUSED", str(err)) from err
    run_id = svc.state.save_lab_run(result)
    stored = svc.state.lab_run(run_id)
    assert stored is not None
    return stored


@router.get("/lab/runs")
def list_lab_runs() -> list[dict[str, Any]]:
    return services().state.lab_runs()


@router.get("/lab/runs/{run_id}")
def get_lab_run(run_id: str) -> dict[str, Any]:
    result = services().state.lab_run(run_id)
    if result is None:
        raise V2Error(404, "RUN_NOT_FOUND", "That lab run does not exist.")
    return result


# --------------------------------------------------------------------------- settings


@router.get("/settings")
def get_settings() -> dict[str, Any]:
    return services().state.settings().model_dump(mode="json")


@router.put("/settings")
def put_settings(patch: dict[str, Any]) -> dict[str, Any]:
    patch.pop("data_folder", None)  # set only through /data/folder, which validates it
    try:
        return services().state.update_settings(patch).model_dump(mode="json")
    except ValidationError as err:
        first = err.errors()[0]
        field = ".".join(str(part) for part in first.get("loc", ()))
        raise V2Error(422, "INVALID_SETTINGS", f"{field}: {first.get('msg')}") from err


@router.post("/settings/disclaimer")
def accept_disclaimer() -> dict[str, Any]:
    stamp = datetime.now(UTC).isoformat(timespec="seconds")
    return (
        services().state.update_settings({"disclaimer_accepted_at": stamp}).model_dump(mode="json")
    )


# --------------------------------------------------------------------------- watchlist


@router.get("/watchlist")
def get_watchlist() -> list[dict[str, Any]]:
    svc = services()
    symbols = svc.state.watchlist()
    if not symbols:
        return []
    index = _index()
    rows: list[dict[str, Any]] = []
    for symbol in symbols:
        try:
            info = index.symbol_info(symbol)
        except SymbolNotFoundError:
            rows.append({"symbol": symbol, "missing": True})
            continue
        snap = info["snapshot"] or {}
        asof = str(snap.get("asof") or info["last_date"])
        start = (date.fromisoformat(asof) - timedelta(days=100)).isoformat()
        spark = index.bars(symbol, start=start).close.tolist()
        rows.append(
            {
                "symbol": symbol,
                "name": info["name"],
                "spark": spark,
                **{k: snap.get(k) for k in ("asof", "close", "chg_1d", "ret_1m", "ret_1y")},
            }
        )
    return rows


@router.post("/watchlist")
def add_watchlist(body: WatchlistRequest) -> list[str]:
    symbol = body.symbol.strip().upper()
    try:
        _index().symbol_info(symbol)
    except SymbolNotFoundError as err:
        raise V2Error(404, "SYMBOL_NOT_FOUND", f"{symbol} is not in the market data.") from err
    return services().state.add_to_watchlist(symbol)


@router.delete("/watchlist/{symbol}")
def remove_watchlist(symbol: str) -> list[str]:
    return services().state.remove_from_watchlist(symbol)


# --------------------------------------------------------------------------- portfolio


@router.get("/portfolio")
def get_portfolio() -> dict[str, Any]:
    svc = services()
    settings = svc.state.settings()
    holdings = svc.state.holdings()
    if not holdings:
        return {"holdings": [], "totals": None, "warnings": [], "nifty": None}
    return portfolio_summary(_index(), holdings, _broker(settings), _today())


def _validated_holding(body: HoldingRequest) -> str:
    symbol = body.symbol.strip().upper()
    try:
        _index().symbol_info(symbol)
    except SymbolNotFoundError as err:
        raise V2Error(404, "SYMBOL_NOT_FOUND", f"{symbol} is not in the market data.") from err
    if body.buy_date > _today():
        raise V2Error(400, "FUTURE_DATE", "The buy date cannot be in the future.")
    return symbol


@router.post("/portfolio/holdings")
def add_holding(body: HoldingRequest) -> dict[str, Any]:
    symbol = _validated_holding(body)
    holding = services().state.add_holding(
        symbol, body.quantity, body.avg_price, body.buy_date.isoformat(), body.note
    )
    return holding.model_dump(mode="json")


@router.put("/portfolio/holdings/{holding_id}")
def update_holding(holding_id: int, body: HoldingRequest) -> dict[str, Any]:
    _validated_holding(body)
    holding = services().state.update_holding(
        holding_id, body.quantity, body.avg_price, body.buy_date.isoformat(), body.note
    )
    if holding is None:
        raise V2Error(404, "HOLDING_NOT_FOUND", "That holding does not exist.")
    return holding.model_dump(mode="json")


@router.delete("/portfolio/holdings/{holding_id}")
def delete_holding(holding_id: int) -> dict[str, bool]:
    if not services().state.delete_holding(holding_id):
        raise V2Error(404, "HOLDING_NOT_FOUND", "That holding does not exist.")
    return {"deleted": True}


# ------------------------------------------------------------------------------ paper


@router.get("/update")
def update_status(refresh: bool = False) -> dict[str, Any]:
    """Is a newer release available? Never an error: a failed check just says so quietly."""
    return services().updates.check(force=refresh)


@router.get("/paper/updates")
def paper_updates() -> dict[str, Any]:
    """Whether paper books are being kept up to date automatically, and if not, why not."""
    return services().auto.snapshot()


@router.get("/paper/mine")
def my_paper_books() -> list[dict[str, Any]]:
    """The paper books started in this app, each replayed against the latest market data."""
    return services().paper.summaries(_index())


@router.post("/paper/mine")
def start_paper_book(body: PaperBookRequest) -> dict[str, Any]:
    index = _index()
    svc = services()
    broker = svc.state.settings().broker.model_dump(mode="json")
    try:
        return svc.paper.create(
            index,
            name=body.name,
            template_id=body.template_id,
            params=body.params,
            scope=body.scope,
            symbols=body.symbols,
            universe=body.universe,
            capital=body.capital,
            slippage_bps=body.slippage_bps,
            broker=broker,
        )
    except (LabError, ValueError) as err:
        raise V2Error(400, "PAPER_REFUSED", str(err)) from err


@router.get("/paper/mine/{book_id}")
def paper_book_detail(book_id: str) -> dict[str, Any]:
    try:
        return services().paper.detail(_index(), book_id)
    except KeyError as err:
        raise V2Error(404, "PAPER_BOOK_NOT_FOUND", "That paper book does not exist.") from err


@router.post("/paper/mine/{book_id}/stop")
def stop_paper_book(book_id: str) -> dict[str, Any]:
    try:
        return services().paper.stop(_index(), book_id)
    except KeyError as err:
        raise V2Error(404, "PAPER_BOOK_NOT_FOUND", "That paper book does not exist.") from err


@router.get("/paper/books")
def get_paper_books() -> list[dict[str, Any]]:
    svc = services()
    folder = _data_folder(svc.state.settings())
    index = svc.index if svc.index.is_ready() else None
    return paper_books(folder.parent if folder else None, index)


# ------------------------------------------------------------------------------ tools


@router.post("/tools/costs")
def tool_costs(body: CostsRequest) -> dict[str, Any]:
    settings = services().state.settings()
    try:
        return trade_costs(
            body.segment,
            body.buy_price,
            body.sell_price,
            body.quantity,
            body.trade_date or _today(),
            _broker(settings),
        )
    except ToolError as err:
        raise V2Error(400, "TOOL_INPUT", str(err)) from err


@router.post("/tools/position-size")
def tool_position_size(body: PositionSizeRequest) -> dict[str, Any]:
    money = services().state.settings().money
    try:
        return position_size(
            body.capital or money.capital,
            body.risk_pct or money.risk_per_trade_pct,
            body.entry,
            body.stop,
            body.lot_size,
        )
    except ToolError as err:
        raise V2Error(400, "TOOL_INPUT", str(err)) from err


@router.post("/tools/options-payoff")
def tool_options_payoff(body: OptionsPayoffRequest) -> dict[str, Any]:
    legs = [
        OptionLeg(leg.kind, leg.side, leg.strike, leg.premium, leg.lots, leg.lot_size)
        for leg in body.legs
    ]
    try:
        return options_payoff(
            legs, body.spot, body.days_to_expiry, body.volatility_pct / 100, body.rate_pct / 100
        )
    except ToolError as err:
        raise V2Error(400, "TOOL_INPUT", str(err)) from err


# ------------------------------------------------------------------------ credentials


@router.get("/credentials")
def get_credentials() -> dict[str, Any]:
    store = services().credentials
    return {"available": store.available, "secrets": store.status()}


@router.post("/credentials/test")
def test_credential(body: CredentialTestRequest) -> dict[str, Any]:
    return verify_credential_connection(body.provider, with_saved_credentials(body.credentials))


@router.put("/credentials/{name}")
def put_credential(name: str, body: SecretRequest) -> dict[str, Any]:
    store = services().credentials
    try:
        store.set(name, body.value)
    except CredentialError as err:
        raise V2Error(400, "CREDENTIAL_REFUSED", str(err)) from err
    val = body.value.strip()
    os.environ[name] = val
    return {"available": store.available, "secrets": store.status()}


@router.delete("/credentials/{name}")
def delete_credential(name: str) -> dict[str, Any]:
    store = services().credentials
    try:
        previous = store.get(name)
        store.delete(name)
    except CredentialError as err:
        raise V2Error(400, "CREDENTIAL_REFUSED", str(err)) from err
    if name in os.environ:
        os.environ.pop(name, None)
    scrub_mirrored_value(paths.app_root() / ".env", name, previous)
    return {"available": store.available, "secrets": store.status()}


# ---------------------------------------------------------------------------- Agent CLI Bridge


@router.get("/cli/status")
def get_cli_status(refresh: bool = False) -> list[dict[str, Any]]:
    return list_cli_status(force=refresh)


@router.post("/cli/launch")
def post_cli_launch(body: CliLaunchRequest) -> dict[str, Any]:
    try:
        if body.action in ("install", "signin"):
            status = {item["id"]: item for item in list_cli_status()}.get(body.agent_id)
            terminal_signin = (
                body.action == "signin"
                and status is not None
                and status["signin_mode"] == "terminal"
            )
            if not terminal_signin:
                return start_agent_job(body.agent_id, body.action)
        return launch_agent_session(
            agent_id=body.agent_id,
            action=body.action,
            custom_command=body.custom_command,
        )
    except Exception as err:
        raise V2Error(400, "CLI_LAUNCH_FAILED", str(err)) from err


@router.post("/cli/jobs/{agent_id}/input")
def post_cli_job_input(agent_id: str, body: CliCodeRequest) -> dict[str, bool]:
    if not send_job_input(agent_id, body.text):
        raise V2Error(409, "NO_SIGN_IN_WAITING", "There is no sign-in waiting for a code.")
    return {"sent": True}


# ---------------------------------------------------------------------------- AI models


@router.get("/ai/models/{provider}")
def ai_models(provider: str, refresh: bool = False) -> dict[str, Any]:
    """The newest models this provider offers, read live with the saved key (never a fixed list)."""
    name = provider.lower()
    if name not in AI_PROVIDERS:
        raise V2Error(404, "UNKNOWN_PROVIDER", f"{provider} is not an AI provider QuantOS knows.")
    key = os.environ.get(AI_KEY_NAMES.get(name, ""), "").strip() or None
    try:
        models = fetch_models(name, key, refresh=refresh)
    except ModelCatalogError as err:
        raise V2Error(400, "MODELS_UNAVAILABLE", str(err)) from err
    return {
        "provider": name,
        "total": len(models),
        "newest": [m.as_dict() for m in newest_models(name, models)],
    }


# ---------------------------------------------------------------------------- AI tools


@router.get("/ai-tools")
def ai_tools(refresh: bool = False) -> list[dict[str, Any]]:
    return detect_cli_tools(force=refresh)


def register_api(app: FastAPI) -> None:
    app.add_exception_handler(V2Error, v2_error_handler)
    app.include_router(router)
    _run_auto_update_with(app)
    try:
        services().credentials.apply_to_environment()
    except CredentialError:
        pass


def _run_auto_update_with(app: FastAPI) -> None:
    """Start the paper-book updater when the server starts and stop it when the server stops.

    Wraps the app's existing lifespan, so ``server/app.py`` does not change.
    """
    inner = app.router.lifespan_context

    @asynccontextmanager
    async def lifespan(scope: FastAPI) -> AsyncIterator[Any]:
        services().auto.start()
        try:
            async with inner(scope) as state:
                yield state
        finally:
            services().auto.stop()

    app.router.lifespan_context = lifespan
