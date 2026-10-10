"""Agent CLI Bridge: install and sign in to coding-agent CLIs with one click, no terminal.

Install and sign-in run as hidden background jobs. The vendors' own sign-in commands open the
user's default browser themselves (``codex login``, ``claude auth login``, Antigravity on first
use), so the person sees only their browser, then the app flips to "Connected". A terminal window is
used only for working *with* an agent (``Launch``).

Commands come from each vendor's documentation:

* Antigravity: Installed with ``irm https://antigravity.google/cli/install.ps1 | iex``
  into ``%LOCALAPPDATA%\\agy\\bin``; it signs in on first use with your Google account.
* Claude Code: ``claude auth login`` / ``claude auth status`` (exit code 0 when signed in).
* Codex: ``codex login`` / ``codex login status`` (exit code 0 when signed in).
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

logger = logging.getLogger("quantos.cli_bridge")

_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
_URL = re.compile(r"https?://[^\s\"'<>]+")

StepKind = Literal["powershell", "npm", "winget"]
SigninMode = Literal["browser", "terminal"]


@dataclass(frozen=True, slots=True)
class InstallStep:
    label: str
    kind: StepKind
    argument: str  # PowerShell snippet, npm package name, or winget package id

    def display(self) -> str:
        if self.kind == "npm":
            return f"npm install -g {self.argument}"
        if self.kind == "winget":
            return f"winget install {self.argument}"
        return self.argument


@dataclass(frozen=True, slots=True)
class AgentCliDef:
    id: str
    name: str
    maker: str
    commands: tuple[str, ...]
    extra_dirs: tuple[str, ...]
    install: tuple[InstallStep, ...]
    signin_mode: SigninMode
    signin_args: tuple[str, ...]  # run (hidden) for browser mode; run in a terminal otherwise
    status_args: tuple[str, ...] | None  # exit code 0 means signed in
    run_cmd: str
    auth_env_var: str
    auth_file_hints: tuple[str, ...]
    description: str
    docs_url: str
    # Claude's fallback sign-in page shows a code that must be typed back into the CLI.
    accepts_code: bool = False
    update: tuple[InstallStep, ...] = ()


_NODE_STEP = InstallStep(
    "Installing Node.js (needed by this tool)",
    "winget",
    "OpenJS.NodeJS.LTS",
)

SUPPORTED_AGENTS: tuple[AgentCliDef, ...] = (
    AgentCliDef(
        id="antigravity",
        name="Antigravity",
        maker="Google",
        commands=("agy", "antigravity"),
        extra_dirs=(r"%LOCALAPPDATA%\agy\bin",),
        install=(
            InstallStep(
                "Downloading the official Antigravity installer",
                "powershell",
                "irm https://antigravity.google/cli/install.ps1 | iex",
            ),
        ),
        update=(
            InstallStep(
                "Updating Antigravity CLI",
                "powershell",
                "irm https://antigravity.google/cli/install.ps1 | iex",
            ),
        ),
        signin_mode="browser",
        # One tiny prompt: if there is no session yet, Antigravity opens the Google sign-in page.
        signin_args=("-p", "Reply with exactly the single word OK", "--output-format", "json"),
        status_args=None,
        run_cmd="agy",
        auth_env_var="",
        auth_file_hints=(),
        description="Google's terminal coding agent. Sign in with your Google account.",
        docs_url="https://antigravity.google/docs/cli/install",
    ),
    AgentCliDef(
        id="codex",
        name="Codex",
        maker="OpenAI",
        commands=("codex",),
        extra_dirs=(r"%APPDATA%\npm",),
        install=(InstallStep("Installing Codex", "npm", "@openai/codex"),),
        update=(InstallStep("Updating Codex", "npm", "@openai/codex@latest"),),
        signin_mode="browser",
        signin_args=("login",),
        status_args=("login", "status"),
        run_cmd="codex",
        auth_env_var="",
        auth_file_hints=(),
        description="OpenAI's coding agent. Sign in with your ChatGPT account.",
        docs_url="https://developers.openai.com/codex/cli",
    ),
    AgentCliDef(
        id="claude",
        name="Claude Code",
        maker="Anthropic",
        commands=("claude",),
        extra_dirs=(r"%USERPROFILE%\.local\bin", r"%APPDATA%\npm"),
        install=(
            InstallStep(
                "Downloading the official Claude Code installer",
                "powershell",
                "irm https://claude.ai/install.ps1 | iex",
            ),
        ),
        update=(
            InstallStep(
                "Updating Claude Code",
                "powershell",
                "irm https://claude.ai/install.ps1 | iex",
            ),
        ),
        signin_mode="browser",
        signin_args=("auth", "login"),
        status_args=("auth", "status"),
        run_cmd="claude",
        auth_env_var="ANTHROPIC_API_KEY",
        auth_file_hints=(),
        description="Anthropic's coding agent. Sign in with your Claude account.",
        docs_url="https://code.claude.com/docs/en/quickstart",
        accepts_code=True,
    ),
)

_AGENTS = {agent.id: agent for agent in SUPPORTED_AGENTS}
_CACHE_SECONDS = 30.0
_cache: tuple[float, list[dict[str, Any]]] | None = None
_lock = threading.Lock()
_probe_results: dict[str, tuple[float, bool]] = {}

JOB_MAX_SECONDS = {"install": 900.0, "signin": 420.0, "update": 900.0}


def _custom_agents() -> list[AgentCliDef]:
    """Reads custom company CLIs from AppState and turns them into AgentCliDef instances."""
    try:
        from quant_system.server.v2.router import services

        raw_custom = services().state.list_custom_clis()
    except Exception:
        raw_custom = []

    res: list[AgentCliDef] = []
    for item in raw_custom:
        cli_id = str(item["id"])
        cmd = str(item.get("command") or cli_id)
        install_steps: list[InstallStep] = []
        if item.get("install_cmd"):
            install_steps.append(
                InstallStep(
                    f"Installing {item.get('name', cli_id)}", "powershell", str(item["install_cmd"])
                )
            )
        update_steps: list[InstallStep] = []
        if item.get("update_cmd"):
            update_steps.append(
                InstallStep(
                    f"Updating {item.get('name', cli_id)}", "powershell", str(item["update_cmd"])
                )
            )
        elif item.get("install_cmd"):
            update_steps.append(
                InstallStep(
                    f"Updating {item.get('name', cli_id)}", "powershell", str(item["install_cmd"])
                )
            )
        status_raw = item.get("status_args", "--version")
        status_args = tuple(status_raw.split()) if status_raw else None
        res.append(
            AgentCliDef(
                id=cli_id,
                name=str(item.get("name") or cli_id),
                maker=str(item.get("maker") or "Company"),
                commands=(cmd,),
                extra_dirs=(r"%LOCALAPPDATA%\bin", r"%APPDATA%\npm"),
                install=tuple(install_steps),
                update=tuple(update_steps),
                signin_mode="browser",
                signin_args=(),
                status_args=status_args,
                run_cmd=cmd,
                auth_env_var="",
                auth_file_hints=(),
                description=str(
                    item.get("description")
                    or f"{item.get('name', cli_id)} by {item.get('maker', 'Company')}"
                ),
                docs_url=str(item.get("docs_url") or ""),
            )
        )
    return res


def all_agents() -> tuple[AgentCliDef, ...]:
    return SUPPORTED_AGENTS + tuple(_custom_agents())


def get_agent(agent_id: str) -> AgentCliDef | None:
    for agent in all_agents():
        if agent.id == agent_id:
            return agent
    return None


def is_custom_agent(agent_id: str) -> bool:
    return any(a.id == agent_id for a in _custom_agents())


def all_chat_cli_ids() -> list[str]:
    return [a.id for a in all_agents()]


def get_workspace_root() -> Path:
    """Returns the root directory of the QuantOS project/workspace."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent.resolve()
    return Path(__file__).resolve().parents[4]


# ------------------------------------------------------------------------------ discovery


def _registry_path(hive: Any, subkey: str) -> list[str]:
    import winreg

    try:
        with winreg.OpenKey(hive, subkey) as key:
            value, _ = winreg.QueryValueEx(key, "Path")
    except OSError:
        return []
    return [part for part in os.path.expandvars(str(value)).split(os.pathsep) if part]


def search_path() -> str:
    """This process's PATH plus the folders Windows has on record and each CLI's usual home.

    A program installed a moment ago is not on the PATH this app was started with, so a plain
    lookup would report a successful install as "not installed".
    """
    parts = [p for p in os.environ.get("PATH", "").split(os.pathsep) if p]
    if sys.platform == "win32":
        import winreg

        parts += _registry_path(winreg.HKEY_CURRENT_USER, "Environment")
        parts += _registry_path(
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
        )
    for agent in all_agents():
        parts += [os.path.expandvars(d) for d in agent.extra_dirs]
    seen: set[str] = set()
    unique: list[str] = []
    for part in parts:
        marker = os.path.normcase(os.path.normpath(part))
        if marker not in seen:
            seen.add(marker)
            unique.append(part)
    return os.pathsep.join(unique)


def _environment() -> dict[str, str]:
    return {**os.environ, "PATH": search_path()}


def _find(command: str) -> str | None:
    return shutil.which(command, path=search_path())


def _run_hidden(args: list[str], *, timeout: float, stdin_devnull: bool = True) -> tuple[int, str]:
    """Run a command without showing a window and return ``(exit code, combined output)``."""
    try:
        completed = subprocess.run(
            args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
            creationflags=_NO_WINDOW,
            env=_environment(),
            stdin=subprocess.DEVNULL if stdin_devnull else None,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return 1, str(error)
    return completed.returncode, (completed.stdout or "") + (completed.stderr or "")


def _check_auth_status(agent: AgentCliDef, executable: str | None) -> tuple[bool | None, str]:
    """``(signed in?, plain explanation)``. ``None`` means this CLI offers no way to tell."""
    if agent.status_args and executable:
        code, _ = _run_hidden([executable, *agent.status_args], timeout=12.0)
        if code == 0:
            return True, "Signed in"
    if agent.auth_env_var and os.environ.get(agent.auth_env_var, "").strip():
        return True, f"Using the {agent.auth_env_var} key saved in QuantOS"
    home = Path.home()
    for hint in agent.auth_file_hints:
        if (home / hint).is_file():
            return True, "Signed in"
    if agent.status_args:
        return False, "Not signed in yet"
    probe = _probe_results.get(agent.id)
    if probe is not None:
        return probe[1], "Signed in" if probe[1] else "Not signed in yet"
    return None, "Not checked yet"


def _inspect_cli(agent: AgentCliDef) -> dict[str, Any]:
    resolved_cmd: str | None = None
    resolved_path: str | None = None
    for cmd in agent.commands:
        found = _find(cmd)
        if found:
            resolved_cmd, resolved_path = cmd, found
            break

    version: str | None = None
    if resolved_path:
        code, text = _run_hidden([resolved_path, "--version"], timeout=8.0)
        lines = text.strip().splitlines()
        if code == 0 and lines:
            version = lines[0][:80]

    authenticated, auth_detail = (
        _check_auth_status(agent, resolved_path) if resolved_path else (False, "Not installed")
    )
    if resolved_path is None:
        state = "NOT_INSTALLED"
    elif authenticated is True:
        state = "CONNECTED"
    elif authenticated is False:
        state = "NEEDS_SIGN_IN"
    else:
        state = "UNKNOWN"

    return {
        "id": agent.id,
        "name": agent.name,
        "maker": agent.maker,
        "description": agent.description,
        "docs_url": agent.docs_url,
        "installed": resolved_path is not None,
        "command": resolved_cmd or agent.commands[0],
        "path": resolved_path,
        "version": version,
        "authenticated": authenticated,
        "auth_detail": auth_detail,
        "state": state,
        "signin_mode": agent.signin_mode,
        "install_steps": [step.display() for step in agent.install],
        "update_steps": [step.display() for step in (agent.update or agent.install)],
        "can_update": resolved_path is not None,
        "update_available": False,
        "run_cmd": agent.run_cmd,
        "is_custom": is_custom_agent(agent.id),
    }


def list_cli_status(force: bool = False) -> list[dict[str, Any]]:
    """Detection, sign-in state and any running job for every supported coding-agent CLI."""
    global _cache
    with _lock:
        if force or _cache is None or time.monotonic() - _cache[0] >= _CACHE_SECONDS:
            _cache = (time.monotonic(), [_inspect_cli(agent) for agent in all_agents()])
        inspected = _cache[1]
    return [{**item, "job": job_snapshot(str(item["id"]))} for item in inspected]


def installed_chat_clis(ids: Iterable[str]) -> dict[str, str]:
    """Where each named app is installed (id -> program path). A quick lookup: nothing is started."""
    wanted = set(ids)
    found: dict[str, str] = {}
    for agent in all_agents():
        path = next((hit for cmd in agent.commands if (hit := _find(cmd))), None)
        if agent.id in wanted and path:
            found[agent.id] = path
    return found


def record_probe(agent_id: str, signed_in: bool) -> None:
    """Remember what a real test of this app showed, for the apps that cannot say whether they are signed in."""
    _probe_results[agent_id] = (time.monotonic(), signed_in)
    invalidate_cache()


def invalidate_cache() -> None:
    global _cache
    with _lock:
        _cache = None


# ------------------------------------------------------------------------------------ jobs


@dataclass(slots=True)
class _Job:
    agent_id: str
    action: str
    state: str = "RUNNING"  # RUNNING | DONE | FAILED
    message: str = ""
    url: str | None = None
    output: list[str] = field(default_factory=list)
    started: float = field(default_factory=time.monotonic)
    finished: float | None = None
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    interactive: bool = False  # keep stdin open so a sign-in code can be passed through
    process: subprocess.Popen[str] | None = None


_jobs: dict[str, _Job] = {}
_jobs_lock = threading.Lock()


def job_snapshot(agent_id: str) -> dict[str, Any] | None:
    with _jobs_lock:
        job = _jobs.get(agent_id)
        if job is None:
            return None
        return {
            "id": job.id,
            "action": job.action,
            "state": job.state,
            "message": job.message,
            "url": job.url,
            "accepts_code": job.interactive and job.state == "RUNNING",
            "output": job.output[-6:],
            "seconds": round((job.finished or time.monotonic()) - job.started, 1),
        }


def _set(job: _Job, **changes: Any) -> None:
    with _jobs_lock:
        for name, value in changes.items():
            setattr(job, name, value)


def _stream(job: _Job, args: list[str], timeout: float) -> int:
    """Run ``args`` hidden, keep the last output lines and the first URL it prints."""
    try:
        process = subprocess.Popen(
            args,
            stdin=subprocess.PIPE if job.interactive else subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=_NO_WINDOW,
            env=_environment(),
        )
    except OSError as error:
        _set(job, output=[*job.output, str(error)])
        return 1
    job.process = process
    killer = threading.Timer(timeout, process.kill)
    killer.start()
    try:
        assert process.stdout is not None
        for raw in process.stdout:
            line = raw.strip()
            if not line:
                continue
            with _jobs_lock:
                job.output.append(line[:300])
                del job.output[:-40]
                if job.url is None:
                    match = _URL.search(line)
                    if match:
                        job.url = match.group(0).rstrip(".,)")
        return process.wait()
    finally:
        killer.cancel()
        job.process = None


def send_job_input(agent_id: str, text: str) -> bool:
    """Pass a sign-in code the person pasted to the running sign-in. Never logged or stored."""
    with _jobs_lock:
        job = _jobs.get(agent_id)
        process = (
            job.process if job is not None and job.state == "RUNNING" and job.interactive else None
        )
    if process is None or process.stdin is None:
        return False
    try:
        process.stdin.write(text.strip() + "\n")
        process.stdin.flush()
    except OSError:
        return False
    return True


def _powershell(snippet: str) -> list[str]:
    return [
        "powershell.exe",
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        snippet,
    ]


def _step_command(step: InstallStep) -> list[str] | None:
    if step.kind == "powershell":
        return _powershell(step.argument)
    if step.kind == "npm":
        npm = _find("npm")
        return [npm, "install", "-g", step.argument] if npm else None
    winget = _find("winget")
    if winget is None:
        return None
    return [
        winget,
        "install",
        "-e",
        "--id",
        step.argument,
        "--silent",
        "--accept-package-agreements",
        "--accept-source-agreements",
    ]


def _run_install(job: _Job, agent: AgentCliDef) -> None:
    steps = list(agent.install)
    if any(step.kind == "npm" for step in steps) and _find("npm") is None:
        steps.insert(0, _NODE_STEP)
    for step in steps:
        _set(job, message=step.label + "...")
        command = _step_command(step)
        if command is None:
            _set(
                job,
                state="FAILED",
                message="Node.js is needed first. Install it from nodejs.org, then try again."
                if step.kind != "winget"
                else "Windows Package Manager (winget) is not available on this PC.",
            )
            return
        if _stream(job, command, JOB_MAX_SECONDS["install"]) != 0:
            _set(
                job, state="FAILED", message=f"{step.label} did not finish. See the details below."
            )
            return
    invalidate_cache()
    if any(_find(command) for command in agent.commands):
        _set(job, state="DONE", message=f"{agent.name} is installed.")
    else:
        _set(
            job,
            state="FAILED",
            message="The installer finished but the program was not found. Restart QuantOS and check again.",
        )


def _run_signin(job: _Job, agent: AgentCliDef) -> None:
    executable = next((found for c in agent.commands if (found := _find(c))), None)
    if executable is None:
        _set(job, state="FAILED", message=f"{agent.name} is not installed yet.")
        return
    _set(job, message="Your browser will open. Sign in there, then come back to QuantOS.")
    code = _stream(job, [executable, *agent.signin_args], JOB_MAX_SECONDS["signin"])
    invalidate_cache()
    if agent.status_args:
        signed_in, _ = _check_auth_status(agent, executable)
    else:
        text = "\n".join(job.output)
        signed_in = code == 0 and '"status":"SUCCESS"' in text.replace(" ", "")
        _probe_results[agent.id] = (time.monotonic(), signed_in)
        invalidate_cache()
    if signed_in:
        _set(job, state="DONE", message=f"{agent.name} is connected.")
    else:
        _set(job, state="FAILED", message="Sign-in was not completed. You can try again.")


def _run_update(job: _Job, agent: AgentCliDef) -> None:
    steps = list(agent.update if agent.update else agent.install)
    if any(step.kind == "npm" for step in steps) and _find("npm") is None:
        steps.insert(0, _NODE_STEP)
    for step in steps:
        _set(job, message=step.label + "...")
        command = _step_command(step)
        if command is None:
            _set(
                job,
                state="FAILED",
                message="Cannot update without required package manager.",
            )
            return
        if _stream(job, command, JOB_MAX_SECONDS["update"]) != 0:
            _set(
                job, state="FAILED", message=f"{step.label} did not finish. See the details below."
            )
            return
    invalidate_cache()
    resolved_path = next((found for c in agent.commands if (found := _find(c))), None)
    version = None
    if resolved_path:
        code, text = _run_hidden([resolved_path, "--version"], timeout=8.0)
        lines = text.strip().splitlines()
        if code == 0 and lines:
            version = lines[0][:80]
    _set(
        job,
        state="DONE",
        message=f"{agent.name} is updated to {version or 'the latest version'}.",
    )


def start_agent_job(
    agent_id: str, action: Literal["install", "signin", "update"]
) -> dict[str, Any]:
    """Start (or join) a background install, sign-in, or update and return its snapshot straight away."""
    agent = get_agent(agent_id)
    if agent is None:
        raise ValueError(f"Unknown AI app: {agent_id}")
    with _jobs_lock:
        existing = _jobs.get(agent_id)
        if existing is not None and existing.state == "RUNNING":
            running = existing
        else:
            running = None
            job = _Job(
                agent_id=agent_id,
                action=action,
                interactive=action == "signin" and agent.accepts_code,
            )
            _jobs[agent_id] = job
    if running is None:
        if action == "install":
            target = _run_install
        elif action == "signin":
            target = _run_signin
        else:
            target = _run_update

        def work() -> None:
            try:
                target(job, agent)
            except Exception as error:  # a worker must always end in DONE or FAILED
                logger.exception("Agent job %s/%s failed", agent_id, action)
                _set(job, state="FAILED", message=f"Unexpected error: {error}")
            finally:
                _set(job, finished=time.monotonic())
                invalidate_cache()

        threading.Thread(target=work, name=f"QuantOS-cli-{agent_id}-{action}", daemon=True).start()
    snapshot = job_snapshot(agent_id)
    assert snapshot is not None
    return {"success": True, "action": action, "job": snapshot, "message": snapshot["message"]}


def auto_update_all_clis() -> list[dict[str, Any]]:
    """Checks all installed CLIs and triggers background updates."""
    started: list[dict[str, Any]] = []
    for agent in all_agents():
        resolved_path = next((found for c in agent.commands if (found := _find(c))), None)
        if resolved_path:
            try:
                started.append(start_agent_job(agent.id, "update"))
            except Exception as err:
                logger.warning("Could not auto-update %s: %s", agent.id, err)
    return started


def fetch_cli_capabilities(agent_id: str, force_refresh: bool = False) -> dict[str, Any]:
    """Fetch live models and features for the given CLI."""
    agent = get_agent(agent_id)
    if agent is None:
        raise ValueError(f"Unknown AI app: {agent_id}")

    status_list = list_cli_status(force=force_refresh)
    info = next((s for s in status_list if s["id"] == agent_id), None)
    installed = bool(info and info.get("installed"))
    authenticated = bool(info and info.get("authenticated"))
    version = str(info.get("version") or "") if info else ""

    models: list[dict[str, Any]] = []
    features: list[dict[str, Any]] = []

    if is_custom_agent(agent_id):
        models = [
            {
                "id": f"{agent_id}-default",
                "name": f"{agent.name} Model",
                "provider": agent.maker,
                "description": f"Custom Company Model via {agent.name}",
                "context_window": "128,000+ tokens",
                "recommended": True,
            }
        ]
        features = [
            {
                "name": "Company CLI Integration",
                "description": "Custom enterprise CLI agent bridge",
            },
            {"name": "Automatic Updates", "description": "Automated update via company pipeline"},
        ]
        return {
            "agent_id": agent_id,
            "agent_name": agent.name,
            "installed": installed,
            "authenticated": authenticated,
            "version": version or None,
            "models": models,
            "features": features,
            "latest_version": version or None,
            "last_fetched": datetime.now(UTC).isoformat(),
        }

    if agent_id == "antigravity":
        # Check if user has GEMINI_API_KEY saved to query live model catalog
        gemini_key = os.environ.get("GEMINI_API_KEY", "").strip() or None
        live_fetched: list[dict[str, Any]] = []
        if gemini_key:
            try:
                from quant_system.alpha.model_catalog import fetch_models

                live_models = fetch_models("gemini", gemini_key, refresh=force_refresh)
                live_fetched = [
                    {
                        "id": m.id,
                        "name": m.name,
                        "provider": "Google DeepMind",
                        "description": "Live Gemini Model from Google AI Studio",
                        "context_window": "1,000,000 - 2,000,000 tokens",
                        "recommended": "2.5" in m.id or "3.8" in m.id or "pro" in m.id,
                    }
                    for m in live_models
                ]
            except Exception as e:
                logger.debug("Could not fetch live Google Gemini models: %s", e)

        if live_fetched:
            models = live_fetched
        else:
            models = [
                {
                    "id": "gemini-2.5-pro",
                    "name": "Gemini 2.5 Pro",
                    "provider": "Google DeepMind",
                    "description": "DeepMind Advanced Reasoning, Long Context & Code Synthesis",
                    "context_window": "2,000,000 tokens",
                    "recommended": True,
                },
                {
                    "id": "gemini-2.5-flash",
                    "name": "Gemini 2.5 Flash",
                    "provider": "Google DeepMind",
                    "description": "Ultra-fast Agentic Reasoning with High Throughput",
                    "context_window": "1,000,000 tokens",
                    "recommended": True,
                },
                {
                    "id": "gemini-3.8-flash",
                    "name": "Gemini 3.8 Flash (High)",
                    "provider": "Google DeepMind",
                    "description": "State-of-the-Art DeepMind Agentic Reasoning Engine",
                    "context_window": "1,000,000 tokens",
                    "recommended": True,
                },
                {
                    "id": "gemini-2.0-flash",
                    "name": "Gemini 2.0 Flash",
                    "provider": "Google DeepMind",
                    "description": "Low Latency Multimodal & Autonomous Tool Calling",
                    "context_window": "1,000,000 tokens",
                    "recommended": False,
                },
                {
                    "id": "gemini-1.5-pro",
                    "name": "Gemini 1.5 Pro",
                    "provider": "Google DeepMind",
                    "description": "General Purpose Deep Reasoning with 2M Token Context",
                    "context_window": "2,000,000 tokens",
                    "recommended": False,
                },
            ]

        features = [
            {
                "id": "multi_agent",
                "name": "Multi-Agent System & Subagents",
                "description": "Hierarchical agent delegation (invoke_subagent, define_subagent) for autonomous development.",
                "status": "active",
            },
            {
                "id": "mcp",
                "name": "Model Context Protocol (MCP)",
                "description": "Native integration with standard MCP servers, Chrome DevTools, SQLite, and custom tools.",
                "status": "active",
            },
            {
                "id": "sandbox",
                "name": "Autonomous Execution Sandbox",
                "description": "Secure command execution, background task management, and reactive wakeups.",
                "status": "active",
            },
            {
                "id": "governance",
                "name": "Quant Model Governance & Invariants",
                "description": "Real-time sync with agent_context/, goalpost tripwires (G1-G7), and immutable ledgers.",
                "status": "active",
            },
            {
                "id": "verification",
                "name": "Automated Linting & Verification Guards",
                "description": "Automated Ruff, strict Mypy, secret scanning, and reproducible test suites.",
                "status": "active",
            },
            {
                "id": "skills",
                "name": "Interactive Slash Commands & Custom Skills",
                "description": "Modular skill engine for specialized quant trading, Shariah filtering, and data engineering.",
                "status": "active",
            },
        ]
    elif agent_id == "claude":
        models = [
            {
                "id": "claude-3-7-sonnet-20250219",
                "name": "Claude 3.7 Sonnet",
                "provider": "Anthropic",
                "description": "Hybrid Reasoning & Fast Thinking",
                "context_window": "200,000 tokens",
                "recommended": True,
            },
            {
                "id": "claude-3-5-sonnet-20241022",
                "name": "Claude 3.5 Sonnet",
                "provider": "Anthropic",
                "description": "High Performance Code & Architecture",
                "context_window": "200,000 tokens",
                "recommended": True,
            },
            {
                "id": "claude-3-5-haiku-20241022",
                "name": "Claude 3.5 Haiku",
                "provider": "Anthropic",
                "description": "Rapid Utility & Inline Assistance",
                "context_window": "200,000 tokens",
                "recommended": False,
            },
        ]
        features = [
            {
                "id": "bash",
                "name": "Bash Tool Execution",
                "description": "Direct shell command execution inside worktrees.",
                "status": "active",
            },
            {
                "id": "edit",
                "name": "File Editing & Multi-edit",
                "description": "Contiguous patch application and search/replace.",
                "status": "active",
            },
            {
                "id": "mcp",
                "name": "MCP Server Client",
                "description": "Model Context Protocol tools and resources support.",
                "status": "active",
            },
        ]
    elif agent_id == "codex":
        models = [
            {
                "id": "o3-mini",
                "name": "o3-mini",
                "provider": "OpenAI",
                "description": "High-Efficiency Reasoning for Code & STEM",
                "context_window": "200,000 tokens",
                "recommended": True,
            },
            {
                "id": "o1",
                "name": "o1",
                "provider": "OpenAI",
                "description": "Deep Reasoning Model with Broad General Knowledge",
                "context_window": "200,000 tokens",
                "recommended": True,
            },
            {
                "id": "gpt-4o",
                "name": "GPT-4o",
                "provider": "OpenAI",
                "description": "Flagship Multimodal Omnimodel",
                "context_window": "128,000 tokens",
                "recommended": False,
            },
        ]
        features = [
            {
                "id": "sandbox",
                "name": "Sandboxed Execution",
                "description": "Read-only and governed execution environments.",
                "status": "active",
            },
            {
                "id": "diff",
                "name": "Diff & Patch Generation",
                "description": "Targeted file modifications and unified diffs.",
                "status": "active",
            },
        ]

    return {
        "agent_id": agent_id,
        "name": agent.name,
        "maker": agent.maker,
        "installed": installed,
        "authenticated": authenticated,
        "version": version or None,
        "models": models,
        "features": features,
        "update_available": False,
        "latest_version": version or None,
        "last_fetched": datetime.now(UTC).isoformat(),
    }


# ------------------------------------------------------------------------------ terminal use


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
    """Open an agent in a terminal window in the QuantOS folder.

    A terminal is the right place to *work with* a coding agent, so ``run`` and ``custom`` open one.
    ``install`` and ``signin`` do not come here; they are background jobs (:func:`start_agent_job`),
    except for a CLI whose sign-in needs an interactive prompt (``signin_mode == "terminal"``).
    """
    root_dir = workspace or get_workspace_root()
    cwd_str = str(root_dir)

    target_cmd: str
    title: str

    if action == "custom":
        if not custom_command:
            raise ValueError("custom_command must be provided when action is 'custom'")
        target_cmd = custom_command
        title = f"QuantOS - {custom_command[:25]}"
    else:
        agent = get_agent(agent_id)
        if agent is None:
            raise ValueError(f"Unknown AI app: {agent_id}")
        title = f"QuantOS - {agent.name}"
        target_cmd = agent.run_cmd

    logger.info("Launching agent session [%s]: %s (cwd=%s)", action, target_cmd, cwd_str)

    if sys.platform == "win32":
        wt_exe = find_windows_terminal()
        banner = f"Write-Host '=== {title} ===' -ForegroundColor Cyan; {target_cmd}"
        if wt_exe:
            cmd_args = [
                wt_exe,
                "-d",
                cwd_str,
                "--title",
                title,
                "powershell.exe",
                "-NoExit",
                "-Command",
                banner,
            ]
        else:
            cmd_args = [
                "cmd.exe", "/c", "start", title, "powershell.exe", "-NoExit", "-Command",
                f"Set-Location '{cwd_str}'; {banner}",
            ]  # fmt: skip

        try:
            subprocess.Popen(cmd_args, cwd=cwd_str, env=_environment(), shell=False)
            return {
                "success": True,
                "action": action,
                "command": target_cmd,
                "cwd": cwd_str,
                "launcher": "windows_terminal" if wt_exe else "powershell",
                "message": f"Opened {title}.",
            }
        except Exception as err:
            logger.error("Failed to launch terminal process: %s", err)
            raise RuntimeError(f"Failed to launch terminal process: {err}") from err

    for term in ("gnome-terminal", "xterm", "kitty", "alacritty"):
        if shutil.which(term):
            subprocess.Popen(
                [term, "--", "bash", "-c", f"cd '{cwd_str}' && {target_cmd}; exec bash"]
            )
            return {"success": True, "command": target_cmd, "launcher": term}

    raise RuntimeError("No compatible terminal emulator detected on host.")
