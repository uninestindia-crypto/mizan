"""The few changes the Copilot may ask for, bound to this app's own watchlist and strategy tests.

Kept apart from ``copilot_wiring`` (the read-only lookups) on purpose. Nothing here is reached except by an approval the
person gave (see :class:`quant_system.copilot.agent_runs.AgentRuns`).
"""

from __future__ import annotations

from typing import Any

from quant_system.copilot.actions import ActionContext, ActionRegistry, default_actions
from quant_system.copilot.registry import UserFacingError
from quant_system.lab import TEMPLATES, LabRequest
from quant_system.market import SymbolNotFoundError

__all__ = ["action_context", "action_registry"]


def action_context() -> ActionContext:
    # The router imports the Copilot routes, so it is imported here, when a run starts, not when this module loads.
    from quant_system.server.v2 import router

    state = router.services().state

    def symbol_exists(symbol: str) -> bool:
        try:
            router._index().symbol_info(symbol)
        except (SymbolNotFoundError, router.V2Error):
            return False
        return True

    def run_test(template_id: str, symbols: list[str]) -> dict[str, Any]:
        request = LabRequest(
            template_id=template_id,
            scope="stocks",
            symbols=tuple(symbols),
            capital=state.settings().money.capital,
        )
        try:
            return router.run_and_save_lab(request)
        except router.V2Error as error:
            raise UserFacingError(error.message) from error

    return ActionContext(
        symbol_exists=symbol_exists,
        watchlist=state.watchlist,
        add_to_watchlist=state.add_to_watchlist,
        remove_from_watchlist=state.remove_from_watchlist,
        test_names=lambda: {template.id: template.name for template in TEMPLATES},
        tests_so_far=state.lab_run_count,
        run_test=run_test,
    )


def action_registry() -> ActionRegistry:
    return default_actions(action_context())
