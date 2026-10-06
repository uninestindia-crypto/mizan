"""Run an assistant's steps one after another and keep what each step found.

With an AI model every step is a small Copilot conversation limited to the tools the assistant may use. With no AI
key each step is answered from the built-in tool answers, so a ready-made assistant still works on a fresh install.
A step that fails stops the run with a plain reason; nothing in here can place an order or change a setting.
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from typing import Any, Protocol

from quant_system.copilot.agent import AgentResult, CopilotAgent, Message, Step
from quant_system.copilot.llm import ChatModel
from quant_system.copilot.registry import Proposal, ToolRegistry
from quant_system.copilot.rules import AnswerContext, answer_without_ai

__all__ = ["RunOptions", "Runnable", "StepRun", "WorkflowResult", "run_workflow"]

MAX_STEPS = 8
SYMBOL_RULE = re.compile(r"^[A-Z0-9&-]{1,15}$")
_ADD_KEY = Proposal("navigate", "Add an AI key", "/settings/accounts")
_NO_AI_NOTE = (
    "No AI key is set up, so each step used only the built-in answers. Add an AI key in Settings, then Accounts "
    "and keys, to let this assistant work through open-ended steps."
)
_NEEDS_AI = (
    "This assistant needs an AI key to work through its steps. Open Settings, then Accounts and keys, add one, "
    "and run it again."
)
_NEEDS_SYMBOL = "Tell me which stock to run this on, for example TCS."
_BAD_SYMBOL = (
    "That does not look like a stock symbol. Use letters and numbers only, for example TCS."
)
_TOO_SLOW = "Stopped early because this was taking too long. What finished is shown above."


class Runnable(Protocol):
    @property
    def name(self) -> str: ...
    @property
    def instructions(self) -> str: ...
    @property
    def tools(self) -> tuple[str, ...]: ...
    @property
    def steps(self) -> tuple[str, ...]: ...
    @property
    def needs_symbol(self) -> bool: ...


@dataclass(frozen=True, slots=True)
class RunOptions:
    symbol: str | None = None
    model: ChatModel | None = None
    page: str | None = None
    needs_ai: bool = False
    deadline_seconds: float = 300.0
    clock: Callable[[], float] = time.monotonic


@dataclass(slots=True)
class StepRun:
    number: int
    text: str
    reply: str
    looked_at: list[Step] = field(default_factory=list)
    error: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "number": self.number,
            "text": self.text,
            "reply": self.reply,
            "looked_at": [
                {"label": s.label, "summary": s.summary, "ok": s.ok} for s in self.looked_at
            ],
            "error": self.error,
        }


@dataclass(slots=True)
class WorkflowResult:
    name: str
    symbol: str | None
    steps: list[StepRun] = field(default_factory=list)
    proposals: list[Proposal] = field(default_factory=list)
    model: str | None = None
    completed: bool = False
    note: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "symbol": self.symbol,
            "steps": [s.as_dict() for s in self.steps],
            "proposals": [p.as_dict() for p in self.proposals],
            "model": self.model,
            "completed": self.completed,
            "note": self.note,
        }


def _fill(text: str, symbol: str | None) -> str:
    return text.replace("{symbol}", symbol) if symbol else text


def _step_answer(
    agent: Runnable, registry: ToolRegistry, history: list[Message], options: RunOptions
) -> AgentResult:
    text = history[-1].content
    if options.model is None:
        allowed = frozenset(agent.tools)
        context = AnswerContext(options.page, False, allowed, hint=False, symbol=options.symbol)
        return answer_without_ai(text, registry, context)
    runner = CopilotAgent(options.model, registry)
    instructions = _fill(agent.instructions, options.symbol) or None
    return runner.run(
        history, page=options.page, instructions=instructions, allowed=set(agent.tools)
    )


def _refusal(agent: Runnable, options: RunOptions) -> WorkflowResult | None:
    """A run that cannot start at all, and the plain reason why."""
    symbol = (options.symbol or "").strip().upper() or None
    result = WorkflowResult(agent.name, symbol)
    if options.needs_ai and options.model is None:
        result.note, result.proposals = _NEEDS_AI, [_ADD_KEY]
        return result
    if agent.needs_symbol and symbol is None:
        result.note = _NEEDS_SYMBOL
        return result
    if symbol is not None and not SYMBOL_RULE.match(symbol):
        result.note = _BAD_SYMBOL
        return result
    return None


def _merge(into: list[Proposal], new: list[Proposal]) -> None:
    into.extend(p for p in new if p not in into)


def run_workflow(
    agent: Runnable, registry: ToolRegistry, options: RunOptions | None = None
) -> WorkflowResult:
    """Run every step in order. Never raises: a failure is a plain note on the result."""
    options = options or RunOptions()
    refused = _refusal(agent, options)
    if refused is not None:
        return refused
    symbol = (options.symbol or "").strip().upper() or None
    options = replace(options, symbol=symbol)
    result = WorkflowResult(agent.name, symbol)
    history: list[Message] = []
    started = options.clock()
    for number, step in enumerate(agent.steps[:MAX_STEPS], start=1):
        if options.clock() - started > options.deadline_seconds:
            result.note = _TOO_SLOW
            return result
        text = _fill(step, symbol)
        history.append(Message("user", text))
        answer = _step_answer(agent, registry, history, options)
        failure = (
            answer.reply if answer.error else None
        )  # the plain sentence, never the internal code
        result.steps.append(StepRun(number, text, answer.reply, answer.steps, failure))
        result.model = answer.model or result.model
        _merge(result.proposals, answer.proposals)
        history.append(Message("assistant", answer.reply))
        if answer.error:
            return result
    result.completed = True
    if options.model is None:
        result.note = _NO_AI_NOTE
        _merge(result.proposals, [_ADD_KEY])
    return result
