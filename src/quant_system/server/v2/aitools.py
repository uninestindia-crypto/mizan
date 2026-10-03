"""Detect locally installed AI assistant CLIs. Read-only: never installs or signs in."""

from __future__ import annotations

import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class CliSpec:
    command: str
    name: str
    maker: str
    install: str
    sign_in: str


CLIS: tuple[CliSpec, ...] = (
    CliSpec(
        "claude", "Claude Code", "Anthropic", "npm install -g @anthropic-ai/claude-code", "claude"
    ),
    CliSpec("codex", "Codex CLI", "OpenAI", "npm install -g @openai/codex", "codex login"),
    CliSpec("gemini", "Gemini CLI", "Google", "npm install -g @google/gemini-cli", "gemini"),
)

_CACHE_SECONDS = 60.0
_cache: tuple[float, list[dict[str, Any]]] | None = None
_lock = threading.Lock()


def detect_cli_tools(force: bool = False) -> list[dict[str, Any]]:
    global _cache
    with _lock:
        if not force and _cache is not None and time.monotonic() - _cache[0] < _CACHE_SECONDS:
            return _cache[1]
        found = [_detect(spec) for spec in CLIS]
        _cache = (time.monotonic(), found)
        return found


def _detect(spec: CliSpec) -> dict[str, Any]:
    path = shutil.which(spec.command)
    version: str | None = None
    if path:
        flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        try:
            completed = subprocess.run(
                [path, "--version"],
                capture_output=True,
                text=True,
                timeout=8,
                check=False,
                creationflags=flags,
            )
            text = (completed.stdout or completed.stderr).strip().splitlines()
            version = text[0][:80] if text else None
        except (OSError, subprocess.TimeoutExpired):
            version = None
    return {
        "command": spec.command,
        "name": spec.name,
        "maker": spec.maker,
        "installed": path is not None,
        "version": version,
        "install": spec.install,
        "sign_in": spec.sign_in,
    }
