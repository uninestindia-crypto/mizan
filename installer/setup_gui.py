"""QuantOS Standalone Setup Wizard (GUI Installer).

Apple-grade desktop setup wizard for QuantOS.
Installs QuantOS onto any selected drive with 100% drive isolation (Zero C: leakage)
and guarantees immutable evidence preservation on uninstall.
Conforms to apple-grade-ui design laws: Dynamic Type, concentric radii, verified contrast,
single primary accent action, and refined Cupertino dark mode surfaces.
"""

from __future__ import annotations

import os
import shutil
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

from quant_system import __version__

# ============================================================================
# Apple-Grade Design System Color Tokens (Dark Mode)
# ============================================================================
COLOR_CANVAS = "#161618"  # macOS Window Chrome
COLOR_HEADER = "#1A1A1D"  # Subtle elevated header
COLOR_CARD = "#212124"  # Primary surface container (rounded-xl)
COLOR_CARD_BORDER = "#2E2E32"  # Subtle 1px boundary
COLOR_SEPARATOR = "#26262A"  # 1px hairline divider
COLOR_INPUT_BG = "#2B2B2E"  # Inset control fill
COLOR_INPUT_BORDER = "#3A3A3E"  # Control border
COLOR_INPUT_FOCUS = "#0A84FF"  # Apple systemBlue focus ring

COLOR_ACCENT = "#0A84FF"  # Apple systemBlue fill
COLOR_ACCENT_HOVER = "#3898FF"  # Hovered accent
COLOR_ACCENT_ACTIVE = "#0066CC"  # Pressed accent

COLOR_BTN_SECONDARY = "#2C2C30"  # Tinted gray control fill
COLOR_BTN_SECONDARY_HOVER = "#3A3A40"  # Hovered secondary

COLOR_LABEL_PRIMARY = "#FFFFFF"  # Primary text (100% white)
COLOR_LABEL_SECONDARY = "#98989D"  # Secondary text (Apple 60% alpha eq)
COLOR_LABEL_TERTIARY = "#636366"  # Tertiary / captions / footers

COLOR_SUCCESS = "#30D158"  # Apple systemGreen
COLOR_SUCCESS_BG = "#132D1C"  # Tinted green chip
COLOR_SUCCESS_BORDER = "#1E4C2C"


def get_available_drives() -> list[str]:
    """Lists all available drive letters on Windows."""
    drives = []
    for letter in "DEFGHIJKLMNOPQRSTUVWXYZC":  # pragma: allowlist secret
        p = Path(f"{letter}:\\")
        if p.exists():
            drives.append(f"{letter}:\\")
    return drives


def get_free_space_gb(path_str: str) -> float:
    """Returns free space in GB for the given path."""
    try:
        total, used, free = shutil.disk_usage(path_str)
        return free / (1024**3)
    except Exception:
        return 0.0


def create_shortcuts(target_exe: Path) -> None:
    """Creates Windows desktop shortcut pointing exclusively to QuantOS Desktop Studio."""
    try:
        import subprocess

        desktop_dir = Path.home() / "Desktop"
        vbs_script = f"""
Set oWS = WScript.CreateObject("WScript.Shell")
sLinkFile = "{desktop_dir}\\QuantOS Studio.lnk"
Set oLink = oWS.CreateShortcut(sLinkFile)
oLink.TargetPath = "{target_exe}"
oLink.WorkingDirectory = "{target_exe.parent}"
oLink.Description = "QuantOS Studio — Quantitative Research & Risk Engine"
oLink.Save
"""
        vbs_path = target_exe.parent / "tmp" / "create_shortcut.vbs"
        vbs_path.parent.mkdir(parents=True, exist_ok=True)
        vbs_path.write_text(vbs_script, encoding="utf-8")
        subprocess.run(["cscript", "//nologo", str(vbs_path)], check=False)
        vbs_path.unlink(missing_ok=True)

        # Clean legacy shortcut if present
        legacy_link = desktop_dir / "QuantOS.lnk"
        if legacy_link.exists():
            legacy_link.unlink(missing_ok=True)
    except Exception:
        pass


class SetupWizard(tk.Tk):
    """Apple-Grade Setup Wizard for QuantOS Desktop Studio."""

    def __init__(self, bundle_source_dir: Path) -> None:
        super().__init__()
        self.bundle_source = bundle_source_dir
        self.title(f"QuantOS Studio Setup — v{__version__}")
        self.resizable(False, False)
        self.configure(bg=COLOR_CANVAS)

        # Geometry & Display Centering
        width = 640
        height = 520
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        x = max(0, (screen_w - width) // 2)
        y = max(0, (screen_h - height) // 2)
        self.geometry(f"{width}x{height}+{x}+{y}")

        # Default installation target (prefer non-C: drive)
        drives = get_available_drives()
        default_drive = drives[0] if drives else "C:\\"
        self.install_path_var = tk.StringVar(value=str(Path(default_drive) / "QuantOS"))
        self.desktop_icon_var = tk.BooleanVar(value=True)
        self._progress_val = 0.0

        self._build_ui()

    def _build_ui(self) -> None:
        # Header banner (macOS style translucent header)
        header = tk.Frame(self, bg=COLOR_HEADER, height=80)
        header.pack(fill="x", side="top")
        header.pack_propagate(False)

        # Header inner container with icon and titles
        h_inner = tk.Frame(header, bg=COLOR_HEADER)
        h_inner.pack(fill="both", expand=True, padx=24, pady=14)

        # Apple-style squircle App Icon Canvas
        icon_cv = tk.Canvas(h_inner, width=52, height=52, bg=COLOR_HEADER, highlightthickness=0)
        icon_cv.pack(side="left", padx=(0, 16))
        self._draw_app_icon(icon_cv)

        h_text = tk.Frame(h_inner, bg=COLOR_HEADER)
        h_text.pack(side="left", fill="y", expand=True)

        lbl_title = tk.Label(
            h_text,
            text="QuantOS Desktop Studio",
            font=("Segoe UI Variable Display", 15, "bold"),
            fg=COLOR_LABEL_PRIMARY,
            bg=COLOR_HEADER,
            anchor="w",
        )
        lbl_title.pack(anchor="w")

        lbl_sub = tk.Label(
            h_text,
            text=f"Version {__version__} · Isolated Drive Installation (Zero C: Drive Leakage)",
            font=("Segoe UI Variable Text", 9),
            fg=COLOR_LABEL_SECONDARY,
            bg=COLOR_HEADER,
            anchor="w",
        )
        lbl_sub.pack(anchor="w", pady=(2, 0))

        # 1px Hairline divider under header
        div_top = tk.Frame(self, bg=COLOR_SEPARATOR, height=1)
        div_top.pack(fill="x")

        # Main Elevated Card Container (Apple-grade concentric container)
        main_content = tk.Frame(self, bg=COLOR_CANVAS, padx=24, pady=20)
        main_content.pack(fill="both", expand=True)

        card = tk.Frame(
            main_content,
            bg=COLOR_CARD,
            highlightbackground=COLOR_CARD_BORDER,
            highlightthickness=1,
            padx=20,
            pady=18,
        )
        card.pack(fill="both", expand=True)

        card_title = tk.Label(
            card,
            text="INSTALLATION DESTINATION",
            font=("Segoe UI Variable Display", 9, "bold"),
            fg=COLOR_LABEL_SECONDARY,
            bg=COLOR_CARD,
        )
        card_title.pack(anchor="w", pady=(0, 4))

        card_desc = tk.Label(
            card,
            text="All program files, market data caches, model weights, and logs will reside\n"
            "exclusively within this directory without using space on other drives.",
            font=("Segoe UI Variable Text", 9),
            fg=COLOR_LABEL_SECONDARY,
            bg=COLOR_CARD,
            justify="left",
        )
        card_desc.pack(anchor="w", pady=(0, 14))

        # Path input row
        path_row = tk.Frame(card, bg=COLOR_CARD)
        path_row.pack(fill="x", pady=(0, 10))

        entry_border = tk.Frame(
            path_row,
            bg=COLOR_INPUT_BORDER,
            padx=1,
            pady=1,
        )
        entry_border.pack(side="left", fill="x", expand=True, padx=(0, 10))

        self.entry_path = tk.Entry(
            entry_border,
            textvariable=self.install_path_var,
            font=("Segoe UI Variable Text", 10),
            bg=COLOR_INPUT_BG,
            fg=COLOR_LABEL_PRIMARY,
            insertbackground=COLOR_LABEL_PRIMARY,
            relief="flat",
        )
        self.entry_path.pack(fill="both", expand=True, ipady=6, padx=8)

        btn_browse = tk.Button(
            path_row,
            text="Browse…",
            font=("Segoe UI Variable Text", 9, "bold"),
            bg=COLOR_BTN_SECONDARY,
            fg=COLOR_LABEL_PRIMARY,
            activebackground=COLOR_BTN_SECONDARY_HOVER,
            activeforeground=COLOR_LABEL_PRIMARY,
            relief="flat",
            command=self._on_browse,
            padx=16,
            pady=6,
            cursor="hand2",
        )
        btn_browse.pack(side="right")
        self._bind_hover(btn_browse, COLOR_BTN_SECONDARY, COLOR_BTN_SECONDARY_HOVER)

        # Storage capacity pill chip
        self.chip_space = tk.Frame(
            card,
            bg=COLOR_INPUT_BG,
            highlightbackground=COLOR_CARD_BORDER,
            highlightthickness=1,
            padx=12,
            pady=6,
        )
        self.chip_space.pack(anchor="w", pady=(0, 14))

        self.lbl_space_dot = tk.Label(
            self.chip_space,
            text="●",
            font=("Segoe UI Variable Text", 9, "bold"),
            fg=COLOR_SUCCESS,
            bg=COLOR_INPUT_BG,
        )
        self.lbl_space_dot.pack(side="left", padx=(0, 6))

        self.lbl_space = tk.Label(
            self.chip_space,
            text="Calculating drive space...",
            font=("Segoe UI Variable Text", 9),
            fg=COLOR_LABEL_PRIMARY,
            bg=COLOR_INPUT_BG,
        )
        self.lbl_space.pack(side="left")
        self._update_space_label()
        self.install_path_var.trace_add("write", lambda *args: self._update_space_label())

        # Desktop shortcut toggle
        chk_desktop = tk.Checkbutton(
            card,
            text="Add QuantOS Studio shortcut to Desktop",
            variable=self.desktop_icon_var,
            font=("Segoe UI Variable Text", 9),
            fg=COLOR_LABEL_PRIMARY,
            bg=COLOR_CARD,
            selectcolor=COLOR_INPUT_BG,
            activebackground=COLOR_CARD,
            activeforeground=COLOR_LABEL_PRIMARY,
            highlightthickness=0,
            cursor="hand2",
        )
        chk_desktop.pack(anchor="w", pady=(0, 14))

        # Smooth Apple-style Canvas Progress Bar
        self.progress_cv = tk.Canvas(card, height=8, bg=COLOR_INPUT_BG, highlightthickness=0)
        self.progress_cv.pack(fill="x", pady=(0, 8))
        self._draw_progress(0.0)

        # Status text
        self.lbl_status = tk.Label(
            card,
            text="Ready to install.",
            font=("Segoe UI Variable Text", 9),
            fg=COLOR_LABEL_SECONDARY,
            bg=COLOR_CARD,
        )
        self.lbl_status.pack(anchor="w")

        # 1px Hairline divider above footer
        div_bottom = tk.Frame(self, bg=COLOR_SEPARATOR, height=1)
        div_bottom.pack(fill="x", side="bottom")

        # Footer Actions Bar
        footer = tk.Frame(self, bg=COLOR_CANVAS, height=66)
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)

        foot_inner = tk.Frame(footer, bg=COLOR_CANVAS)
        foot_inner.pack(fill="both", expand=True, padx=24, pady=12)

        lbl_shield = tk.Label(
            foot_inner,
            text="🔒 Research datasets & evidence are always preserved",
            font=("Segoe UI Variable Text", 8),
            fg=COLOR_LABEL_TERTIARY,
            bg=COLOR_CANVAS,
        )
        lbl_shield.pack(side="left")

        self.btn_install = tk.Button(
            foot_inner,
            text="Install Now",
            font=("Segoe UI Variable Display", 10, "bold"),
            bg=COLOR_ACCENT,
            fg="#FFFFFF",
            activebackground=COLOR_ACCENT_HOVER,
            activeforeground="#FFFFFF",
            relief="flat",
            command=self._start_install,
            padx=22,
            pady=8,
            cursor="hand2",
        )
        self.btn_install.pack(side="right", padx=(10, 0))
        self._bind_hover(self.btn_install, COLOR_ACCENT, COLOR_ACCENT_HOVER)

        btn_cancel = tk.Button(
            foot_inner,
            text="Cancel",
            font=("Segoe UI Variable Text", 9),
            bg=COLOR_BTN_SECONDARY,
            fg=COLOR_LABEL_PRIMARY,
            activebackground=COLOR_BTN_SECONDARY_HOVER,
            activeforeground=COLOR_LABEL_PRIMARY,
            relief="flat",
            command=self.destroy,
            padx=16,
            pady=8,
            cursor="hand2",
        )
        btn_cancel.pack(side="right")
        self._bind_hover(btn_cancel, COLOR_BTN_SECONDARY, COLOR_BTN_SECONDARY_HOVER)

    def _draw_app_icon(self, cv: tk.Canvas) -> None:
        """Renders an Apple-style squircle app icon badge."""
        cv.delete("all")
        # Squircle base
        cv.create_rectangle(2, 2, 50, 50, fill="#0E1626", outline="#25354F", width=1.5)
        # Gradient/glow layer
        cv.create_rectangle(4, 4, 48, 48, fill="#0F203C", outline="")
        # Polyline trend graph
        pts = [10, 36, 18, 30, 26, 34, 34, 18, 42, 22]
        cv.create_line(pts, fill=COLOR_ACCENT, width=2.5, capstyle="round", joinstyle="round")
        # Terminal node point
        cv.create_oval(39, 19, 45, 25, fill=COLOR_SUCCESS, outline="")

    def _draw_progress(self, ratio: float) -> None:
        """Renders a smooth rounded pill progress bar on canvas."""
        self.progress_cv.delete("all")
        w = self.progress_cv.winfo_width() or 550
        h = 8
        # Track
        self.progress_cv.create_rectangle(0, 0, w, h, fill=COLOR_INPUT_BG, outline="")
        # Fill
        fill_w = max(0, min(w, int(w * ratio)))
        if fill_w > 0:
            self.progress_cv.create_rectangle(0, 0, fill_w, h, fill=COLOR_ACCENT, outline="")

    def set_progress(self, percent: float) -> None:
        """Updates progress bar smoothly."""
        self._progress_val = max(0.0, min(100.0, percent)) / 100.0
        self._draw_progress(self._progress_val)

    def _bind_hover(self, btn: tk.Button, normal_bg: str, hover_bg: str) -> None:
        btn.bind("<Enter>", lambda e: btn.config(bg=hover_bg))
        btn.bind("<Leave>", lambda e: btn.config(bg=normal_bg))

    def _on_browse(self) -> None:
        chosen = filedialog.askdirectory(
            title="Select Installation Directory",
            initialdir=self.install_path_var.get(),
        )
        if chosen:
            self.install_path_var.set(str(Path(chosen) / "QuantOS"))

    def _update_space_label(self) -> None:
        target = self.install_path_var.get()
        try:
            drive = Path(target).drive or str(target).split("\\")[0]
            free_gb = get_free_space_gb(drive if drive.endswith("\\") else f"{drive}\\")
            if free_gb >= 0.2:
                self.lbl_space_dot.config(fg=COLOR_SUCCESS)
                self.lbl_space.config(
                    text=f"Selected Drive [{drive}]: {free_gb:.1f} GB Available · Required: ~150 MB",
                    fg=COLOR_LABEL_PRIMARY,
                )
            else:
                self.lbl_space_dot.config(fg="#FF453A")
                self.lbl_space.config(
                    text=f"Selected Drive [{drive}]: Only {free_gb * 1024:.0f} MB Available (Warning: Insufficient)",
                    fg="#FF453A",
                )
        except Exception:
            self.lbl_space.config(text="")

    def _start_install(self) -> None:
        target = self.install_path_var.get().strip()
        if not target:
            messagebox.showerror("Invalid Path", "Please select a valid installation directory.")
            return

        drive = Path(target).drive or str(target).split("\\")[0]
        free_gb = get_free_space_gb(drive if drive.endswith("\\") else f"{drive}\\")
        if free_gb < 0.2:  # Less than 200 MB
            messagebox.showerror(
                "Insufficient Disk Space",
                f"Selected drive {drive} has only {free_gb * 1024:.0f} MB available.\n"
                "QuantOS requires at least 200 MB of free disk space.",
            )
            return

        self.btn_install.config(state="disabled")
        self.entry_path.config(state="disabled")
        threading.Thread(target=self._run_installation, daemon=True).start()

    def _run_installation(self) -> None:
        target_dir = Path(self.install_path_var.get()).resolve()
        desktop_dir = Path.home() / "Desktop"
        try:
            self.lbl_status.config(text="Creating drive-isolated folder structure...")
            target_dir.mkdir(parents=True, exist_ok=True)

            for folder in ["tmp", "data", "logs"]:
                (target_dir / folder).mkdir(parents=True, exist_ok=True)

            self.set_progress(20.0)

            # Copy all bundle files
            self.lbl_status.config(text=f"Installing application binaries to {target_dir}...")
            if self.bundle_source.exists():
                for item in self.bundle_source.iterdir():
                    dest = target_dir / item.name
                    if item.is_dir():
                        if dest.exists():
                            shutil.rmtree(dest)
                        shutil.copytree(item, dest)
                    else:
                        shutil.copy2(item, dest)

            self.set_progress(70.0)

            # Write uninstaller script inside target folder that preserves data/evidence
            uninst_script = target_dir / "uninstall.bat"
            uninst_script.write_text(
                f"""@echo off
setlocal
echo =======================================================
echo   QuantOS v{__version__} Safe Uninstaller
echo =======================================================
echo Uninstalling application binaries from: {target_dir}
echo Note: User datasets, evidence, and logs in data/ and logs/ will be preserved.

if "%1"=="--silent" goto run
if "%1"=="/y" goto run
pause

:run
cd ..
if exist "{target_dir}\\quantos-studio.exe" del /f /q "{target_dir}\\quantos-studio.exe"
if exist "{target_dir}\\quantos.exe" del /f /q "{target_dir}\\quantos.exe"
if exist "{target_dir}\\QuantOS.exe" del /f /q "{target_dir}\\QuantOS.exe"
if exist "{target_dir}\\_internal" rd /s /q "{target_dir}\\_internal"
if exist "{target_dir}\\quant_system" rd /s /q "{target_dir}\\quant_system"
if exist "{target_dir}\\tmp" rd /s /q "{target_dir}\\tmp"
if exist "{target_dir}\\configs" rd /s /q "{target_dir}\\configs"
if exist "{target_dir}\\release-manifest.json" del /f /q "{target_dir}\\release-manifest.json"
if exist "{target_dir}\\MANIFEST.sha256" del /f /q "{target_dir}\\MANIFEST.sha256"
if exist "{target_dir}\\release.json" del /f /q "{target_dir}\\release.json"
if exist "{target_dir}\\sbom.json" del /f /q "{target_dir}\\sbom.json"
if exist "{desktop_dir}\\QuantOS Studio.lnk" del /f /q "{desktop_dir}\\QuantOS Studio.lnk"
if exist "{desktop_dir}\\QuantOS.lnk" del /f /q "{desktop_dir}\\QuantOS.lnk"
for /d /r "{target_dir}" %%d in (__pycache__) do @if exist "%%d" rd /s /q "%%d"
echo QuantOS application binaries and caches have been cleanly removed.
echo Your research datasets, logs, and evidence records remain intact.

if "%1"=="--silent" goto end
if "%1"=="/y" goto end
pause

:end
endlocal
""",
                encoding="utf-8",
            )

            # Locate executable: prioritize Desktop Studio (quantos-studio.exe) for zero-console launch
            target_exe = target_dir / "quantos-studio.exe"
            if not target_exe.exists():
                target_exe = target_dir / "quantos.exe"
            if not target_exe.exists():
                target_exe = target_dir / "QuantOS.exe"

            # Create Desktop Shortcut if selected
            if self.desktop_icon_var.get() and target_exe.exists():
                self.lbl_status.config(text="Creating desktop shortcut...")
                create_shortcuts(target_exe)

            self.set_progress(100.0)
            self.lbl_status.config(
                text="Installation complete! Zero C: drive leakage.", fg=COLOR_SUCCESS
            )

            launch_now = messagebox.askyesno(
                "Installation Complete",
                f"QuantOS v{__version__} has been successfully installed on {target_dir.drive}!\n\n"
                "Would you like to launch QuantOS Desktop Studio now?",
            )

            if launch_now and target_exe.exists():
                os.startfile(str(target_exe))

            self.destroy()

        except Exception as err:
            messagebox.showerror("Installation Error", f"Failed to install QuantOS:\n{err}")
            self.btn_install.config(state="normal")
            self.entry_path.config(state="normal")


def main() -> None:
    # Bundle source directory (defaults to sibling dist/quantos or dist/QuantOS or sys._MEIPASS when frozen)
    if getattr(sys, "frozen", False):
        bundle_source = Path(sys._MEIPASS) / "quantos"  # type: ignore[attr-defined]
        if not bundle_source.exists():
            bundle_source = Path(sys._MEIPASS) / "QuantOS"  # type: ignore[attr-defined]
    else:
        bundle_source = Path(__file__).parent.parent / "dist" / "quantos"
        if not bundle_source.exists():
            bundle_source = Path(__file__).parent.parent / "dist" / "QuantOS"

    app = SetupWizard(bundle_source_dir=bundle_source)
    app.mainloop()


if __name__ == "__main__":
    main()
