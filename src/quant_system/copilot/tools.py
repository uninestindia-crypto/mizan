"""The Copilot's tools, assembled. Every one is read-only; none can place an order or change a setting.

The tools live in focused modules: :mod:`tools_market` (stocks, screens), :mod:`tools_screening` (halal screening,
fundamentals), :mod:`tools_fundamentals` (a company's own filed results), :mod:`tools_user` (the person's data, live
prices, news, evidence). This module builds the registry and re-exports what callers need.
"""

from __future__ import annotations

from quant_system.copilot.registry import (
    Param,
    Proposal,
    ToolContext,
    ToolRegistry,
    ToolResult,
    ToolSpec,
)
from quant_system.copilot.tools_fundamentals import fundamentals_specs
from quant_system.copilot.tools_market import market_specs
from quant_system.copilot.tools_screening import SCREENING_DISCLAIMER, screening_specs
from quant_system.copilot.tools_user import EVIDENCE_STATEMENT, user_specs

__all__ = [
    "EVIDENCE_STATEMENT",
    "SCREENING_DISCLAIMER",
    "Param",
    "Proposal",
    "ToolContext",
    "ToolRegistry",
    "ToolResult",
    "ToolSpec",
    "default_registry",
]


def default_registry(ctx: ToolContext) -> ToolRegistry:
    """The full set of tools, bound to ``ctx``."""
    specs = [*market_specs(ctx), *screening_specs(ctx), *user_specs(ctx), *fundamentals_specs(ctx)]
    return ToolRegistry(specs)
