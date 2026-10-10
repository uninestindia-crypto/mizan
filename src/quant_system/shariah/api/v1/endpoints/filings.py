"""Reading company filings from NSE from inside the app: start, follow, stop, and what is covered."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from quant_system.shariah.api.v1.endpoints.proof import fail
from quant_system.shariah.filings.nse_client import InvalidSymbol
from quant_system.shariah.services.filing_jobs import BUSY, TooBusy
from quant_system.shariah.services.proof_runtime import ProofRuntime, current_runtime

router = APIRouter()

Runtime = Annotated[ProofRuntime, Depends(current_runtime)]
NO_SUCH_JOB = "QuantOS has no record of that filing job. It may have finished a while ago."


class FetchBody(BaseModel):
    symbol: str = Field(max_length=40)


def _started(job_id: str) -> JSONResponse:
    return JSONResponse(status_code=202, content={"job_id": job_id})


@router.post("/filings/fetch", status_code=202, response_model=None)
def fetch_filing(body: FetchBody, runtime: Runtime) -> Any:
    """Read one company's latest results filing from NSE, in the background."""
    try:
        return _started(runtime.jobs.start_one(body.symbol))
    except InvalidSymbol as error:
        return fail(422, "INVALID_SYMBOL", error.message)
    except TooBusy:
        return fail(429, "TOO_BUSY", BUSY)


@router.post("/filings/refresh", status_code=202, response_model=None)
def refresh_filings(runtime: Runtime) -> Any:
    """Read the latest filing of every stock the app follows and every stock already screened, politely."""
    try:
        return _started(runtime.jobs.start_refresh())
    except TooBusy:
        return fail(429, "TOO_BUSY", BUSY)


@router.get("/filings/coverage", response_model=None)
def filings_coverage(runtime: Runtime) -> Any:
    """How many stocks are screened from a filing, how many NSE lists, and how new the figures are."""
    return runtime.service.coverage()


@router.get("/filings/jobs/{job_id}", response_model=None)
def filing_job(job_id: str, runtime: Runtime) -> Any:
    found = runtime.jobs.get(job_id)
    return found if found is not None else fail(404, "NOT_FOUND", NO_SUCH_JOB)


@router.delete("/filings/jobs/{job_id}", response_model=None)
def cancel_filing_job(job_id: str, runtime: Runtime) -> Any:
    """Stop reading filings. Filings already read are kept."""
    if not runtime.jobs.cancel(job_id):
        return fail(404, "NOT_FOUND", NO_SUCH_JOB)
    return {"cancelled": True}
