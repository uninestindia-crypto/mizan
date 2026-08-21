"""CLI auto-discovery, diagnostics, and non-technical consumer onboarding manager."""

from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class CLIDiagnosticItem:
    """Diagnostic state for an external agent CLI."""

    name: str
    command: str
    is_installed: bool
    executable_path: str | None
    version: str | None
    install_command: str
    login_command: str
    description: str


class CLIManager:
    """Scans and manages local CLI agent subscriptions for zero-friction consumer UX."""

    SUPPORTED_CLIS = [
        {
            "name": "Claude Code CLI",
            "command": "claude",
            "install_command": "npm install -g @anthropic-ai/claude-code",
            "login_command": "claude login",
            "description": "Macro regime, news sentiment, and qualitative reasoning (uses Claude Pro/Team).",
        },
        {
            "name": "Codex / OpenAI CLI",
            "command": "codex",
            "install_command": "npm install -g @openai/codex",
            "login_command": "codex login",
            "description": "Mathematical model sanity and strategy invariant auditing (uses ChatGPT Plus/Team).",
        },
        {
            "name": "Antigravity CLI",
            "command": "agy",
            "install_command": "pip install antigravity-cli",
            "login_command": "agy login",
            "description": "Autonomous multi-agent consensus and validation (uses Google AI / Antigravity).",
        },
    ]

    @classmethod
    def scan_cli(cls, command: str) -> tuple[bool, str | None, str | None]:
        """Check if CLI is in PATH and retrieve its version."""
        path = shutil.which(command)
        if not path:
            # Check common Windows npm/Python script paths as fallback
            appdata = os.getenv("APPDATA", "")
            local_appdata = os.getenv("LOCALAPPDATA", "")
            candidates = [
                os.path.join(appdata, "npm", f"{command}.cmd"),
                os.path.join(local_appdata, "Programs", command, f"{command}.exe"),
            ]
            for cand in candidates:
                if os.path.exists(cand):
                    path = cand
                    break

        if not path:
            return False, None, None

        version_str: str | None = None
        try:
            res = subprocess.run([path, "--version"], capture_output=True, text=True, timeout=2)
            if res.returncode == 0:
                version_str = res.stdout.strip().split("\n")[0]
        except Exception:
            version_str = "Available"

        return True, path, version_str

    @classmethod
    def inspect_system(cls) -> list[CLIDiagnosticItem]:
        """Run full diagnostic scan across all supported agent CLIs."""
        results: list[CLIDiagnosticItem] = []
        for meta in cls.SUPPORTED_CLIS:
            installed, path, ver = cls.scan_cli(meta["command"])
            results.append(
                CLIDiagnosticItem(
                    name=meta["name"],
                    command=meta["command"],
                    is_installed=installed,
                    executable_path=path,
                    version=ver,
                    install_command=meta["install_command"],
                    login_command=meta["login_command"],
                    description=meta["description"],
                )
            )
        return results

    @classmethod
    def get_summary(cls) -> dict[str, Any]:
        """Return human-readable summary for dashboard diagnostics and onboarding."""
        items = cls.inspect_system()
        installed_count = sum(1 for item in items if item.is_installed)
        return {
            "total_supported": len(items),
            "installed_count": installed_count,
            "has_any_cli": installed_count > 0,
            "items": [
                {
                    "name": item.name,
                    "command": item.command,
                    "status": "INSTALLED" if item.is_installed else "NOT_FOUND",
                    "path": item.executable_path,
                    "version": item.version,
                    "install_command": item.install_command,
                    "login_command": item.login_command,
                    "description": item.description,
                }
                for item in items
            ],
        }
