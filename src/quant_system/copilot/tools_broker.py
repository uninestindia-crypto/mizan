"""The Copilot's one tool for the person's broker account. It can only look, and only if the person allowed it."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from quant_system.broker_view import messages
from quant_system.copilot.registry import (
    ToolContext,
    ToolResult,
    ToolSpec,
    ToolText,
    bound,
    failure,
)


def broker_account(ctx: ToolContext, _: Mapping[str, Any]) -> ToolResult:
    if ctx.broker is None:
        return failure("broker account unavailable", messages.NOT_AVAILABLE)
    return ToolResult(True, "broker account summary", ctx.broker())


_TEXT = ToolText(
    "My broker account",
    "Reads what your broker shows: holdings, open positions and cash. It can only look, never trade.",
    "The person's real broker account, view only, as last fetched: totals, holdings, open positions and available "
    "cash, with the time they were fetched. Always say when they were fetched. Nothing can be bought, sold or "
    "changed through QuantOS; never suggest otherwise. If the person has not allowed it, the lookup says so.",
)


def broker_specs(ctx: ToolContext) -> list[ToolSpec]:
    return [bound(ctx, "broker_account", _TEXT, (), broker_account)]
