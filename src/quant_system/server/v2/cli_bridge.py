"""Agent CLI Bridge: Detect, check authentication, and 1-click launch AI coding agent CLIs.

Supports Google Antigravity CLI, OpenAI Codex CLI, Anthropic Claude Code CLI, and custom agent CLIs.
Provides 1-click native Windows Terminal / PowerShell session launching pre-navigated to the QuantOS workspace.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger("quantos.cli_bridge")


@dataclass(frozen=True, slots=True)
class AgentCliDef:
    id: str
    name: str
    maker: str
    commands: tuple[str, ...]
    install_cmd: str
    signin_cmd: str
    run_cmd: str
    auth_env_var: str
    auth_file_hints: tuple[str, ...]
    description: str


SUPPORTED_AGENTS: tuple[AgentCliDef, ...] = (
    AgentCliDef(
        id="antigravity",
        name="Antigravity CLI",
        maker="Google DeepMind",
        commands=("agy", "antigravity"),
        install_cmd="npm install -g @google/antigravity",
        signin_cmd="agy auth login",
        run_cmd="agy",
        auth_env_var="GEMINI_API_KEY",
        auth_file_hints=(".gemini", ".antigravity", "antigravity.json"),
        description="Google DeepMind agentic coding assistant with multi-agent orchestration.",
    ),
    AgentCliDef(
        id="codex",
        name="Codex CLI",
        maker="OpenAI",
        commands=("codex",),
        install_cmd="npm install -g @openai/codex",
        signin_cmd="codex login",
        run_cmd="codex",
        auth_env_var="OPENAI_API_KEY",
        auth_file_hints=(".codex", ".openai", "codex.json"),
        description="OpenAI autonomous developer agent for terminal pair programming.",
    ),
    AgentCliDef(
        id="claude",
        name="Claude Code",
        maker="Anthropic",
        commands=("claude",),
        install_cmd="npm install -g @anthropic-ai/claude-code",
        signin_cmd="claude login",
        run_cmd="claude",
        auth_env_var="ANTHROPIC_API_KEY",
        auth_file_hints=(".claude.json", ".claude", "claude_desktop_config.json"),
        description="Anthropic agentic coding CLI tool designed for direct codebase collaboration.",
    ),
    AgentCliDef(
        id="gemini",
        name="Gemini CLI",
        maker="Google",
        commands=("gemini",),
        install_cmd="npm install -g @google/gemini-cli",
        signin_cmd="gemini auth",
        run_cmd="gemini",
        auth_env_var="GEMINI_API_KEY",
        auth_file_hints=(".gemini",),
        description="Command-line interface for Gemini models and developer workflows.",
    ),
)

_CACHE_SECONDS = 30.0
_cache: tuple[float, list[dict[str, Any]]] | None = None
_lock = threading.Lock()


def get_workspace_root() -> Path:
    """Returns the root directory of the QuantOS project/workspace."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent.resolve()
    return Path(__file__).resolve().parents[4]


def _check_auth_status(agent: AgentCliDef) -> tuple[bool, str]:
    """Determines whether the CLI is authenticated via environment variables or local credential files."""
    env_val = os.environ.get(agent.auth_env_var, "").strip()
    if env_val:
        return True, f"Authenticated via {agent.auth_env_var}"

    home = Path.home()
    for hint in agent.auth_file_hints:
        candidate = home / hint
        if candidate.exists():
            return True, f"Credentials detected in ~/{hint}"
        app_data = os.environ.get("APPDATA")
        if app_data and (Path(app_data) / hint).exists():
            return True, f"Credentials detected in APPDATA/{hint}"

    return False, f"Missing {agent.auth_env_var} or session login"


def _inspect_cli(agent: AgentCliDef) -> dict[str, Any]:
    resolved_cmd: str | None = None
    resolved_path: str | None = None

    for cmd in agent.commands:
        found = shutil.which(cmd)
        if found:
            resolved_cmd = cmd
            resolved_path = found
            break

    version: str | None = None
    if resolved_path:
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        try:
            completed = subprocess.run(
                [resolved_path, "--version"],
                capture_output=True,
                text=True,
                timeout=6,
                check=False,
                creationflags=flags,
            )
            output = (completed.stdout or completed.stderr).strip().splitlines()
            if output:
                version = output[0][:80]
        except (OSError, subprocess.TimeoutExpired):
            version = None

    authenticated, auth_detail = _check_auth_status(agent)

    return {
        "id": agent.id,
        "name": agent.name,
        "maker": agent.maker,
        "installed": resolved_path is not None,
        "command": resolved_cmd or agent.commands[0],
        "path": resolved_path,
        "version": version,
        "authenticated": authenticated,
        "auth_detail": auth_detail,
        "auth_env_var": agent.auth_env_var,
        "install_cmd": agent.install_cmd,
        "signin_cmd": agent.signin_cmd,
        "run_cmd": agent.run_cmd,
        "description": agent.description,
    }


def list_cli_status(force: bool = False) -> list[dict[str, Any]]:
    """Lists detection and auth status for all supported coding agent CLIs."""
    global _cache
    with _lock:
        if not force and _cache is not None and time.monotonic() - _cache[0] < _CACHE_SECONDS:
            return _cache[1]
        results = [_inspect_cli(agent) for agent in SUPPORTED_AGENTS]
        _cache = (time.monotonic(), results)
        return results


def find_windows_terminal() -> str | None:
    """Finds Windows Terminal (wt.exe) if installed on Windows 10/11."""
    if sys.platform != "win32":
        return None
    wt_path = shutil.which("wt.exe") or shutil.which("wt")
    if wt_path:
        return wt_path

    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if local_app_data:
        candidate = Path(local_app_data) / "Microsoft" / "WindowsApps" / "wt.exe"
        if candidate.is_file():
            return str(candidate)
    return None


def launch_agent_session(
    agent_id: str,
    action: str = "run",
    custom_command: str | None = None,
    workspace: Path | None = None,
) -> dict[str, Any]:
    """1-Click launches a coding agent CLI session in a dedicated native terminal window.

    - action == 'run': Launches the agent CLI in interactive session mode.
    - action == 'signin': Launches the agent's login / authentication workflow.
    - action == 'custom': Executes custom_command in the workspace context.
    """
    root_dir = workspace or get_workspace_root()
    cwd_str = str(root_dir)

    target_cmd: str
    title: str

    if action == "custom":
        if not custom_command:
            raise ValueError("custom_command must be provided when action is 'custom'")
        target_cmd = custom_command
        title = f"Agent CLI - {custom_command[:25]}"
    else:
        agent_dict = {a.id: a for a in SUPPORTED_AGENTS}
        if agent_id not in agent_dict:
            raise ValueError(f"Unknown agent CLI: {agent_id}")
        agent = agent_dict[agent_id]
        title = f"QuantOS Agent Bridge - {agent.name}"

        if action == "signin":
            target_cmd = agent.signin_cmd
        elif action == "install":
            target_cmd = agent.install_cmd
        else:
            target_cmd = agent.run_cmd

    logger.info("Launching agent session [%s]: %s (cwd=%s)", action, target_cmd, cwd_str)

    if sys.platform == "win32":
        wt_exe = find_windows_terminal()
        if wt_exe:
            # Launch in modern Windows Terminal tab/window
            cmd_args = [
                wt_exe,
                "-d",
                cwd_str,
                "--title",
                title,
                "powershell.exe",
                "-NoExit",
                "-Command",
                f"Write-Host '=== {title} ===' -ForegroundColor Cyan; {target_cmd}",
            ]
        else:
            # Launch in standard PowerShell window
            cmd_args = [
                "cmd.exe",
                "/c",
                "start",
                title,
                "powershell.exe",
                "-NoExit",
                "-Command",
                f"Set-Location '{cwd_str}'; Write-Host '=== {title} ===' -ForegroundColor Cyan; {target_cmd}",
            ]

        try:
            subprocess.Popen(
                cmd_args,
                cwd=cwd_str,
                env=os.environ.copy(),
                shell=False,
            )
            return {
                "success": True,
                "action": action,
                "command": target_cmd,
                "cwd": cwd_str,
                "launcher": "windows_terminal" if wt_exe else "powershell",
                "message": f"Launched {title} in dedicated terminal window.",
            }
        except Exception as err:
            logger.error("Failed to launch terminal process: %s", err)
            raise RuntimeError(f"Failed to launch terminal process: {err}") from err
    else:
        # Non-Windows fallback (Linux/macOS terminal launchers)
        for term in ("gnome-terminal", "xterm", "kitty", "alacritty"):
            if shutil.which(term):
                subprocess.Popen([term, "--", "bash", "-c", f"cd '{cwd_str}' && {target_cmd}; exec bash"])
                return {"success": True, "command": target_cmd, "launcher": term}

        raise RuntimeError("No compatible terminal emulator detected on host.")
