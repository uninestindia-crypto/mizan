"""Read-only market data index for the retail product (QuantOS 2.0).

The evidence store under ``data/evidence/market-cache`` is the source of truth. This package builds
a derived SQLite index from it for fast screens and charts, records exactly which manifests were
used, and never writes to the evidence store.
"""

from __future__ import annotations

from quant_system.market.index import IndexNotReadyError, MarketIndex, SymbolNotFoundError
from quant_system.market.index_builder import BuildReport, build_market_index
from quant_system.market.sources import DatasetRef, discover_caches

__all__ = [
    "BuildReport",
    "DatasetRef",
    "IndexNotReadyError",
    "MarketIndex",
    "SymbolNotFoundError",
    "build_market_index",
    "discover_caches",
]
