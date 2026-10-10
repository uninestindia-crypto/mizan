"""The proof behind a stock's Shariah result, and the one-call status a badge or a filter needs."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse

from quant_system.shariah.filings.nse_client import InvalidSymbol
from quant_system.shariah.services.proof_runtime import ProofRuntime, current_runtime
from quant_system.shariah.services.proof_service import TooManySymbols

router = APIRouter()

Runtime = Annotated[ProofRuntime, Depends(current_runtime)]
MAX_QUERY_CHARS = 4000


def fail(status: int, code: str, message: str) -> JSONResponse:
    """The app's plain error answer: a code for the screen and a sentence for the person."""
    # Imported here, not at the top: the server package imports this router, so a top-level import is a cycle.
    from quant_system.server.security import format_error_response

    return JSONResponse(status_code=status, content=format_error_response(code, message))


@router.get(
    "/stocks/{symbol}/proof",
    response_model=None,
    summary="The Proof Behind a Stock's Shariah Result",
)
def stock_proof(symbol: str, runtime: Runtime) -> Any:
    """The verdict, the tests behind it, every figure with the filing it came from, and what it does not cover."""
    try:
        return runtime.service.proof(symbol)
    except InvalidSymbol as error:
        return fail(422, "INVALID_SYMBOL", error.message)


@router.get("/status", response_model=None, summary="Shariah Result for Many Stocks at Once")
def stock_statuses(
    runtime: Runtime,
    symbols: Annotated[
        str, Query(max_length=MAX_QUERY_CHARS, description="Comma-separated symbols")
    ] = "",
) -> Any:
    """One cheap call for badges and filters. A stock QuantOS knows nothing about is "not screened", never a pass."""
    asked = [name for name in symbols.split(",") if name.strip()]
    try:
        return {"statuses": runtime.service.statuses(asked)}
    except TooManySymbols as error:
        return fail(422, "TOO_MANY_SYMBOLS", str(error))
