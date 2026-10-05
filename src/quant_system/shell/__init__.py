"""Desktop shell: the native window that hosts the QuantOS interface."""

from __future__ import annotations

from quant_system.shell.native_window import (
    acquire_single_instance,
    cleanup_zombie_instances,
    focus_existing_window,
    run_native_window,
    system_prefers_dark,
    webview2_runtime_version,
)

__all__ = [
    "acquire_single_instance",
    "cleanup_zombie_instances",
    "focus_existing_window",
    "run_native_window",
    "system_prefers_dark",
    "webview2_runtime_version",
]
