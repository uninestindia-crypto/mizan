"""Agent CLI Bridge: install and sign in to coding-agent CLIs with one click, no terminal.

Install and sign-in run as hidden background jobs. The vendors' own sign-in commands open the
user's default browser themselves (``codex login``, ``claude auth login``, Antigravity on first
use), so the person sees only their browser, then the app flips to "Connected". A terminal window is
used only for the one thing that needs it: working *with* an agent (``Launch``), and for a CLI whose
sign-in genuinely needs an interactive prompt (Gemini CLI).

Commands come from each vendor's documentation (checked 2026-10-03):

* Antigravity: Go binary installed with ``irm https://antigravity.google/cli/install.ps1 | iex``
  into ``%LOCALAPPDATA%\\agy\\bin``; it signs in on first use and has no separate auth command.
* Claude Code: ``claude auth login`` / ``claude auth status`` (exit code 0 when signed in).
* Codex: ``codex login`` / ``codex login status`` (exit code 0 when signed in).
* Gemini CLI: ``npm install -g @google/gemini-cli``; "Login with Google" is chosen at first run.
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
from dataclasses import dataclass, field
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


_NODE_STEP = InstallStep(
    "Installing Node.js (needed by this tool)",
    "winget",
    "OpenJS.NodeJS.LTS",
)

SUPPORTED_AGENTS: tuple[AgentCliDef, ...] = (
    AgentCliDef(
        id="antigravity",
        name="Antigravity CLI",
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
        name="Codex CLI",
        maker="OpenAI",
        commands=("codex",),
        extra_dirs=(r"%APPDATA%\npm",),
        install=(InstallStep("Installing Codex", "npm", "@openai/codex"),),
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
    AgentCliDef(
        id="gemini",
        name="Gemini CLI",
        maker="Google",
        commands=("gemini",),
        extra_dirs=(r"%APPDATA%\npm",),
        install=(InstallStep("Installing Gemini CLI", "npm", "@google/gemini-cli"),),
        # Gemini CLI asks which sign-in method to use the first time it starts, so it needs a window.
        signin_mode="terminal",
        signin_args=(),
        status_args=None,
        run_cmd="gemini",
        auth_env_var="GEMINI_API_KEY",
        auth_file_hints=(r".gemini\oauth_creds.json",),
        description="Google's open-source Gemini terminal agent. Sign in with Google.",
        docs_url="https://geminicli.com/docs/get-started/authentication/",
    ),
)

_AGENTS = {agent.id: agent for agent in SUPPORTED_AGENTS}
_CACHE_SECONDS = 30.0
_cache: tuple[float, list[dict[str, Any]]] | None = None
_lock = threading.Lock()
_probe_results: dict[str, tuple[float, bool]] = {}

JOB_MAX_SECONDS = {"install": 900.0, "signin": 420.0}


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
    for agent in SUPPORTED_AGENTS:
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
        "run_cmd": agent.run_cmd,
    }


def list_cli_status(force: bool = False) -> list[dict[str, Any]]:
    """Detection, sign-in state and any running job for every supported coding-agent CLI."""
    global _cache
    with _lock:
        if force or _cache is None or time.monotonic() - _cache[0] >= _CACHE_SECONDS:
            _cache = (time.monotonic(), [_inspect_cli(agent) for agent in SUPPORTED_AGENTS])
        inspected = _cache[1]
    return [{**item, "job": job_snapshot(str(item["id"]))} for item in inspected]


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


def start_agent_job(agent_id: str, action: Literal["install", "signin"]) -> dict[str, Any]:
    """Start (or join) a background install or sign-in and return its snapshot straight away."""
    agent = _AGENTS.get(agent_id)
    if agent is None:
        raise ValueError(f"Unknown agent CLI: {agent_id}")
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
        target = _run_install if action == "install" else _run_signin

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
        title = f"Agent CLI - {custom_command[:25]}"
    else:
        if agent_id not in _AGENTS:
            raise ValueError(f"Unknown agent CLI: {agent_id}")
        agent = _AGENTS[agent_id]
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
