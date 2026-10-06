"""The shape of a Copilot tool: its arguments, its result, and the registry that checks and runs it.

Every tool is read-only. A result carries facts with their provenance, or a plain reason it could not. Text from
outside the app is flagged ``untrusted`` so the agent treats it as data, never as instructions. The agent may
*propose* a screen or a second opinion; those are buttons the person clicks.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from quant_system.copilot.guard import fence

logger = logging.getLogger(__name__)

MAX_LIST = 20
MAX_TEXT = 200


class MarketReader(Protocol):
    def search(self, query: str, limit: int = 20) -> list[dict[str, Any]]: ...
    def resolve(self, symbol: str) -> str: ...
    def symbol_info(self, symbol: str) -> dict[str, Any]: ...
    def stock_stats(self, symbol: str) -> dict[str, Any]: ...
    def bars(self, symbol: str) -> Any: ...


class ShariahSource(Protocol):
    def company(self, symbol: str) -> dict[str, Any] | None: ...
    def company_count(self) -> int: ...


class QuoteSource(Protocol):
    def quotes(self, symbols: Sequence[str]) -> dict[str, Any]: ...


class NewsSource(Protocol):
    def headlines(self, query: str) -> list[dict[str, Any]]: ...


@dataclass(frozen=True, slots=True)
class Proposal:
    """Something the person may click. ``kind`` is ``navigate`` or ``second_opinion``."""

    kind: str
    label: str
    path: str | None = None
    symbol: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "label": self.label, "path": self.path, "symbol": self.symbol}


@dataclass(slots=True)
class ToolResult:
    ok: bool
    summary: str
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    untrusted: bool = False
    proposals: list[Proposal] = field(default_factory=list)

    def for_prompt(self, limit: int = 6000) -> str:
        """The result as text for the model. Untrusted text is fenced so it reads as data."""
        body = json.dumps(self.data if self.ok else {"error": self.error}, default=str)[:limit]
        return f"<untrusted_data>{fence(body)}</untrusted_data>" if self.untrusted else body


def failure(summary: str, message: str) -> ToolResult:
    return ToolResult(False, summary, error=message)


class UserFacingError(Exception):
    """A refusal whose message is already written for the person. A tool passes it through as the reason."""


@dataclass(frozen=True, slots=True)
class Param:
    name: str
    kind: str  # "str", "list[str]", "number"
    description: str
    required: bool = True


@dataclass(slots=True)
class ToolSpec:
    name: str
    label: str  # plain words for the person: shown in the activity trail and the agent editor
    description: str  # for the model
    params: tuple[Param, ...]
    handler: Callable[[Mapping[str, Any]], ToolResult]


@dataclass(slots=True)
class ToolContext:
    index: MarketReader | None = None
    shariah: ShariahSource | None = None
    quotes: QuoteSource | None = None
    news: NewsSource | None = None
    portfolio: Callable[[], dict[str, Any]] | None = None
    watchlist: Callable[[], list[str]] | None = None
    paper_books: Callable[[], list[dict[str, Any]]] | None = None
    trade_costs: Callable[[Mapping[str, Any]], dict[str, Any]] | None = None
    position_size: Callable[[Mapping[str, Any]], dict[str, Any]] | None = None


def _check_value(spec: ToolSpec, param: Param, value: Any) -> str | None:
    if param.kind == "str" and not isinstance(value, str):
        return f"{param.name} must be text."
    if param.kind == "number" and (isinstance(value, bool) or not isinstance(value, (int, float))):
        return f"{param.name} must be a number."
    is_text_list = isinstance(value, list) and all(isinstance(v, str) for v in value)
    if param.kind == "list[str]" and not is_text_list:
        return f"{param.name} must be a list of text."
    return None


def _check_param(spec: ToolSpec, param: Param, args: Mapping[str, Any]) -> str | None:
    if param.name not in args:
        return f"{spec.name} needs the argument {param.name}." if param.required else None
    return _check_value(spec, param, args[param.name])


def check_args(spec: ToolSpec, args: Mapping[str, Any]) -> str | None:
    if not isinstance(args, Mapping):
        return "The arguments must be an object."
    problems = (_check_param(spec, param, args) for param in spec.params)
    return next((problem for problem in problems if problem), None)


def bound(
    ctx: ToolContext,
    name: str,
    label: str,
    description: str,
    params: tuple[Param, ...],
    fn: Callable[[ToolContext, Mapping[str, Any]], ToolResult],
) -> ToolSpec:
    """A tool whose handler is ``fn`` with the context already supplied."""
    return ToolSpec(name, label, description, params, lambda args: fn(ctx, args))


class ToolRegistry:
    def __init__(self, specs: Sequence[ToolSpec]) -> None:
        self._specs = {spec.name: spec for spec in specs}

    def names(self) -> list[str]:
        return list(self._specs)

    def label(self, name: str) -> str:
        spec = self._specs.get(name)
        return spec.label if spec else name

    def catalog(self) -> list[dict[str, str]]:
        """What the interface shows when a person picks tools for an agent: plain labels, no code names."""
        return [
            {"name": s.name, "label": s.label, "description": s.description}
            for s in self._specs.values()
        ]

    def describe(self, allowed: set[str] | None = None) -> str:
        lines = []
        for spec in self._specs.values():
            if allowed is not None and spec.name not in allowed:
                continue
            marks = ", ".join(
                f"{p.name}{'' if p.required else '?'}: {p.kind} ({p.description})"
                for p in spec.params
            )
            lines.append(f"- {spec.name}({marks}): {spec.description}")
        return "\n".join(lines)

    def call(
        self, name: str, args: Mapping[str, Any], allowed: set[str] | None = None
    ) -> ToolResult:
        spec = self._specs.get(name)
        if spec is None or (allowed is not None and name not in allowed):
            return failure(f"{name}: not available", f"There is no tool called {name}.")
        problem = check_args(spec, args)
        if problem:
            return failure(f"{name}: bad arguments", problem)
        try:
            return spec.handler(args)
        except UserFacingError as error:
            return failure(f"{name}: could not run", str(error))
        except Exception:
            logger.exception("Copilot tool %s failed", name)
            return failure(
                f"{name}: failed", "That lookup failed unexpectedly, so no answer is available."
            )
