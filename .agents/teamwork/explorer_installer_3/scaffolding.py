"""QuantOS Environment Scaffolding & Drive Isolation Module.

Handles smart drive selection, isolated folder scaffolding, starter .env generation,
and standard Windows shortcut creation.
"""

from __future__ import annotations

import ctypes
import os
import platform
import shutil
import subprocess
from pathlib import Path
from typing import NamedTuple

__all__ = [
    "DriveInfo",
    "inspect_windows_drives",
    "select_smart_installation_path",
    "scaffold_runtime_directories",
    "generate_starter_env_file",
    "create_windows_shortcuts",
]

# Win32 Drive Constants
DRIVE_UNKNOWN = 0
DRIVE_NO_ROOT_DIR = 1
DRIVE_REMOVABLE = 2
DRIVE_FIXED = 3
DRIVE_REMOTE = 4
DRIVE_CDROM = 5
DRIVE_RAMDISK = 6

REQUIRED_FREE_SPACE_BYTES = 2 * 1024 * 1024 * 1024  # 2.0 GB


class DriveInfo(NamedTuple):
    letter: str
    drive_type: int
    free_bytes: int
    total_bytes: int
    is_fixed: bool


def inspect_windows_drives() -> list[DriveInfo]:
    """Inspects all available drive letters on Windows using Win32 GetDriveTypeW."""
    if platform.system() != "Windows":
        total, used, free = shutil.disk_usage("/")
        return [DriveInfo(letter="/", drive_type=DRIVE_FIXED, free_bytes=free, total_bytes=total, is_fixed=True)]

    kernel32 = ctypes.windll.kernel32
    drives: list[DriveInfo] = []

    # Enumerate drive letters from D to Z, then C, B, A
    for letter in "DEFGHIJKLMNOPQRSTUVWXYZCBA":
        root_path = f"{letter}:\\"
        drive_type = kernel32.GetDriveTypeW(root_path)
        if drive_type in (DRIVE_NO_ROOT_DIR, DRIVE_UNKNOWN):
            continue

        try:
            total, used, free = shutil.disk_usage(root_path)
            drives.append(
                DriveInfo(
                    letter=f"{letter}:",
                    drive_type=drive_type,
                    free_bytes=free,
                    total_bytes=total,
                    is_fixed=(drive_type == DRIVE_FIXED),
                )
            )
        except OSError:
            continue
    return drives


def select_smart_installation_path(folder_name: str = "QuantOS") -> Path:
    """Selects the optimal installation path on Windows.

    Prefers D:\\ if fixed and >= 2 GB free space, then other fixed drives,
    falling back to C:\\.
    """
    drives = {d.letter.upper(): d for d in inspect_windows_drives()}

    # 1. Priority 1: D:\ if fixed and has >= 2 GB
    d_drive = drives.get("D:")
    if d_drive and d_drive.is_fixed and d_drive.free_bytes >= REQUIRED_FREE_SPACE_BYTES:
        return Path(f"D:\\{folder_name}")

    # 2. Priority 2: Other non-C fixed drives with >= 2 GB
    for letter, info in drives.items():
        if letter not in ("C:", "D:") and info.is_fixed and info.free_bytes >= REQUIRED_FREE_SPACE_BYTES:
            return Path(f"{letter}\\{folder_name}")

    # 3. Priority 3: Fallback to C:\
    c_drive = drives.get("C:")
    if c_drive and c_drive.free_bytes >= REQUIRED_FREE_SPACE_BYTES:
        return Path(f"C:\\{folder_name}")

    # 4. Ultimate fallback
    fallback_letter = "D:" if "D:" in drives else "C:" if "C:" in drives else ""
    if fallback_letter:
        return Path(f"{fallback_letter}\\{folder_name}")
    return Path(folder_name).resolve()


def scaffold_runtime_directories(install_root: Path) -> dict[str, Path]:
    """Creates isolated runtime directories and returns their absolute paths."""
    subdirs = {
        "root": install_root,
        "data": install_root / "data",
        "evidence": install_root / "data" / "evidence",
        "cache": install_root / "data" / "cache",
        "logs": install_root / "logs",
        "tmp": install_root / "tmp",
        "matplotlib": install_root / "tmp" / "matplotlib",
        "pycache": install_root / "tmp" / "pycache",
    }
    for p in subdirs.values():
        p.mkdir(parents=True, exist_ok=True)
    return subdirs


def generate_starter_env_file(install_root: Path, overwrite: bool = False) -> Path:
    """Generates the starter .env configuration file if not already existing."""
    env_path = install_root / ".env"
    if env_path.exists() and not overwrite:
        return env_path

    content = """# ==============================================================================
# QuantOS Institutional Quantitative Trading & Risk Platform Configuration
# Location: .env (Installation Root)
# ==============================================================================

# ------------------------------------------------------------------------------
# 1. Server & Local Network Runtime
# ------------------------------------------------------------------------------
QUANTOS_HOST=127.0.0.1
QUANTOS_PORT=8080
QUANTOS_LOG_LEVEL=INFO

# ------------------------------------------------------------------------------
# 2. Storage Sandbox & Evidence Paths
# All paths remain strictly within the QuantOS installation drive.
# ------------------------------------------------------------------------------
QUANTOS_EVIDENCE_ROOT=data/evidence

# ------------------------------------------------------------------------------
# 3. Market Data Provider: Upstox V3 API
# Leave blank to run in offline SYNTHETIC mode.
# To connect live NSE market data:
#   - UPSTOX_ANALYTICS_TOKEN: Obtain from Upstox Developer Console (Valid ~1 Year)
#   - UPSTOX_ACCESS_TOKEN: Daily interactive token (Expires 03:30 IST each morning)
# ------------------------------------------------------------------------------
UPSTOX_ANALYTICS_TOKEN=
UPSTOX_ACCESS_TOKEN=
UPSTOX_API_KEY=
UPSTOX_API_SECRET=

# ------------------------------------------------------------------------------
# 4. Multi-Agent AI Advisory Keys (Optional)
# QuantOS utilizes an ensemble key pool to generate consensus ranking strategies.
# You can supply single keys or comma-separated lists for load balancing.
# ------------------------------------------------------------------------------
GROQ_API_KEY=
OPENROUTER_API_KEY=
OPENAI_API_KEY=
ANTHROPIC_API_KEY=

# ------------------------------------------------------------------------------
# 5. Advanced Model Hubs & Hardware Accelerators
# ------------------------------------------------------------------------------
# Hugging Face token for downloading fine-tuned Mizan cross-sectional models:
HF_TOKEN=

# AWS Bedrock settings (if using AWS foundation models):
QUANTOS_BEDROCK_REGION=us-east-1
QUANTOS_BEDROCK_SCOPE=global
"""
    env_path.write_text(content, encoding="utf-8")
    return env_path


def create_windows_shortcuts(
    install_dir: Path, desktop: bool = True, start_menu: bool = True
) -> list[Path]:
    """Creates standard Windows Desktop and Start Menu shortcuts pointing to quantos.exe.

    Explicitly sets WorkingDirectory = install_dir to enforce drive isolation.
    """
    created: list[Path] = []
    target_exe = install_dir / "quantos.exe"
    if not target_exe.exists():
        target_exe = install_dir / "QuantOS.exe"

    powershell_script = f"""
$WshShell = New-Object -ComObject WScript.Shell
$TargetExe = "{target_exe}"
$WorkingDir = "{install_dir}"
$Description = "QuantOS Desktop Quantitative Trading, Research & Risk Engine"
$IconLoc = "{target_exe},0"

if ("{desktop}" -eq "True") {{
    $DesktopDir = [System.Environment]::GetFolderPath([System.Environment+SpecialFolder]::Desktop)
    $DeskLnk = Join-Path $DesktopDir "QuantOS.lnk"
    $Shortcut = $WshShell.CreateShortcut($DeskLnk)
    $Shortcut.TargetPath = $TargetExe
    $Shortcut.WorkingDirectory = $WorkingDir
    $Shortcut.Description = $Description
    $Shortcut.IconLocation = $IconLoc
    $Shortcut.Save()
}}

if ("{start_menu}" -eq "True") {{
    $ProgramsDir = [System.Environment]::GetFolderPath([System.Environment+SpecialFolder]::Programs)
    $QuantOSMenu = Join-Path $ProgramsDir "QuantOS"
    if (-not (Test-Path $QuantOSMenu)) {{ New-Item -ItemType Directory -Path $QuantOSMenu -Force | Out-Null }}
    $StartLnk = Join-Path $QuantOSMenu "QuantOS.lnk"
    $Shortcut = $WshShell.CreateShortcut($StartLnk)
    $Shortcut.TargetPath = $TargetExe
    $Shortcut.WorkingDirectory = $WorkingDir
    $Shortcut.Description = $Description
    $Shortcut.IconLocation = $IconLoc
    $Shortcut.Save()
}}
"""
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", powershell_script],
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception as exc:
        print(f"[WARN] Shortcut creation notice: {exc}")

    return created
