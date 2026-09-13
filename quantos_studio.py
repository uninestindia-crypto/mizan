"""QuantOS Desktop Studio Host.

Unsloth Studio / LM Studio-style zero-console application runner.
- Runs silently without displaying a command prompt window to the user.
- Hosts the FastAPI backend server in a managed background thread.
- Launches a dedicated application window (via pywebview or Edge/Chrome App Mode).
- Gracefully terminates the background server and all worker threads upon window close.
"""

from __future__ import annotations

import logging
import multiprocessing
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

import uvicorn

from quant_system import __version__
from quant_system.config import load_env_file


def configure_drive_isolation() -> Path:
    """Configures root-relative runtime directories to guarantee ZERO C: drive leakage."""
    if getattr(sys, "frozen", False):
        app_root = Path(sys.executable).parent.resolve()
    else:
        app_root = Path(__file__).parent.resolve()

    for folder in ["tmp", "data", "logs"]:
        (app_root / folder).mkdir(parents=True, exist_ok=True)

    local_tmp = str(app_root / "tmp")
    os.environ["TEMP"] = local_tmp
    os.environ["TMP"] = local_tmp
    os.environ["TMPDIR"] = local_tmp
    os.environ["MPLCONFIGDIR"] = str(app_root / "tmp" / "matplotlib")
    os.environ["PYTHONPYCACHEPREFIX"] = str(app_root / "tmp" / "pycache")
    return app_root


def setup_studio_logging(app_root: Path) -> logging.Logger:
    """Sets up file-based logging for the studio runner."""
    log_file = app_root / "logs" / "studio.log"
    logger = logging.getLogger("quantos.studio")
    logger.setLevel(logging.INFO)

    # Avoid duplicate handlers on re-entry
    if not logger.handlers:
        fh = logging.FileHandler(log_file, encoding="utf-8")
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] [%(threadName)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        fh.setFormatter(formatter)
        logger.addHandler(fh)

    return logger


def find_free_port(start_port: int = 8080) -> int:
    """Finds an available local port starting from start_port."""
    for port in range(start_port, start_port + 50):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    return start_port


def wait_for_server_ready(url: str, timeout_sec: float = 10.0) -> bool:
    """Polls the local server until it responds or times out."""
    start_time = time.monotonic()
    check_url = f"{url}/api/v1/version"
    while time.monotonic() - start_time < timeout_sec:
        try:
            with urllib.request.urlopen(check_url, timeout=0.5) as response:
                if response.status == 200:
                    return True
        except Exception:
            time.sleep(0.1)
    return False


def find_app_browser() -> str | None:
    """Finds an installed browser supporting dedicated --app mode (Edge or Chrome)."""
    candidates = [
        # Microsoft Edge (Standard on Windows 10/11)
        Path(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"))
        / "Microsoft"
        / "Edge"
        / "Application"
        / "msedge.exe",
        Path(os.environ.get("ProgramFiles", "C:\\Program Files"))
        / "Microsoft"
        / "Edge"
        / "Application"
        / "msedge.exe",
        Path(os.environ.get("LOCALAPPDATA", ""))
        / "Microsoft"
        / "Edge"
        / "Application"
        / "msedge.exe",
        # Google Chrome
        Path(os.environ.get("ProgramFiles", "C:\\Program Files"))
        / "Google"
        / "Chrome"
        / "Application"
        / "chrome.exe",
        Path(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"))
        / "Google"
        / "Chrome"
        / "Application"
        / "chrome.exe",
        Path(os.environ.get("LOCALAPPDATA", ""))
        / "Google"
        / "Chrome"
        / "Application"
        / "chrome.exe",
    ]
    for p in candidates:
        if p.is_file():
            return str(p)
    return None


def run_studio() -> None:
    app_root = configure_drive_isolation()
    logger = setup_studio_logging(app_root)
    logger.info("=" * 60)
    logger.info("Starting QuantOS Studio %s", __version__)

    # Load environment variables
    load_env_file()

    port = find_free_port(8080)
    url = f"http://127.0.0.1:{port}"
    logger.info("Allocated port %d. Target URL: %s", port, url)

    # Import and configure FastAPI application
    from quant_system.server.app import app

    config = uvicorn.Config(
        app=app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
        access_log=False,
    )
    server = uvicorn.Server(config)

    # Run Uvicorn in background thread
    server_thread = threading.Thread(
        target=server.run,
        name="QuantOS-UvicornServer",
        daemon=True,
    )
    server_thread.start()
    logger.info("Background Uvicorn thread started.")

    # Wait for local server to become responsive
    if not wait_for_server_ready(url, timeout_sec=12.0):
        logger.error("Server failed to respond within timeout.")
        server.should_exit = True
        server_thread.join(timeout=3.0)
        sys.exit(1)

    logger.info("Server is healthy and ready on %s", url)

    # Launch UI Window
    # Strategy 1: Try pywebview if installed
    opened_via_webview = False
    try:
        import webview  # type: ignore[import-not-found]

        logger.info("Launching native window via pywebview WebView2 engine.")
        webview.create_window(
            title=f"QuantOS Studio — v{__version__}",
            url=url,
            width=1440,
            height=900,
            min_size=(1024, 700),
            text_select=True,
            confirm_close=False,
        )
        opened_via_webview = True
        webview.start()
        logger.info("WebView window closed by user.")
    except (ImportError, Exception) as exc:
        logger.info("pywebview not active (%s). Using Native App Window Shell.", exc)
        opened_via_webview = False

    # Strategy 2: Dedicated Windows App Mode Shell (Isolated Edge/Chrome window)
    if not opened_via_webview:
        browser_exe = find_app_browser()
        if browser_exe:
            profile_dir = str(app_root / "tmp" / "studio_profile")
            cmd = [
                browser_exe,
                f"--app={url}",
                "--window-size=1440,900",
                f"--user-data-dir={profile_dir}",
                "--no-first-run",
                "--no-default-browser-check",
            ]
            logger.info("Launching isolated App Window: %s", " ".join(cmd))
            try:
                proc = subprocess.Popen(cmd)
                logger.info(
                    "App Window process running (PID: %d). Waiting for user exit.", proc.pid
                )
                proc.wait()
                logger.info("App Window closed by user (Exit code: %s).", proc.returncode)
            except Exception as err:
                logger.error("Error launching App Window: %s", err)
        else:
            logger.warning("No App Mode browser found; falling back to default browser.")
            import webbrowser

            webbrowser.open(url)
            # In browser tab fallback, keep process alive until interrupt
            try:
                while True:
                    time.sleep(1)
            except (KeyboardInterrupt, SystemExit):
                pass

    # Clean Graceful Shutdown on Window Close
    logger.info("Initiating graceful server shutdown...")
    server.should_exit = True
    server_thread.join(timeout=4.0)
    logger.info("QuantOS Studio shutdown complete. Exiting.")
    sys.exit(0)


if __name__ == "__main__":
    multiprocessing.freeze_support()
    run_studio()
