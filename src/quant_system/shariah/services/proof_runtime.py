"""The one proof service and filing-job runner the Shariah screens share, and a way for tests to swap them.

The default is built by the app's own wiring (`quant_system.server.v2.shariah_wiring`), which knows where this
computer keeps its files and which market data is loaded. It is imported only when first needed, so the Shariah
package does not pull the whole app in just by being imported.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from quant_system.shariah.services.filing_jobs import FilingJobs
from quant_system.shariah.services.proof_service import ProofService

__all__ = ["ProofRuntime", "current_runtime", "filing_proof", "use_runtime"]

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ProofRuntime:
    service: ProofService
    jobs: FilingJobs


_override: ProofRuntime | None = None


def use_runtime(runtime: ProofRuntime | None) -> None:
    """Use this runtime instead of the app's own, or go back to the app's own with None. For tests."""
    global _override
    _override = runtime


def current_runtime() -> ProofRuntime:
    if _override is not None:
        return _override
    from quant_system.server.v2.shariah_wiring import proof_runtime

    return proof_runtime()


def filing_proof(symbol: str) -> dict[str, Any] | None:
    """The proof for a stock when it rests on a company filing, else None. Never raises.

    The older screener screens call this to prefer the filing's verdict. If anything about the proof cannot be had,
    they carry on with the sample, exactly as before.
    """
    try:
        return current_runtime().service.filing_proof(symbol)
    except Exception:  # the older screens must keep working whatever happens here
        logger.warning("the filing proof for %s could not be had", symbol, exc_info=True)
        return None
