"""QuantOS Visual Diagnostics Readiness Dialog.

Apple-grade dark UI presenting green checkmark badges for passing gates,
hardware discovery summary, and a 1-click trigger to launch QuantOS.
"""

from __future__ import annotations

import os
import sys
import tkinter as tk
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from preflight_diagnostics import PreFlightDiagnosticsReport


class DiagnosticsReadinessDialog(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Tk | None,
        report: PreFlightDiagnosticsReport,
        target_exe: Path,
    ) -> None:
        if parent is None:
            self.root = tk.Tk()
            super().__init__(self.root)
            self.root.withdraw()
        else:
            self.root = parent
            super().__init__(parent)

        self.report = report
        self.target_exe = target_exe

        self.title("QuantOS System Readiness & Pre-Flight Diagnostics")
        self.geometry("640x520")
        self.resizable(False, False)
        self.configure(bg="#1E1E1E")

        self._build_ui()

    def _build_ui(self) -> None:
        # Header banner
        header = tk.Frame(self, bg="#0D0D0D", height=75)
        header.pack(fill="x", side="top")

        lbl_title = tk.Label(
            header,
            text="QuantOS System Readiness Certified",
            font=("Segoe UI", 14, "bold"),
            fg="#FFFFFF",
            bg="#0D0D0D",
        )
        lbl_title.pack(anchor="w", padx=20, pady=(12, 2))

        status_text = (
            "All pre-flight system integrity checks passed successfully (0 errors)."
            if self.report.all_passed
            else "One or more pre-flight checks failed. Review details below."
        )
        status_color = "#34C759" if self.report.all_passed else "#FF453A"
        lbl_sub = tk.Label(
            header,
            text=status_text,
            font=("Segoe UI", 9),
            fg=status_color,
            bg="#0D0D0D",
        )
        lbl_sub.pack(anchor="w", padx=20)

        # Body Cards
        cards_frame = tk.Frame(self, bg="#1E1E1E", padx=20, pady=15)
        cards_frame.pack(fill="both", expand=True)

        for gate in self.report.gates:
            row = tk.Frame(cards_frame, bg="#2A2A2A", padx=12, pady=9)
            row.pack(fill="x", pady=4)

            badge_fg = (
                "#34C759"
                if gate.status == "PASS"
                else "#FF9F0A"
                if gate.status == "INFO"
                else "#FF453A"
            )
            badge_icon = "✔" if gate.status == "PASS" else "★" if gate.status == "INFO" else "✖"

            left = tk.Frame(row, bg="#2A2A2A")
            left.pack(side="left", fill="both", expand=True)

            tk.Label(
                left,
                text=f"{badge_icon}  {gate.title}",
                font=("Segoe UI", 10, "bold"),
                fg="#FFFFFF",
                bg="#2A2A2A",
            ).pack(anchor="w")

            tk.Label(
                left,
                text=gate.detail,
                font=("Segoe UI", 8),
                fg="#A1A1A6",
                bg="#2A2A2A",
                wraplength=480,
                justify="left",
            ).pack(anchor="w", pady=(2, 0))

            tk.Label(
                row,
                text=f"[{gate.status}]",
                font=("Segoe UI", 9, "bold"),
                fg=badge_fg,
                bg="#2A2A2A",
            ).pack(side="right", padx=(10, 0))

        # Footer
        footer = tk.Frame(self, bg="#141414", height=60)
        footer.pack(fill="x", side="bottom")

        btn_launch = tk.Button(
            footer,
            text="Launch QuantOS",
            font=("Segoe UI", 10, "bold"),
            bg="#0071E3",
            fg="#FFFFFF",
            activebackground="#0077ED",
            relief="flat",
            command=self._on_launch,
            padx=20,
            pady=6,
        )
        btn_launch.pack(side="right", padx=20, pady=12)

        btn_close = tk.Button(
            footer,
            text="Close",
            font=("Segoe UI", 9),
            bg="#2C2C2E",
            fg="#FFFFFF",
            relief="flat",
            command=self._on_close,
            padx=16,
            pady=6,
        )
        btn_close.pack(side="right", padx=10, pady=12)

    def _on_launch(self) -> None:
        if self.target_exe.exists():
            os.startfile(str(self.target_exe))
        self._on_close()

    def _on_close(self) -> None:
        self.destroy()
        if self.root != self:
            self.root.destroy()


def show_diagnostics_ui(report: PreFlightDiagnosticsReport, target_exe: Path) -> None:
    """Convenience helper to display the diagnostics readiness window."""
    root = tk.Tk()
    root.withdraw()
    dlg = DiagnosticsReadinessDialog(root, report, target_exe)
    dlg.mainloop()
