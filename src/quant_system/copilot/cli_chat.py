"""Ask the signed-in AI app already on this computer (Claude Code, Codex, Gemini CLI) instead of using a saved key.

A person who is signed in to one of these apps can use the Copilot with no key at all. The app is a program that can
act on the computer, so it is run only in a way that stops it doing so:

* its tools are switched off (Claude Code) or limited to reading (Codex), and it runs in an empty folder of its own;
* the question travels on standard input, never on the command line, so no text from the chat can become an option;
* it gets only the few settings it needs to start and none of the keys QuantOS holds;
* an app too old to accept a safety switch is refused with a plain sentence. It is never run again without the switch.

``CliChat.complete`` never raises: whatever goes wrong is a status and a plain sentence, as for ``ProviderChat``.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Final

from quant_system.copilot.llm import MAX_PROMPT_CHARS, ChatReply

__all__ = [
    "CHAT_CLIS",
    "CLI_FAILED",
    "CLI_LABELS",
    "CLI_NOT_FOUND",
    "CLI_NOT_SIGNED_IN",
    "CLI_UNSUPPORTED",
    "MIN_TIMEOUT_SECONDS",
    "CliChat",
    "RunResult",
    "build_command",
    "cli_environment",
    "run_cli",
]

# Statuses of a reply made here. They are never sent or received over the network.
CLI_NOT_FOUND: Final = 491
CLI_NOT_SIGNED_IN: Final = 492
CLI_UNSUPPORTED: Final = 493
CLI_FAILED: Final = 494

# The apps that can answer a chat, in the order the Copilot prefers them.
CHAT_CLIS: Final[tuple[str, ...]] = ("antigravity", "claude", "codex")
CLI_LABELS: Final[dict[str, str]] = {
    "antigravity": "Antigravity (your Google sign-in)",
    "claude": "Claude Code (your Claude sign-in)",
    "codex": "Codex (your ChatGPT sign-in)",
}

MIN_TIMEOUT_SECONDS: Final = (
    120.0  # these apps take a while to start; a web call's wait is too short
)
MAX_REPLY_CHARS: Final = 30_000
_ERROR_CHARS: Final = 300
_READ_LIMIT: Final = 400_000  # of an app's output, before it is parsed

_PREAMBLE = (
    "You are answering a question for a person using QuantOS, an investing app. You are not working on a "
    "coding task: do not use any tool, read any file or run any command. Follow the instructions below and "
    "reply with the answer only."
)
_ANTIGRAVITY_INSTRUCTION = (
    "Answer the instructions given on standard input. Use no tools, read no files, run no commands."
)

_UNSUPPORTED = re.compile(
    r"unknown (option|argument|flag)|unrecogni[sz]ed (option|argument|arguments|flag)|invalid option"
    r"|unexpected argument|no such option|did you mean",
    re.IGNORECASE,
)
_SIGNED_OUT = re.compile(
    r"not logged in|not signed in|log ?in|sign ?in|unauthori[sz]ed|\b401\b|authentication"
    r"|invalid .{0,10}key|credentials",
    re.IGNORECASE,
)

# What the app needs to start on this computer. Nothing else is handed over.
_KEEP = frozenset(
    {
        "USERPROFILE",
        "HOME",
        "APPDATA",
        "LOCALAPPDATA",
        "PROGRAMDATA",
        "PROGRAMFILES",
        "PROGRAMFILES(X86)",
        "SYSTEMROOT",
        "SYSTEMDRIVE",
        "WINDIR",
        "COMSPEC",
        "PATHEXT",
        "TEMP",
        "TMP",
        "TMPDIR",
        "LANG",
        "LC_ALL",
        "USERNAME",
        "HOMEDRIVE",
        "HOMEPATH",
        "XDG_CONFIG_HOME",
        "XDG_DATA_HOME",
        "XDG_CACHE_HOME",
        "XDG_STATE_HOME",
    }
)


@dataclass(frozen=True, slots=True)
class RunResult:
    code: int
    out: str = ""
    err: str = ""
    timed_out: bool = False
    missing: bool = False


Env = Mapping[str, str]
Runner = Callable[[list[str], str, float, Env], RunResult]


def build_command(agent_id: str, executable: str) -> list[str]:
    """The command line for one app, fixed here. Nothing from the chat is ever part of it."""
    if agent_id == "claude":
        return [
            executable,
            "-p",
            "--output-format",
            "json",
            "--tools",
            "",
            "--strict-mcp-config",
            "--max-turns",
            "1",
        ]
    if agent_id == "codex":
        return [executable, "exec", "--sandbox", "read-only", "--skip-git-repo-check", "-"]
    if agent_id == "antigravity":
        return [executable, "-p", _ANTIGRAVITY_INSTRUCTION]
    raise ValueError(f"{agent_id} cannot answer a chat.")


def cli_environment(base: Env, path: str) -> dict[str, str]:
    """Only the settings an app needs to start, with ``path`` as its search path. No key, token or secret."""
    kept = {name: value for name, value in base.items() if name.upper() in _KEEP}
    return {**kept, "PATH": path}


def run_cli(argv: list[str], stdin: str, timeout: float, env: Env) -> RunResult:
    """Run one command without a window, in an empty folder of its own. Never raises."""
    folder = tempfile.mkdtemp(prefix="quantos-ai-")
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    try:
        done = subprocess.run(
            argv,
            input=stdin,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
            cwd=folder,
            env=dict(env),
            creationflags=flags,
        )
    except subprocess.TimeoutExpired:
        return RunResult(1, timed_out=True)
    except FileNotFoundError:
        return RunResult(127, missing=True)
    except OSError as error:
        return RunResult(1, err=type(error).__name__)
    finally:
        shutil.rmtree(folder, ignore_errors=True)
    return RunResult(
        done.returncode, (done.stdout or "")[:_READ_LIMIT], (done.stderr or "")[:_READ_LIMIT]
    )


def _prompt(system: str, user: str) -> str:
    return f"{_PREAMBLE}\n\n[Instructions]\n{system}\n\n[Conversation]\n{user}\n"


def _claude_answer(out: str) -> tuple[str, bool, str | None]:
    """``(text, is_error, model)`` from Claude Code's JSON result. Text that is not that JSON is the answer."""
    try:
        data = json.loads(out)
    except ValueError:
        return out.strip(), False, None
    if not isinstance(data, dict):
        return out.strip(), False, None
    usage = data.get("modelUsage")
    model = next(iter(usage), None) if isinstance(usage, dict) and usage else None
    return str(data.get("result") or "").strip(), bool(data.get("is_error")), model


class CliChat:
    """A chat model that is a signed-in app on this computer. ``provider`` reads ``cli:claude`` and so on."""

    def __init__(
        self,
        agent_id: str,
        executable: str,
        *,
        runner: Runner = run_cli,
        environment: Env | None = None,
    ) -> None:
        build_command(agent_id, executable)  # refuses an app that cannot chat, at construction
        self.agent_id = agent_id
        self.provider = f"cli:{agent_id}"
        self.model: str | None = None
        self._executable = executable
        self._runner = runner
        self._environment = environment

    def complete(
        self, system: str, user: str, *, max_tokens: int = 900, timeout: float = 60.0
    ) -> ChatReply:
        if len(system) + len(user) > MAX_PROMPT_CHARS:
            return ChatReply(None, 413, "The question is too long to send to a model.")
        argv = build_command(self.agent_id, self._executable)
        try:
            run = self._runner(
                argv, _prompt(system, user), max(timeout, MIN_TIMEOUT_SECONDS), self._env()
            )
        except (
            Exception
        ) as error:  # a runner is meant not to raise; if one does, it is still just a failure
            return self._failed(CLI_FAILED, type(error).__name__)
        return self._reply(run)

    # ------------------------------------------------------------------------------------------

    def _env(self) -> Env:
        if self._environment is not None:
            return self._environment
        from quant_system.server.v2 import (
            cli_bridge,
        )  # the search path that finds a freshly installed app

        return cli_environment(os.environ, cli_bridge.search_path())

    def _reply(self, run: RunResult) -> ChatReply:
        if run.missing:
            return self._failed(CLI_NOT_FOUND, "not found")
        if run.timed_out:
            return ChatReply(None, 408, "The AI app did not answer in time.")
        text, is_error, model = self._answer(run.out)
        if run.code != 0 or is_error:
            return self._failed(self._status(f"{text} {run.err}"), text or run.err)
        if not text:
            return ChatReply(None, 502, "The AI app returned no text.")
        self.model = model
        return ChatReply(text[:MAX_REPLY_CHARS], 200, None, None, model)

    def _answer(self, out: str) -> tuple[str, bool, str | None]:
        if self.agent_id == "claude":
            return _claude_answer(out)
        return out.strip(), False, None

    @staticmethod
    def _status(output: str) -> int:
        if _UNSUPPORTED.search(output):
            return CLI_UNSUPPORTED
        return CLI_NOT_SIGNED_IN if _SIGNED_OUT.search(output) else CLI_FAILED

    def _failed(self, status: int, detail: str) -> ChatReply:
        cleaned = " ".join(detail.split())[:_ERROR_CHARS]
        return ChatReply(None, status, f"{self.provider}: {cleaned or 'failed'}")
