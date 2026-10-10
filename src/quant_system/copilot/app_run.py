"""One agent run done by an AI app on this computer, from the tools it is given to the answer the person reads.

The app's answer is treated exactly like the built-in Copilot's: it goes through the same checks (advice phrasing removed,
a halal statement kept only when the screener covered the stock, web addresses limited to ones a tool returned), and the
screener's own block is added after it. What the app *did* is only what its tools recorded, never what it says it did.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from collections.abc import Callable, Mapping, Sequence
from pathlib import Path

from quant_system.copilot.actions import ActionRegistry
from quant_system.copilot.agent import (
    REPLY_CHARS,
    STOPPED_LEAD,
    AgentResult,
    Message,
    build_system_prompt,
    conversation_text,
)
from quant_system.copilot.agent_runs import RunHandle
from quant_system.copilot.agent_tools import AgentTools
from quant_system.copilot.ai_prefs import SpeedPreset
from quant_system.copilot.cli_agent import (
    agent_prompt,
    build_agent_command,
    mcp_config,
    run_agent_app,
)
from quant_system.copilot.cli_chat import CLI_NOT_FOUND, CliChat
from quant_system.copilot.finalise import add_halal_blocks, finalise_reply
from quant_system.copilot.messages import explain_failure
from quant_system.copilot.registry import ToolRegistry

__all__ = ["RUN_SECONDS", "run_with_app"]

logger = logging.getLogger(__name__)

# Longest one run may take, waiting for the person included. The run list gives up on a run well after this.
RUN_SECONDS = 1500.0
TOO_SLOW_LEAD = "That took too long, so here is what I found so far:"


def _found(tools: AgentTools, lead: str) -> str:
    found = "\n".join(f"- {s.summary}" for s in tools.steps if s.ok) or "- nothing yet"
    return add_halal_blocks(f"{lead}\n{found}", list(tools.screened.values()))


def _result(ran_text: str, tools: AgentTools, model: str | None) -> AgentResult:
    reply = finalise_reply(
        ran_text[:REPLY_CHARS], screened=list(tools.screened.values()), links=tools.links
    )
    return AgentResult(
        reply,
        tools.steps,
        tools.proposals,
        model,
        halal=next(iter(reversed(tools.screened.values())), None),
    )


def run_with_app(
    *,
    app_id: str,
    executable: str,
    handle: RunHandle,
    attach: Callable[[AgentTools], None],
    base_url: str,
    registry: ToolRegistry,
    actions: ActionRegistry,
    allowed: set[str] | None,
    instructions: str | None,
    shariah_mode: bool,
    history: Sequence[Message],
    page: str | None,
    limits: SpeedPreset,
    model: str | None,
    thinking: str | None,
    environment: Mapping[str, str],
    search_path: str,
    kill: Callable[[subprocess.Popen[str]], None],
) -> AgentResult:
    """Never raises: whatever goes wrong becomes a result with a plain sentence."""
    tools = AgentTools(
        registry,
        actions,
        handle.broker(actions),
        allowed=allowed,
        emit=handle.emit,
        cancelled=handle.cancelled,
        max_calls=max(12, limits.agent_steps * 3),
    )
    attach(tools)
    folder = Path(tempfile.mkdtemp(prefix="quantos-agent-"))
    try:
        config = folder / "tools.json"
        config.write_text(
            mcp_config(f"{base_url}/api/v2/copilot/agent/tools/{handle.run_id}", tools.token),
            encoding="utf-8",
        )
        command = build_agent_command(
            app_id,
            executable,
            config,
            max_turns=limits.agent_steps * 3,
            model=model,
            thinking=thinking,
        )
        system = build_system_prompt(
            registry,
            allowed,
            instructions,
            shariah_mode,
            actions_text=actions.describe(),
            native=True,
        )
        prompt = agent_prompt(system, conversation_text(history), page)
        ran = run_agent_app(
            command,
            prompt,
            folder=folder,
            base_environment=environment,
            search_path=search_path,
            timeout=RUN_SECONDS,
            cancelled=handle.cancelled,
            kill=kill,
        )
    except Exception:  # a run never takes the server down with it
        logger.exception("An AI app run failed")
        return AgentResult(
            explain_failure(500), tools.steps, tools.proposals, error="ai_unavailable"
        )
    finally:
        shutil.rmtree(folder, ignore_errors=True)
    if ran.missing:
        return AgentResult(explain_failure(CLI_NOT_FOUND), error="ai_unavailable")
    if ran.stopped:
        return AgentResult(
            _found(tools, STOPPED_LEAD), tools.steps, tools.proposals, ran.model, "incomplete"
        )
    if ran.timed_out:
        return AgentResult(
            _found(tools, TOO_SLOW_LEAD), tools.steps, tools.proposals, ran.model, "incomplete"
        )
    if ran.code != 0 or ran.is_error or not ran.text:
        status = CliChat._status(f"{ran.text} {ran.stderr}")
        return AgentResult(
            explain_failure(status), tools.steps, tools.proposals, ran.model, error="ai_unavailable"
        )
    return _result(ran.text, tools, ran.model)
