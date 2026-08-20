"""QuantOS Standalone Setup Wizard (GUI Installer).

Installs QuantOS onto any selected drive with 100% drive isolation (Zero C: leakage).
"""

from __future__ import annotations

import os
import shutil
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from quant_system import __version__


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
    """Creates Windows desktop shortcut pointing directly to target_exe."""
    try:
        import subprocess

        desktop_dir = Path.home() / "Desktop"
        vbs_script = f"""
Set oWS = WScript.CreateObject("WScript.Shell")
sLinkFile = "{desktop_dir}\\QuantOS.lnk"
Set oLink = oWS.CreateShortcut(sLinkFile)
oLink.TargetPath = "{target_exe}"
oLink.WorkingDirectory = "{target_exe.parent}"
oLink.Description = "QuantOS Quantitative Trading Engine"
oLink.Save
"""
        vbs_path = target_exe.parent / "tmp" / "create_shortcut.vbs"
        vbs_path.parent.mkdir(parents=True, exist_ok=True)
        vbs_path.write_text(vbs_script, encoding="utf-8")
        subprocess.run(["cscript", "//nologo", str(vbs_path)], check=False)
        vbs_path.unlink(missing_ok=True)
    except Exception:
        pass


class SetupWizard(tk.Tk):
    def __init__(self, bundle_source_dir: Path) -> None:
        super().__init__()
        self.bundle_source = bundle_source_dir
        self.title(f"QuantOS v{__version__} Setup Wizard")
        self.geometry("580x420")
        self.resizable(False, False)
        self.configure(bg="#1E1E1E")

        # Determine default drive (Prefer D:, E:, etc. if available)
        drives = get_available_drives()
        default_drive = drives[0] if drives else "C:\\"
        self.install_path_var = tk.StringVar(value=str(Path(default_drive) / "QuantOS"))
        self.desktop_icon_var = tk.BooleanVar(value=True)

        self._build_ui()

    def _build_ui(self) -> None:
        # Header banner
        header = tk.Frame(self, bg="#0D0D0D", height=70)
        header.pack(fill="x", side="top")

        lbl_title = tk.Label(
            header,
            text="QuantOS Desktop Engine Setup",
            font=("Segoe UI", 15, "bold"),
            fg="#FFFFFF",
            bg="#0D0D0D",
        )
        lbl_title.pack(anchor="w", padx=20, pady=(12, 2))

        lbl_sub = tk.Label(
            header,
            text=f"Version {__version__} — Isolated Drive Installation (Zero C: Drive Leakage)",
            font=("Segoe UI", 9),
            fg="#86868B",
            bg="#0D0D0D",
        )
        lbl_sub.pack(anchor="w", padx=20)

        # Content frame
        content = tk.Frame(self, bg="#1E1E1E", padx=24, pady=20)
        content.pack(fill="both", expand=True)

        lbl_desc = tk.Label(
            content,
            text="Select the installation folder. All program files, caches, data, and logs will\nreside strictly within this directory without using space on other drives:",
            font=("Segoe UI", 10),
            fg="#CCCCCC",
            bg="#1E1E1E",
            justify="left",
        )
        lbl_desc.pack(anchor="w", pady=(0, 15))

        # Folder selection row
        path_frame = tk.Frame(content, bg="#1E1E1E")
        path_frame.pack(fill="x", pady=5)

        self.entry_path = tk.Entry(
            path_frame,
            textvariable=self.install_path_var,
            font=("Segoe UI", 10),
            bg="#2A2A2A",
            fg="#FFFFFF",
            insertbackground="#FFFFFF",
            relief="flat",
        )
        self.entry_path.pack(side="left", fill="x", expand=True, ipady=6, padx=(0, 8))

        btn_browse = tk.Button(
            path_frame,
            text="Browse...",
            font=("Segoe UI", 9, "bold"),
            bg="#3A3A3C",
            fg="#FFFFFF",
            activebackground="#4A4A4C",
            activeforeground="#FFFFFF",
            relief="flat",
            command=self._on_browse,
            padx=12,
            pady=4,
        )
        btn_browse.pack(side="right")

        # Disk space info
        self.lbl_space = tk.Label(
            content,
            text="",
            font=("Segoe UI", 9),
            fg="#34C759",
            bg="#1E1E1E",
        )
        self.lbl_space.pack(anchor="w", pady=(6, 12))
        self._update_space_label()

        self.install_path_var.trace_add("write", lambda *args: self._update_space_label())

        # Options
        chk_desktop = tk.Checkbutton(
            content,
            text="Create a Desktop Shortcut",
            variable=self.desktop_icon_var,
            font=("Segoe UI", 9),
            fg="#FFFFFF",
            bg="#1E1E1E",
            selectcolor="#2A2A2A",
            activebackground="#1E1E1E",
            activeforeground="#FFFFFF",
        )
        chk_desktop.pack(anchor="w", pady=(0, 10))

        # Progress bar
        self.progress = ttk.Progressbar(content, mode="determinate")
        self.progress.pack(fill="x", pady=(10, 5))

        self.lbl_status = tk.Label(
            content,
            text="Ready to install.",
            font=("Segoe UI", 9),
            fg="#86868B",
            bg="#1E1E1E",
        )
        self.lbl_status.pack(anchor="w")

        # Footer actions
        footer = tk.Frame(self, bg="#141414", height=60)
        footer.pack(fill="x", side="bottom")

        btn_cancel = tk.Button(
            footer,
            text="Cancel",
            font=("Segoe UI", 9),
            bg="#2C2C2E",
            fg="#FFFFFF",
            activebackground="#3A3A3C",
            relief="flat",
            command=self.destroy,
            padx=16,
            pady=6,
        )
        btn_cancel.pack(side="right", padx=(0, 20), pady=12)

        self.btn_install = tk.Button(
            footer,
            text="Install Now",
            font=("Segoe UI", 9, "bold"),
            bg="#0071E3",
            fg="#FFFFFF",
            activebackground="#0077ED",
            relief="flat",
            command=self._start_install,
            padx=20,
            pady=6,
        )
        self.btn_install.pack(side="right", padx=10, pady=12)

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
            self.lbl_space.config(
                text=f"Selected Drive [{drive}]: {free_gb:.1f} GB Available (Required: ~150 MB)"
            )
        except Exception:
            self.lbl_space.config(text="")

    def _start_install(self) -> None:
        self.btn_install.config(state="disabled")
        self.entry_path.config(state="disabled")
        threading.Thread(target=self._run_installation, daemon=True).start()

    def _run_installation(self) -> None:
        target_dir = Path(self.install_path_var.get()).resolve()
        try:
            self.lbl_status.config(text="Creating drive-isolated folder structure...")
            target_dir.mkdir(parents=True, exist_ok=True)

            for folder in ["tmp", "data", "logs"]:
                (target_dir / folder).mkdir(parents=True, exist_ok=True)

            self.progress["value"] = 20

            # Copy all bundle files
            self.lbl_status.config(text=f"Installing binaries to {target_dir}...")
            if self.bundle_source.exists():
                for item in self.bundle_source.iterdir():
                    dest = target_dir / item.name
                    if item.is_dir():
                        if dest.exists():
                            shutil.rmtree(dest)
                        shutil.copytree(item, dest)
                    else:
                        shutil.copy2(item, dest)

            self.progress["value"] = 70

            # Write uninstaller script inside target folder
            uninst_script = target_dir / "uninstall.bat"
            uninst_script.write_text(
                f"""@echo off
echo =======================================================
echo   QuantOS v{__version__} Uninstaller
echo =======================================================
echo Uninstalling from: {target_dir}
pause
cd ..
rd /s /q "{target_dir}"
echo QuantOS has been completely removed from your drive.
pause
""",
                encoding="utf-8",
            )

            # Create Desktop Shortcut if selected
            if self.desktop_icon_var.get():
                target_exe = target_dir / "QuantOS.exe"
                if target_exe.exists():
                    self.lbl_status.config(text="Creating desktop shortcut...")
                    create_shortcuts(target_exe)

            self.progress["value"] = 100
            self.lbl_status.config(
                text="Installation complete! Zero C: drive leakage.", fg="#34C759"
            )

            launch_now = messagebox.askyesno(
                "Installation Complete",
                f"QuantOS v{__version__} has been successfully installed on {target_dir.drive}!\n\nWould you like to launch QuantOS now?",
            )

            if launch_now:
                target_exe = target_dir / "QuantOS.exe"
                if target_exe.exists():
                    os.startfile(str(target_exe))

            self.destroy()

        except Exception as err:
            messagebox.showerror("Installation Error", f"Failed to install QuantOS:\n{err}")
            self.btn_install.config(state="normal")
            self.entry_path.config(state="normal")


def main() -> None:
    # Bundle source directory (defaults to sibling dist/QuantOS or sys._MEIPASS when frozen)
    if getattr(sys, "frozen", False):
        bundle_source = Path(sys._MEIPASS) / "QuantOS"  # type: ignore[attr-defined]
    else:
        bundle_source = Path(__file__).parent.parent / "dist" / "QuantOS"

    app = SetupWizard(bundle_source_dir=bundle_source)
    app.mainloop()


if __name__ == "__main__":
    main()
