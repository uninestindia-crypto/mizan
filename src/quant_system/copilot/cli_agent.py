"""Let an AI app on this computer do the work of an agent run, with no tool of its own.

The app is started in a way that leaves it exactly one thing to use: the Copilot's tools, served by this app for this one
run (:mod:`quant_system.copilot.agent_tools`). Everything else it could normally do is switched off, and that was
checked on the real app, not assumed: started this way, Claude Code lists only the tools it was given.

* every built-in tool is off (no file, shell or web tools), and only this run's tools are allowed;
* it runs in an empty folder of its own, with only the few settings it needs to start and none of the keys QuantOS holds;
* the person's own settings, hooks and tool permissions are left out, and it keeps no record of the session;
* the run's token travels in a file in that folder, not on the command line, and the folder is deleted when it ends;
* it can be stopped at any moment, and everything it started stops with it.

Only apps that have been shown to stay inside this are listed in :data:`AGENT_APPS`. An app that cannot be confined stays
a chat-only app: it is never given the tools and never run with a looser command.
"""

from __future__ import annotations

import json
import queue
import subprocess
import threading
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from quant_system.copilot.ai_prefs import clean_model, clean_thinking
from quant_system.copilot.cli_chat import cli_environment

__all__ = [
    "AGENT_APPS",
    "AgentRunResult",
    "agent_prompt",
    "build_agent_command",
    "mcp_config",
    "run_agent_app",
]

# The apps shown to stay inside the tools they are given. Claude Code was checked; the others were not and stay chat-only.
AGENT_APPS: Final[tuple[str, ...]] = ("claude",)
SERVER = "quantos"
_EFFORT_LEVELS: Final[tuple[str, ...]] = ("low", "medium", "high", "xhigh", "max")
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_READ_LIMIT = 400_000


def mcp_config(url: str, token: str) -> str:
    """The file that tells the app where this run's tools are and how to prove it is the run's own app."""
    return json.dumps(
        {
            "mcpServers": {
                SERVER: {
                    "type": "http",
                    "url": url,
                    "headers": {"Authorization": f"Bearer {token}"},
                }
            }
        }
    )


def build_agent_command(
    agent_id: str,
    executable: str,
    config_path: str | Path,
    *,
    max_turns: int,
    model: str | None = None,
    thinking: str | None = None,
) -> list[str]:
    """The command line for an agent run. Nothing from the chat is part of it, and no safety switch is optional."""
    if agent_id not in AGENT_APPS:
        raise ValueError(f"{agent_id} cannot do the work of an agent run.")
    chosen, level = clean_model(model), clean_thinking(thinking)
    command = [
        executable,
        "-p",
        "--output-format",
        "stream-json",
        "--verbose",
        "--mcp-config",
        str(config_path),
        "--strict-mcp-config",
        "--tools",
        "",
        "--allowedTools",
        f"mcp__{SERVER}",
        "--permission-mode",
        "dontAsk",
        "--setting-sources",
        "project",
        "--no-session-persistence",
        "--max-turns",
        str(max(2, int(max_turns))),
    ]
    if chosen:
        command += ["--model", chosen]
    if level in _EFFORT_LEVELS:
        command += ["--effort", str(level)]
    return command


_PREAMBLE = (
    "You are doing a task for a person using QuantOS, an investing app. You have no files, no commands and no internet: "
    "the only things you can use are the tools from the quantos tools server. Do not try anything else. Follow the "
    "instructions below."
)


def agent_prompt(system: str, conversation: str, page: str | None) -> str:
    """Everything the app is told, on standard input (never on the command line)."""
    where = f"\n\nThe person is currently looking at this screen: {page}" if page else ""
    return f"{_PREAMBLE}\n\n[Instructions]\n{system}\n\n[Conversation]\n{conversation}{where}\n"


@dataclass(frozen=True, slots=True)
class AgentRunResult:
    code: int
    text: str = ""
    is_error: bool = False
    model: str | None = None
    stderr: str = ""
    stopped: bool = False
    timed_out: bool = False
    missing: bool = False


def _answer(event: Mapping[str, object]) -> tuple[str, bool, str | None]:
    usage = event.get("modelUsage")
    model = next(iter(usage), None) if isinstance(usage, dict) and usage else None
    return str(event.get("result") or "").strip(), bool(event.get("is_error")), model


def run_agent_app(
    command: Sequence[str],
    prompt: str,
    *,
    folder: Path,
    base_environment: Mapping[str, str],
    search_path: str,
    timeout: float,
    cancelled: Callable[[], bool],
    kill: Callable[[subprocess.Popen[str]], None],
    on_line: Callable[[Mapping[str, object]], None] | None = None,
) -> AgentRunResult:
    """Runs the app until it finishes, is stopped or runs out of time. Never raises."""
    try:
        process = subprocess.Popen(
            list(command),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            cwd=str(folder),
            env=cli_environment(base_environment, search_path),
            creationflags=_NO_WINDOW,
        )
    except FileNotFoundError:
        return AgentRunResult(127, missing=True)
    except OSError as error:
        return AgentRunResult(1, stderr=type(error).__name__)
    lines: queue.Queue[str | None] = queue.Queue()
    errors: list[str] = []

    def read_out() -> None:
        assert process.stdout is not None
        for line in process.stdout:
            lines.put(line)
        lines.put(None)

    def read_err() -> None:
        assert process.stderr is not None
        errors.append(process.stderr.read(_READ_LIMIT))

    threading.Thread(target=read_out, daemon=True).start()
    threading.Thread(target=read_err, daemon=True).start()
    try:
        assert process.stdin is not None
        process.stdin.write(prompt)
        process.stdin.close()
    except OSError:
        pass  # the app is already gone; its output below says why

    answer, failed, model = "", False, None
    deadline = time.monotonic() + timeout
    stopped = timed_out = False
    while True:
        if cancelled():
            stopped = True
            break
        if time.monotonic() > deadline:
            timed_out = True
            break
        try:
            line = lines.get(timeout=0.2)
        except queue.Empty:
            continue
        if line is None:
            break
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if not isinstance(event, dict):
            continue
        if on_line is not None:
            on_line(event)
        if event.get("type") == "result":
            answer, failed, model = _answer(event)
    if stopped or timed_out:
        kill(process)
    try:
        code = process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        kill(process)
        code = 1
    return AgentRunResult(
        code,
        answer,
        failed,
        model,
        (errors[0] if errors else "")[:_READ_LIMIT],
        stopped=stopped,
        timed_out=timed_out,
    )
