"""The QuantOS desktop window: a native Windows window around the local interface.

The engine serves the interface on ``127.0.0.1``; this module shows it in its own window using
Windows' WebView2 engine (through pywebview), so QuantOS behaves like an installed program:
its own taskbar entry and icon (the executable's), no address bar, no dependence on which browser
the user prefers, and one instance at a time.

Everything here is best effort. ``run_native_window`` returns ``False`` when a native window cannot
be shown (pywebview or the WebView2 runtime missing), and the caller falls back to an Edge/Chrome
app window. It never raises for those reasons.
"""

from __future__ import annotations

import ctypes
import logging
import os
import sys
import threading
import time
from collections.abc import Callable
from pathlib import Path

DEFAULT_TITLE = "QuantOS"
MUTEX_NAME = "Local\\QuantOS.Desktop.SingleInstance"
APP_USER_MODEL_ID = "QuantOS.Desktop.Studio.2.0"

_ERROR_ALREADY_EXISTS = 183
_SW_RESTORE = 9

# Background shown for the instant before the page paints, so a dark system never flashes white.
LIGHT_BACKGROUND = "#f4f6fa"
DARK_BACKGROUND = "#080d17"

# Kept alive for the life of the process: closing the handle would release the single-instance lock.
_mutex_handle: int | None = None


def ensure_app_user_model_id(app_id: str = APP_USER_MODEL_ID) -> None:
    """Set the Windows Application User Model ID for dedicated taskbar grouping and icon display."""
    if sys.platform == "win32":
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(app_id)
        except Exception:
            pass


# Ensure AppUserModelID is registered immediately upon import
ensure_app_user_model_id()


def system_prefers_dark() -> bool:
    """Whether Windows apps are set to dark mode (False when it cannot be determined)."""
    if sys.platform != "win32":
        return False
    try:
        import winreg

        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
        ) as key:
            value, _kind = winreg.QueryValueEx(key, "AppsUseLightTheme")
        return int(value) == 0
    except OSError:
        return False


def webview2_runtime_version() -> str | None:
    """Installed WebView2 Evergreen runtime version, or None when it is not installed."""
    if sys.platform != "win32":
        return None
    try:
        import winreg
    except ImportError:
        return None
    guid = "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
    locations = (
        (winreg.HKEY_LOCAL_MACHINE, rf"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{guid}"),
        (winreg.HKEY_LOCAL_MACHINE, rf"SOFTWARE\Microsoft\EdgeUpdate\Clients\{guid}"),
        (winreg.HKEY_CURRENT_USER, rf"Software\Microsoft\EdgeUpdate\Clients\{guid}"),
    )
    for hive, path in locations:
        try:
            with winreg.OpenKey(hive, path) as key:
                version, _kind = winreg.QueryValueEx(key, "pv")
        except OSError:
            continue
        text = str(version).strip()
        if text and text != "0.0.0.0":
            return text
    return None


def acquire_single_instance(name: str = MUTEX_NAME) -> bool:
    """Take the per-user single-instance lock. False means another QuantOS window owns it."""
    global _mutex_handle
    if sys.platform != "win32":
        return True
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateMutexW.restype = ctypes.c_void_p
    kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_wchar_p]
    handle = kernel32.CreateMutexW(None, False, name)
    already_running = ctypes.get_last_error() == _ERROR_ALREADY_EXISTS
    if already_running:
        if handle:
            kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
            kernel32.CloseHandle(handle)
        return False
    _mutex_handle = int(handle) if handle else None
    return True


def release_single_instance() -> None:
    """Explicitly release and close the single-instance mutex handle.

    Releasing the mutex as soon as window destruction begins allows subsequent
    user launches to acquire the lock immediately without waiting for background
    teardown.
    """
    global _mutex_handle
    if sys.platform != "win32" or _mutex_handle is None:
        return
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel32.CloseHandle(_mutex_handle)
    except Exception:
        pass
    finally:
        _mutex_handle = None


def hard_exit(code: int = 0) -> None:
    """Terminate the process unconditionally without deadlocking in DLL detach routines.

    On Windows, ExitProcess (called by os._exit) invokes DLL_PROCESS_DETACH on all loaded
    DLLs while holding the Windows loader lock. In GUI runtimes using WebView2 and pywebview,
    COM threads, RPC channels, and CLR workers frequently deadlock in DllMain / DLL_PROCESS_DETACH,
    leaving an orphaned zombie process with 1 stuck thread.
    TerminateProcess bypasses DLL_PROCESS_DETACH and guarantees immediate kernel cleanup.
    """
    release_single_instance()
    if sys.platform == "win32":
        try:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.TerminateProcess(kernel32.GetCurrentProcess(), code)
        except Exception:
            pass
    os._exit(code)


def focus_existing_window(title: str = DEFAULT_TITLE) -> bool:
    """Bring the already-running QuantOS window to the front. Returns whether one was found."""
    if sys.platform != "win32":
        return False
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.FindWindowW.restype = ctypes.c_void_p
    user32.FindWindowW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p]
    hwnd = user32.FindWindowW(None, title)

    if not hwnd:
        matched_hwnd = None
        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

        def _enum_cb(h: ctypes.c_void_p, _lparam: ctypes.c_void_p) -> bool:
            nonlocal matched_hwnd
            if user32.IsWindowVisible(h):
                length = user32.GetWindowTextLengthW(h)
                if length > 0:
                    buf = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(h, buf, length + 1)
                    if title.lower() in buf.value.lower():
                        matched_hwnd = h
                        return False
            return True

        user32.EnumWindows(WNDENUMPROC(_enum_cb), None)
        hwnd = matched_hwnd

    if not hwnd:
        return False

    user32.ShowWindow.argtypes = [ctypes.c_void_p, ctypes.c_int]
    user32.SetForegroundWindow.argtypes = [ctypes.c_void_p]
    user32.BringWindowToTop.argtypes = [ctypes.c_void_p]
    user32.ShowWindow(hwnd, _SW_RESTORE)
    user32.BringWindowToTop(hwnd)
    user32.SetForegroundWindow(hwnd)
    return True


def cleanup_zombie_instances(process_names: tuple[str, ...] = ("quantos-studio.exe",)) -> int:
    """Terminates orphaned headless instances of QuantOS Studio.

    Only targets processes with matching names whose PID differs from the current process.
    Uses process tree termination and synchronously waits for kernel process handles to close.
    Returns the number of processes terminated.
    """
    if sys.platform != "win32":
        return 0
    import subprocess

    current_pid = os.getpid()
    cleaned = 0
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    synchronize = 0x00100000

    for name in process_names:
        try:
            cmd = f'tasklist /FI "IMAGENAME eq {name}" /FO CSV /NH'
            out = subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.DEVNULL)
            for line in out.strip().splitlines():
                line = line.strip()
                if not line or "INFO: No tasks" in line:
                    continue
                parts = [p.strip('"') for p in line.split('","')]
                if len(parts) >= 2 and parts[0].lower() == name.lower():
                    try:
                        pid = int(parts[1])
                        if pid != current_pid:
                            # Terminate process tree (/T) to ensure child WebView2 processes are cleaned
                            subprocess.run(
                                f"taskkill /F /T /PID {pid}",
                                shell=True,
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL,
                            )
                            # Wait for kernel to finalize process termination
                            try:
                                h_proc = kernel32.OpenProcess(synchronize, False, pid)
                                if h_proc:
                                    kernel32.WaitForSingleObject(h_proc, 1500)
                                    kernel32.CloseHandle(h_proc)
                            except Exception:
                                pass
                            cleaned += 1
                    except (ValueError, OSError):
                        pass
        except Exception:
            pass
    return cleaned


def diagnostics_port(environ: dict[str, str] | None = None) -> int | None:
    """The WebView2 remote-debugging port requested through ``QUANTOS_DEBUG_PORT``, if valid.

    Off by default. Accepts only a whole number from 1024 to 65535; anything else is ignored.
    """
    raw = (environ if environ is not None else os.environ).get("QUANTOS_DEBUG_PORT", "").strip()
    if not raw.isdigit():
        return None
    port = int(raw)
    return port if 1024 <= port <= 65535 else None


def fit_to_screen(
    screen_size: tuple[int, int] | None,
    desired: tuple[int, int] = (1440, 900),
    minimum: tuple[int, int] = (1024, 700),
) -> tuple[tuple[int, int], tuple[int, int]]:
    """Window size and minimum size that fit a display (logical pixels).

    A laptop at 150% scaling reports 1280x800, so a fixed 1440x900 window would run off the screen.
    """
    if screen_size is None:
        return desired, minimum
    screen_width, screen_height = screen_size
    width = min(desired[0], int(screen_width * 0.92))
    height = min(desired[1], int(screen_height * 0.9))
    return (width, height), (min(minimum[0], width), min(minimum[1], height))


def default_icon_path() -> str | None:
    """Finds the QuantOS icon file across development and installed directories."""
    candidates = [
        Path.cwd() / "assets" / "quantos.ico",
        Path.cwd() / "installer" / "assets" / "quantos.ico",
        Path(__file__).resolve().parents[3] / "assets" / "quantos.ico",
        Path(__file__).resolve().parents[3] / "installer" / "assets" / "quantos.ico",
        Path(sys.executable).parent / "assets" / "quantos.ico",
        Path(sys.executable).parent / "installer" / "assets" / "quantos.ico",
    ]
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        candidates.insert(0, Path(sys._MEIPASS) / "assets" / "quantos.ico")
    for p in candidates:
        if p.is_file():
            return str(p.resolve())
    return None


def run_native_window(
    url: str,
    *,
    title: str = DEFAULT_TITLE,
    icon: str | None = None,
    storage_path: str | None = None,
    logger: logging.Logger | None = None,
    width: int = 1440,
    height: int = 900,
    min_size: tuple[int, int] = (1024, 700),
    start: Callable[..., object] | None = None,
) -> bool:
    """Show ``url`` in a native window and block until it is closed.

    Returns True if a native window was shown and then closed by the user, False if none could be
    shown (the caller should fall back). ``start`` is injectable for tests.
    """
    ensure_app_user_model_id()
    log = logger or logging.getLogger("quantos.shell")
    try:
        import webview
    except ImportError as err:
        log.info("pywebview is not installed (%s); no native window.", err)
        return False

    if webview2_runtime_version() is None:
        log.info("The WebView2 runtime is not installed; no native window.")
        return False

    debug_port = diagnostics_port()
    if debug_port is not None:
        # Opt-in only, for automated tests and support: exposes the window to local tools.
        webview.settings["REMOTE_DEBUGGING_PORT"] = debug_port
        log.warning("Diagnostics port %d is open on localhost (QUANTOS_DEBUG_PORT).", debug_port)

    try:
        try:
            primary = webview.screens[0]
            screen_size: tuple[int, int] | None = (int(primary.width), int(primary.height))
        except Exception:
            screen_size = None
        (width, height), min_size = fit_to_screen(screen_size, (width, height), min_size)
        win = webview.create_window(
            title=title,
            url=url,
            width=width,
            height=height,
            min_size=min_size,
            background_color=DARK_BACKGROUND if system_prefers_dark() else LIGHT_BACKGROUND,
            text_select=True,
            confirm_close=False,
        )

        if win is not None and hasattr(win, "events") and hasattr(win.events, "closed"):

            def _on_window_closed() -> None:
                log.info("Native window closed event received.")
                release_single_instance()

                def _watchdog() -> None:
                    time.sleep(2.0)
                    log.warning(
                        "GUI loop did not exit within 2.0s after window close; forcing process exit."
                    )
                    hard_exit(0)

                threading.Thread(
                    target=_watchdog, name="QuantOS-CloseWatchdog", daemon=True
                ).start()

            win.events.closed += _on_window_closed

        launcher = start or webview.start
        resolved_icon = icon or default_icon_path()
        storage = storage_path or os.environ.get("WEBVIEW2_USER_DATA_FOLDER")

        if resolved_icon and os.path.isfile(resolved_icon):
            log.info("Applying QuantOS icon: %s", resolved_icon)
            launcher(
                gui="edgechromium",
                private_mode=False,
                storage_path=storage,
                debug=False,
                icon=resolved_icon,
            )
        else:
            launcher(
                gui="edgechromium",
                private_mode=False,
                storage_path=storage,
                debug=False,
            )
    except Exception as err:
        log.warning("Native window failed (%s: %s); falling back.", type(err).__name__, err)
        return False
    log.info("Native window closed by the user.")
    release_single_instance()
    return True


def data_dir_hint() -> Path | None:
    """Where WebView2 keeps its profile, if the launcher configured it."""
    value = os.environ.get("WEBVIEW2_USER_DATA_FOLDER")
    return Path(value) if value else None
