"""The Copilot's tools, offered to an AI app over the Model Context Protocol, for one run.

When the person lets an AI app do the work of an agent run (Claude Code), the app does not use its own tools at all. It is
started with every one of them switched off and is given this one set instead: the same read-only lookups the built-in
Copilot uses, and the same few changes it may *ask* for. Everything stays as strict as in the built-in loop:

* a call is accepted only with the run's own random token, which nothing else on the computer is given;
* a lookup is the same checked, read-only lookup, and its text is fenced as outside data when it came from outside;
* a change is only ever asked for: the call waits for the person's answer, and the change is carried out by their
  approval, never by the app;
* the number of calls in one run is capped, and a run that was stopped answers every call with a plain refusal.

It speaks just enough of the protocol (JSON-RPC in a POST) for an app to list the tools and call them.
"""

from __future__ import annotations

import logging
import secrets
from collections.abc import Callable, Mapping
from typing import Any

from quant_system.copilot.actions import ActionRegistry, ActionSpec
from quant_system.copilot.agent import ActionBroker, Step
from quant_system.copilot.finalise import links_in
from quant_system.copilot.registry import Param, Proposal, ToolRegistry

__all__ = ["SERVER_NAME", "AgentTools"]

logger = logging.getLogger(__name__)

SERVER_NAME = "quantos"
PROTOCOL_VERSION = "2025-03-26"
MAX_CALLS = 30
HALAL_TOOL = "shariah_check"
_WHY = Param("why", "str", "one plain sentence telling the person why you ask", required=False)
_SCHEMA_TYPES: dict[str, dict[str, Any]] = {
    "str": {"type": "string"},
    "number": {"type": "number"},
    "list[str]": {"type": "array", "items": {"type": "string"}},
}


def _schema(params: tuple[Param, ...]) -> dict[str, Any]:
    properties = {
        p.name: {**_SCHEMA_TYPES.get(p.kind, {"type": "string"}), "description": p.description}
        for p in params
    }
    return {
        "type": "object",
        "properties": properties,
        "required": [p.name for p in params if p.required],
        "additionalProperties": False,
    }


def _text(text: str, error: bool = False) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": text}], "isError": error}


class AgentTools:
    """The tools of one run. Holds what the run found, so the final answer can be checked against it."""

    def __init__(
        self,
        registry: ToolRegistry,
        actions: ActionRegistry | None,
        broker: ActionBroker | None,
        *,
        allowed: set[str] | None = None,
        token: str | None = None,
        emit: Callable[..., None] | None = None,
        cancelled: Callable[[], bool] | None = None,
        max_calls: int = MAX_CALLS,
    ) -> None:
        self._registry = registry
        self._actions = actions
        self._broker = broker
        self._allowed = allowed
        self.token = token or secrets.token_urlsafe(24)
        self._emit = emit or (lambda *_a, **_k: None)
        self._cancelled = cancelled or (lambda: False)
        self._max_calls = max_calls
        self.calls = 0
        self.steps: list[Step] = []
        self.proposals: list[Proposal] = []
        self.links: set[str] = set()
        self.screened: dict[str, dict[str, Any]] = {}

    # ----------------------------------------------------------------------------------------- what is offered

    def tool_names(self) -> list[str]:
        """Every tool this run offers, by the name an app calls it."""
        return [spec.name for spec in self._registry.specs(self._allowed)] + [
            spec.name for spec in (self._actions.specs() if self._actions and self._broker else [])
        ]

    def listing(self) -> list[dict[str, Any]]:
        tools = [
            {"name": s.name, "description": s.description, "inputSchema": _schema(s.params)}
            for s in self._registry.specs(self._allowed)
        ]
        if self._actions is not None and self._broker is not None:
            for action in self._actions.specs():
                note = " Asking shows the person a card with Approve and Skip, and waits for their answer."
                tools.append(
                    {
                        "name": action.name,
                        "description": action.description + note,
                        "inputSchema": _schema((*action.params, _WHY)),
                    }
                )
        return tools

    # ---------------------------------------------------------------------------------------------- the protocol

    def handle(self, message: Any, bearer: str | None) -> tuple[int, dict[str, Any] | None]:
        """One request in, ``(status, body)`` out. A request without the run's token learns nothing."""
        if not bearer or not secrets.compare_digest(bearer.encode(), self.token.encode()):
            return 401, {"error": "unauthorised"}
        if not isinstance(message, dict):
            return 400, {"error": "unreadable"}
        ident = message.get("id")
        if ident is None:  # a notification: nothing to answer
            return 202, None
        method = message.get("method")
        raw_params = message.get("params")
        params: dict[str, Any] = raw_params if isinstance(raw_params, dict) else {}
        if method == "initialize":
            result: dict[str, Any] = {
                "protocolVersion": params.get("protocolVersion") or PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": SERVER_NAME, "version": "1"},
            }
        elif method == "tools/list":
            result = {"tools": self.listing()}
        elif method == "tools/call":
            result = self._call(str(params.get("name") or ""), params.get("arguments"))
        elif method == "ping":
            result = {}
        else:
            return 200, {
                "jsonrpc": "2.0",
                "id": ident,
                "error": {"code": -32601, "message": "unknown method"},
            }
        return 200, {"jsonrpc": "2.0", "id": ident, "result": result}

    # -------------------------------------------------------------------------------------------------- a call

    def _call(self, name: str, raw_args: Any) -> dict[str, Any]:
        args: dict[str, Any] = dict(raw_args) if isinstance(raw_args, Mapping) else {}
        if self._cancelled():
            return _text(
                "The person stopped this run. Stop now and give your best answer from what you have.",
                True,
            )
        self.calls += 1
        if self.calls > self._max_calls:
            return _text(
                "You have used all the lookups this run allows. Give your answer now.", True
            )
        if any(s.name == name for s in self._registry.specs(self._allowed)):
            return self._lookup(name, args)
        if self._actions is not None and self._broker is not None:
            spec = self._actions.get(name)
            if spec is not None:
                return self._change(spec, args)
        return _text(f"There is no tool called {name}.", True)

    def _lookup(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        result = self._registry.call(name, args, self._allowed)
        label = self._registry.label(name)
        self.steps.append(Step(name, label, result.summary, result.ok))
        self._emit("step", f"{label}: {result.summary}", result.ok)
        if result.ok:
            self.links |= links_in(result.data)
            if name == HALAL_TOOL:
                self.screened[str(result.data.get("symbol"))] = result.data
        self.proposals.extend(p for p in result.proposals if p not in self.proposals)
        return _text(result.for_prompt(), not result.ok)

    def _change(self, spec: ActionSpec, args: dict[str, Any]) -> dict[str, Any]:
        assert self._broker is not None
        why = str(args.pop("why", "") or "")[:300]
        proposed = self._broker.propose(spec.name, args, why)
        if isinstance(proposed, str):
            self.steps.append(
                Step(f"action:{spec.name}", "A change was not asked for", proposed, False)
            )
            return _text(f"That cannot be asked for: {proposed}", True)
        outcome = self._broker.wait(proposed)
        self.steps.append(
            Step(f"action:{spec.name}", proposed.title, outcome.text, outcome.status == "done")
        )
        self.proposals.extend(p for p in outcome.proposals if p not in self.proposals)
        if outcome.status in ("expired", "stopped"):
            self._emit("action_result", outcome.text, False)
        return _text(f"{outcome.status.upper()}: {outcome.text}", outcome.status != "done")
