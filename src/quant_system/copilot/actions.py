"""What the Copilot may *ask* to do, and only ever through the person's approval.

The lookup tools (:mod:`quant_system.copilot.tools`) are all read-only, and a test keeps every one of their names clear of
words such as "save", "remove" and "write". An action is different in kind, so it lives in its own registry and never in
that one. A model cannot run an action: it can only ask. The request is checked here, shown to the person in plain
words, and carried out by the engine only after they press Approve.

This is a short, fixed list of changes that stay inside the app and can be undone. There is no way here to place an
order, touch a broker, a key, a setting or an account, or change what a paper book trades.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from quant_system.copilot.registry import (
    Param,
    Proposal,
    ToolResult,
    ToolSpec,
    UserFacingError,
    check_args,
)

__all__ = [
    "ActionContext",
    "ActionDone",
    "ActionRegistry",
    "ActionSpec",
    "ActionText",
    "default_actions",
]

SYMBOL_RULE = re.compile(r"^[A-Z0-9&-]{1,15}$")
MAX_TEST_SYMBOLS = 5
_TRIAL_NOTE = (
    "This counts as test number {number} you have run. Every test makes the next result harder to trust, because "
    "QuantOS corrects for how many ideas you have tried."
)


@dataclass(frozen=True, slots=True)
class ActionText:
    """What the person reads before they decide: what will happen, and anything they should weigh first."""

    title: str
    detail: str | None = None
    note: str | None = None


@dataclass(frozen=True, slots=True)
class ActionDone:
    """What happened once the person approved: a plain sentence, and perhaps a screen worth opening."""

    text: str
    proposals: tuple[Proposal, ...] = ()


@dataclass(frozen=True, slots=True)
class ActionSpec:
    name: str
    label: str  # a few plain words for the person
    description: str  # for the model: what it does and when to ask for it
    params: tuple[Param, ...]
    describe: Callable[
        [Mapping[str, Any]], ActionText
    ]  # checks the request and words it; changes nothing
    run: Callable[[Mapping[str, Any]], ActionDone]  # called only after the person approves
    limit: int = 5  # the most times one run may ask for this

    def as_checkable(self) -> ToolSpec:
        """The same argument checks the lookup tools use, applied to this action's parameters."""
        return ToolSpec(
            self.name, self.label, self.description, self.params, lambda _args: ToolResult(True, "")
        )


class ActionRegistry:
    def __init__(self, specs: Sequence[ActionSpec]) -> None:
        self._specs = {spec.name: spec for spec in specs}

    def names(self) -> list[str]:
        return list(self._specs)

    def get(self, name: str) -> ActionSpec | None:
        return self._specs.get(name)

    def describe(self) -> str:
        lines = []
        for spec in self._specs.values():
            marks = ", ".join(f"{p.name}: {p.kind} ({p.description})" for p in spec.params)
            lines.append(f"- {spec.name}({marks}): {spec.description}")
        return "\n".join(lines)

    def check(self, name: str, args: Mapping[str, Any]) -> str | None:
        """A plain reason this request cannot be asked for, or ``None`` when it is well formed."""
        spec = self._specs.get(name)
        if spec is None:
            return f"There is no action called {name}."
        return check_args(spec.as_checkable(), args)


@dataclass(slots=True)
class ActionContext:
    symbol_exists: Callable[[str], bool]
    watchlist: Callable[[], list[str]]
    add_to_watchlist: Callable[[str], list[str]]
    remove_from_watchlist: Callable[[str], list[str]]
    # The strategy tests: template id -> name, how many tests have been run so far, and running one.
    test_names: Callable[[], dict[str, str]]
    tests_so_far: Callable[[], int]
    run_test: Callable[[str, list[str]], dict[str, Any]]
    # The screen where a finished test can be read, from its id.
    test_path: Callable[[str], str] = field(default=lambda run_id: f"/lab/runs/{run_id}")


def _symbol(args: Mapping[str, Any]) -> str:
    symbol = str(args["symbol"]).strip().upper()
    if not SYMBOL_RULE.match(symbol):
        raise UserFacingError(
            "That does not look like a stock symbol. Use letters and numbers only."
        )
    return symbol


def _symbols(args: Mapping[str, Any]) -> list[str]:
    raw = [str(s).strip().upper() for s in args["symbols"]]
    seen = list(dict.fromkeys(raw))
    if not seen or len(seen) > MAX_TEST_SYMBOLS:
        raise UserFacingError(f"Pick between one and {MAX_TEST_SYMBOLS} stocks for a test.")
    if any(not SYMBOL_RULE.match(s) for s in seen):
        raise UserFacingError("One of those does not look like a stock symbol.")
    return seen


def _known(ctx: ActionContext, symbol: str) -> str:
    if not ctx.symbol_exists(symbol):
        raise UserFacingError(f"{symbol} is not in the market data, so it cannot be used.")
    return symbol


def _percent(value: Any) -> str:
    return f"{float(value):.1%}"


def _add_watchlist(ctx: ActionContext) -> ActionSpec:
    def describe(args: Mapping[str, Any]) -> ActionText:
        return ActionText(f"Add {_known(ctx, _symbol(args))} to your watchlist")

    def run(args: Mapping[str, Any]) -> ActionDone:
        symbol = _known(ctx, _symbol(args))
        ctx.add_to_watchlist(symbol)
        return ActionDone(
            f"{symbol} is on your watchlist now.",
            (Proposal("navigate", "Open your watchlist", "/"),),
        )

    return ActionSpec(
        "add_to_watchlist",
        "Add a stock to your watchlist",
        "Adds one stock to the person's watchlist. Ask for it when they want to keep an eye on a stock.",
        (Param("symbol", "str", "the stock's symbol, for example TCS"),),
        describe,
        run,
    )


def _remove_watchlist(ctx: ActionContext) -> ActionSpec:
    def describe(args: Mapping[str, Any]) -> ActionText:
        symbol = _symbol(args)
        if symbol not in ctx.watchlist():
            raise UserFacingError(f"{symbol} is not on the watchlist.")
        return ActionText(f"Take {symbol} off your watchlist")

    def run(args: Mapping[str, Any]) -> ActionDone:
        symbol = _symbol(args)
        ctx.remove_from_watchlist(symbol)
        return ActionDone(f"{symbol} is off your watchlist now.")

    return ActionSpec(
        "remove_from_watchlist",
        "Take a stock off your watchlist",
        "Takes one stock off the person's watchlist. Ask for it only when they want it gone.",
        (Param("symbol", "str", "the stock's symbol, for example TCS"),),
        describe,
        run,
    )


def _strategy_test(ctx: ActionContext) -> ActionSpec:
    def chosen(args: Mapping[str, Any]) -> tuple[str, str, list[str]]:
        template = str(args["template_id"]).strip()
        names = ctx.test_names()
        if template not in names:
            raise UserFacingError("That is not one of the ideas QuantOS can test.")
        return template, names[template], _symbols(args)

    def describe(args: Mapping[str, Any]) -> ActionText:
        _template, name, symbols = chosen(args)
        for symbol in symbols:
            _known(ctx, symbol)
        number = ctx.tests_so_far() + 1
        return ActionText(
            f'Test the idea "{name}" on {", ".join(symbols)}',
            "It uses the real prices from the last ten years, with every charge, and is compared with simply holding NIFTY.",
            _TRIAL_NOTE.format(number=number),
        )

    def run(args: Mapping[str, Any]) -> ActionDone:
        template, name, symbols = chosen(args)
        result = ctx.run_test(template, symbols)
        run_id = str(result.get("id") or "")
        verdict = result.get("verdict", {}).get("title", "The test finished.")
        text = (
            f'The test of "{name}" on {", ".join(symbols)} finished. QuantOS\'s verdict: {verdict}. It returned '
            f"{_percent(result['strategy']['total_return'])} against {_percent(result['benchmark']['total_return'])} "
            "for simply holding NIFTY over the same days."
        )
        shown = (
            (Proposal("navigate", "Read the full result", ctx.test_path(run_id)),) if run_id else ()
        )
        return ActionDone(text, shown)

    return ActionSpec(
        "run_strategy_test",
        "Test an idea on real prices",
        "Runs one of QuantOS's ready-made ideas on up to five stocks over real history and reports its verdict. Each "
        "test is counted, so ask for one only when the person wants it, never to search for something that looks good.",
        (
            Param("template_id", "str", "the id of the idea to test"),
            Param("symbols", "list[str]", "one to five stock symbols"),
        ),
        describe,
        run,
        limit=2,
    )


def default_actions(ctx: ActionContext) -> ActionRegistry:
    """The few changes the Copilot may ask for, bound to the app."""
    return ActionRegistry([_add_watchlist(ctx), _remove_watchlist(ctx), _strategy_test(ctx)])
