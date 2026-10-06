"""HTTP routes for the Copilot, second opinions and saved agents.

The JSON shapes are fixed in agent_context/decisions/20261006-copilot-api-contract.md.

Every route is read-only with respect to money: nothing here places an order. A normal outcome, including "no AI key"
and a provider that is down, is HTTP 200 with a plain-language reply; only a malformed request is an error.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, StringConstraints

from quant_system.copilot.agent import AgentResult, CopilotAgent, Message
from quant_system.copilot.agent_store import AgentDraft, AgentRejectedError, AgentStore, SavedAgent
from quant_system.copilot.factpack import build_fact_pack
from quant_system.copilot.providers import build_models, default_model, provider_status
from quant_system.copilot.recipes import RECIPES, Recipe, recipe
from quant_system.copilot.registry import ToolRegistry
from quant_system.copilot.rules import AnswerContext, answer_without_ai
from quant_system.copilot.tools import default_registry
from quant_system.copilot.verify import VerifyOptions, verify_stock
from quant_system.copilot.verify_jobs import TooBusyError, VerifyJobs
from quant_system.copilot.workflow import RunOptions, run_workflow
from quant_system.server.security import format_error_response
from quant_system.server.v2 import copilot_wiring

router = APIRouter(prefix="/copilot", tags=["Copilot"])
__all__ = ["router"]

SYMBOL = r"^[A-Za-z0-9&-]{1,15}$"
_jobs = VerifyJobs()
_store: AgentStore | None = None
_NO_AI_KEY = "Add at least one AI key first. Open Settings, then Accounts and keys."
_BUSY = "Several second opinions are already running. Wait for one to finish, then try again."
_AI_FAILED = "\n\nMeanwhile, here is what QuantOS can tell you without the AI:\n\n"


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=4000)


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1, max_length=40)
    page: str | None = Field(default=None, max_length=200)
    agent_id: str | None = Field(default=None, max_length=40)


class VerifyRequest(BaseModel):
    symbol: str = Field(pattern=SYMBOL)
    providers: list[str] = Field(min_length=1, max_length=6)
    pick_note: str | None = Field(default=None, max_length=300)
    recheck: bool = True


class AgentBody(BaseModel):
    name: str = Field(max_length=200)
    description: str = Field(default="", max_length=2000)
    instructions: str = Field(default="", max_length=20000)
    tools: list[str] = Field(default_factory=list, max_length=40)
    steps: list[Annotated[str, StringConstraints(max_length=5000)]] = Field(
        default_factory=list, max_length=40
    )

    def draft(self) -> AgentDraft:
        return AgentDraft(
            self.name, self.description, self.instructions, tuple(self.tools), tuple(self.steps)
        )


class RunBody(BaseModel):
    symbol: str | None = Field(default=None, max_length=15)


# ------------------------------------------------------------------------------------- helpers


def _lookup(provider: str) -> str | None:
    return copilot_wiring.key_lookup(provider)


def store() -> AgentStore:
    global _store
    if _store is None:
        from quant_system.server.v2 import paths

        _store = AgentStore(paths.state_dir() / "copilot.sqlite")
    return _store


def _registry() -> ToolRegistry:
    return default_registry(copilot_wiring.tool_context())


def _fail(
    status: int, code: str, message: str, details: dict[str, Any] | None = None
) -> JSONResponse:
    return JSONResponse(status_code=status, content=format_error_response(code, message, details))


def _spec(agent_id: str) -> SavedAgent | Recipe | None:
    return recipe(agent_id) or store().get(agent_id)


def _reply(result: AgentResult, mode: str, provider: str | None) -> dict[str, Any]:
    return {
        "reply": result.reply,
        "steps": [{"label": s.label, "summary": s.summary, "ok": s.ok} for s in result.steps],
        "proposals": [p.as_dict() for p in result.proposals],
        "mode": mode,
        "provider": provider,
        "model": result.model,
        "error": result.error,
    }


# ------------------------------------------------------------------------------------- status and chat


@router.get("/status")
def status() -> dict[str, Any]:
    providers = provider_status(_lookup)
    live: dict[str, Any] = {
        "ready": False,
        "message": "Add an Upstox key in Settings, then Accounts and keys.",
    }
    return {
        "ai_ready": any(p["ready"] for p in providers),
        "providers": providers,
        "live_prices": live,
    }


@router.get("/models")
def models() -> dict[str, Any]:
    return {"models": provider_status(_lookup)}


def _chat_scope(agent_id: str | None) -> tuple[frozenset[str] | None, str | None]:
    spec = _spec(agent_id) if agent_id else None
    return (frozenset(spec.tools), spec.instructions or None) if spec else (None, None)


@router.post("/chat")
def chat(body: ChatRequest) -> dict[str, Any]:
    registry = _registry()
    allowed, instructions = _chat_scope(body.agent_id)
    model = default_model(_lookup)
    if model is not None:
        history = [Message(m.role, m.content) for m in body.messages]
        agent = CopilotAgent(model, registry)
        result = agent.run(
            history,
            page=body.page,
            instructions=instructions,
            allowed=set(allowed) if allowed else None,
        )
        if not result.error:
            return _reply(result, "ai", model.provider)
        fallback = answer_without_ai(
            body.messages[-1].content, registry, AnswerContext(body.page, True, allowed, False)
        )
        result.reply = result.reply + _AI_FAILED + fallback.reply
        result.steps, result.proposals = fallback.steps, fallback.proposals
        return _reply(result, "built_in", None)
    answer = answer_without_ai(
        body.messages[-1].content, registry, AnswerContext(body.page, False, allowed)
    )
    return _reply(answer, "built_in", None)


# ------------------------------------------------------------------------------------- second opinion


@router.post("/verify", status_code=202, response_model=None)
def start_verify(body: VerifyRequest) -> Any:
    chosen = build_models(_lookup, body.providers)
    if not chosen:
        return _fail(422, "NO_AI_KEY", _NO_AI_KEY)
    registry = _registry()
    options = VerifyOptions(pick_context=body.pick_note, recheck=body.recheck)
    symbol = body.symbol.upper()
    arms = 1 + bool(body.pick_note) + body.recheck

    def work(on_opinion: Any) -> Any:
        return verify_stock(chosen, build_fact_pack(registry, symbol), options, on_opinion)

    try:
        return {"job_id": _jobs.start(work, len(chosen) * arms)}
    except TooBusyError:
        return _fail(429, "TOO_BUSY", _BUSY)


@router.get("/verify/{job_id}", response_model=None)
def verify_progress(job_id: str) -> Any:
    found = _jobs.get(job_id)
    if found is None:
        return _fail(
            404, "NOT_FOUND", "That second opinion is no longer available. Start it again."
        )
    return found


# ------------------------------------------------------------------------------------- agents


@router.get("/tools")
def tools() -> dict[str, Any]:
    return {"tools": _registry().catalog()}


@router.get("/agents")
def agents() -> dict[str, Any]:
    return {
        "agents": [a.as_dict() for a in store().agents()],
        "recipes": [r.as_dict() for r in RECIPES],
    }


def _rejected(error: AgentRejectedError) -> JSONResponse:
    problems = [p.as_dict() for p in error.problems]
    return _fail(422, "AGENT_INVALID", "Check the highlighted fields.", {"problems": problems})


@router.post("/agents", status_code=201, response_model=None)
def create_agent(body: AgentBody) -> Any:
    try:
        return store().create(body.draft(), _registry().names()).as_dict()
    except AgentRejectedError as error:
        return _rejected(error)


@router.put("/agents/{agent_id}", response_model=None)
def update_agent(agent_id: str, body: AgentBody) -> Any:
    try:
        saved = store().update(agent_id, body.draft(), _registry().names())
    except AgentRejectedError as error:
        return _rejected(error)
    return saved.as_dict() if saved else _fail(404, "NOT_FOUND", "That agent no longer exists.")


@router.delete("/agents/{agent_id}", response_model=None)
def delete_agent(agent_id: str) -> Any:
    if not store().delete(agent_id):
        return _fail(404, "NOT_FOUND", "That agent no longer exists.")
    return {"deleted": True}


@router.post("/agents/{agent_id}/run", response_model=None)
def run_agent(agent_id: str, body: RunBody) -> Any:
    spec = _spec(agent_id)
    if spec is None:
        return _fail(404, "NOT_FOUND", "That agent no longer exists.")
    options = RunOptions(
        symbol=body.symbol,
        model=default_model(_lookup),
        needs_ai=bool(getattr(spec, "needs_ai", False)),
    )
    return run_workflow(spec, _registry(), options).as_dict()
