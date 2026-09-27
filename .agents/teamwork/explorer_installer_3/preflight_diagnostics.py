"""QuantOS Standalone Pre-Flight Diagnostics Engine.

Verifies loopback socket binding, Decimal double-entry ledger invariants,
folder write/read permissions, and hardware capabilities (Qualcomm Hexagon NPU,
DirectML/DirectX GPU, and CPU AVX2 instructions).
"""

from __future__ import annotations

import ctypes
import json
import logging
import os
import platform
import socket
import subprocess
import sys
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

__all__ = [
    "DiagnosticGateResult",
    "PreFlightDiagnosticsReport",
    "run_preflight_diagnostics",
    "write_diagnostics_log",
]


@dataclass(frozen=True)
class DiagnosticGateResult:
    gate_name: str
    status: str  # "PASS", "FAIL", "INFO", "WARN"
    title: str
    detail: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PreFlightDiagnosticsReport:
    timestamp_utc: str
    install_root: str
    quantos_version: str
    architecture: str
    all_passed: bool
    gates: list[DiagnosticGateResult]
    hardware: dict[str, Any]


def check_loopback_socket(target_port: int = 8080) -> DiagnosticGateResult:
    """Gate 1: Tests local loopback socket binding on 127.0.0.1 and checks port availability."""
    meta: dict[str, Any] = {}
    try:
        # Step 1: Bind and ping-pong on loopback
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind(("127.0.0.1", 0))
            server.listen(1)
            bound_port = server.getsockname()[1]
            meta["bound_port"] = bound_port

            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:
                client.settimeout(2.0)
                client.connect(("127.0.0.1", bound_port))
                conn, _ = server.accept()
                with conn:
                    client.sendall(b"QUANTOS_SYN")
                    data = conn.recv(32)
                    if data != b"QUANTOS_SYN":
                        return DiagnosticGateResult(
                            gate_name="socket_loopback",
                            status="FAIL",
                            title="Local Socket Loopback (127.0.0.1)",
                            detail="Data corrupted during loopback transmission.",
                            metadata=meta,
                        )
                    conn.sendall(b"QUANTOS_ACK")
                    ack = client.recv(32)
                    if ack != b"QUANTOS_ACK":
                        return DiagnosticGateResult(
                            gate_name="socket_loopback",
                            status="FAIL",
                            title="Local Socket Loopback (127.0.0.1)",
                            detail="Loopback acknowledgment failed.",
                            metadata=meta,
                        )

        # Step 2: Target port check (e.g. 8080)
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as port_check:
            is_busy = port_check.connect_ex(("127.0.0.1", target_port)) == 0
            meta[f"port_{target_port}_available"] = not is_busy

        port_str = f"Port {target_port} available" if not is_busy else f"Port {target_port} busy (engine will auto-shift)"
        return DiagnosticGateResult(
            gate_name="socket_loopback",
            status="PASS",
            title="Local Socket Loopback (127.0.0.1)",
            detail=f"Loopback binding verified on 127.0.0.1. {port_str}.",
            metadata=meta,
        )

    except Exception as exc:
        return DiagnosticGateResult(
            gate_name="socket_loopback",
            status="FAIL",
            title="Local Socket Loopback (127.0.0.1)",
            detail=f"Failed to bind or connect to 127.0.0.1: {exc}",
            metadata={"error": str(exc)},
        )


def check_decimal_ledger_invariants() -> DiagnosticGateResult:
    """Gate 2: Verifies exact Decimal accounting, binary float rejection, and double-entry reconciliation."""
    meta: dict[str, Any] = {}
    try:
        from quant_system.core.domain import Fill, Side
        from quant_system.core.ledger import DecimalLedger, _assert_no_float

        # 1. Float rejection
        float_rejected = False
        try:
            _assert_no_float(500000.0, "initial_cash")
        except TypeError:
            float_rejected = True

        if not float_rejected:
            return DiagnosticGateResult(
                gate_name="decimal_ledger",
                status="FAIL",
                title="Decimal Double-Entry Ledger Invariant",
                detail="Critical failure: Binary float was not rejected by accounting kernel.",
                metadata=meta,
            )

        # 2. Reconcile transaction flow
        ledger = DecimalLedger(initial_cash=Decimal("1000000.00"))
        now = datetime.now(UTC)

        # Buy 100 INFY @ 1500.00, fee 33.60
        buy_fill = Fill(
            fill_id="f_diag_1",
            order_id="o_diag_1",
            symbol="INFY",
            side=Side.BUY,
            quantity=100,
            price=Decimal("1500.00"),
            fee=Decimal("33.60"),
            timestamp=now,
        )
        ledger.process_fill(buy_fill)
        if ledger.cash != Decimal("849966.40"):
            return DiagnosticGateResult(
                gate_name="decimal_ledger",
                status="FAIL",
                title="Decimal Double-Entry Ledger Invariant",
                detail=f"Cash deduction mismatch: {ledger.cash} != 849966.40",
                metadata=meta,
            )

        # Sell 40 INFY @ 1600.00, fee 14.34
        sell_fill = Fill(
            fill_id="f_diag_2",
            order_id="o_diag_2",
            symbol="INFY",
            side=Side.SELL,
            quantity=40,
            price=Decimal("1600.00"),
            fee=Decimal("14.34"),
            timestamp=now,
        )
        ledger.process_fill(sell_fill)

        reconciled = ledger.reconcile()
        state_hash = ledger.state_hash
        meta["reconciled"] = reconciled
        meta["state_hash"] = state_hash
        meta["final_cash"] = str(ledger.cash)
        meta["realized_pnl"] = str(ledger.realized_pnl)

        if not reconciled or len(state_hash) != 64:
            return DiagnosticGateResult(
                gate_name="decimal_ledger",
                status="FAIL",
                title="Decimal Double-Entry Ledger Invariant",
                detail="Ledger reconciliation or state hash check failed.",
                metadata=meta,
            )

        return DiagnosticGateResult(
            gate_name="decimal_ledger",
            status="PASS",
            title="Decimal Double-Entry Ledger Invariant",
            detail=f"Paisa-exact accounting verified. State hash: {state_hash[:16]}... Reconcile OK.",
            metadata=meta,
        )

    except Exception as exc:
        return DiagnosticGateResult(
            gate_name="decimal_ledger",
            status="FAIL",
            title="Decimal Double-Entry Ledger Invariant",
            detail=f"Ledger invariant error: {exc}",
            metadata={"error": str(exc)},
        )


def check_folder_write_access(install_root: Path) -> DiagnosticGateResult:
    """Gate 3: Verifies write, read, and delete permissions in data/, logs/, and tmp/."""
    subdirs = ["data", "logs", "tmp"]
    meta: dict[str, str] = {}

    for sub in subdirs:
        target_dir = install_root / sub
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
            probe_file = target_dir / f".quantos_probe_{uuid.uuid4().hex}.tmp"
            token = f"QUANTOS_PROBE_{uuid.uuid4().hex}\n".encode("utf-8")

            # Write
            probe_file.write_bytes(token)
            # Read
            read_back = probe_file.read_bytes()
            if read_back != token:
                return DiagnosticGateResult(
                    gate_name="folder_permissions",
                    status="FAIL",
                    title="Sandbox Folder Permissions",
                    detail=f"Read-back data corrupted in '{sub}/'.",
                    metadata=meta,
                )
            # Delete
            probe_file.unlink(missing_ok=True)
            meta[sub] = "VERIFIED_READ_WRITE_DELETE"
        except Exception as exc:
            meta[sub] = f"ERROR: {exc}"
            return DiagnosticGateResult(
                gate_name="folder_permissions",
                status="FAIL",
                title="Sandbox Folder Permissions",
                detail=f"Write access denied in '{sub}/': {exc}",
                metadata=meta,
            )

    return DiagnosticGateResult(
        gate_name="folder_permissions",
        status="PASS",
        title="Sandbox Folder Permissions",
        detail="Full read/write permissions verified in data/, logs/, and tmp/.",
        metadata=meta,
    )


def detect_hardware_capabilities() -> tuple[DiagnosticGateResult, dict[str, Any]]:
    """Gate 4: Detects Qualcomm Hexagon NPU, GPU/DirectML, and CPU SIMD/AVX2 capabilities."""
    caps: dict[str, Any] = {
        "npu": {"detected": False, "device_name": None, "qnn_available": False},
        "gpu": {"detected": False, "devices": [], "directml_available": False, "cuda_available": False},
        "cpu": {"avx2": False, "architecture": platform.machine(), "arm_neon": False},
    }

    # 1. CPU AVX2 & NEON detection
    try:
        kernel32 = ctypes.windll.kernel32
        PF_AVX2 = 40
        PF_ARM_NEON = 19
        caps["cpu"]["avx2"] = bool(kernel32.IsProcessorFeaturePresent(PF_AVX2))
        caps["cpu"]["arm_neon"] = bool(kernel32.IsProcessorFeaturePresent(PF_ARM_NEON))
    except Exception:
        pass

    # 2. Qualcomm Hexagon NPU detection
    try:
        import winreg

        # Direct check for Qualcomm Hexagon ACPI entry
        for qcom_key in (
            r"SYSTEM\CurrentControlSet\Enum\ACPI\QCOM0D0A",
            r"SYSTEM\CurrentControlSet\Enum\ACPI\QCOM0C11",
        ):
            try:
                k = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, qcom_key)
                sub = winreg.EnumKey(k, 0)
                dev_k = winreg.OpenKey(k, sub)
                desc, _ = winreg.QueryValueEx(dev_k, "DeviceDesc")
                caps["npu"]["detected"] = True
                caps["npu"]["device_name"] = desc.split(";")[-1] if ";" in desc else desc
                break
            except OSError:
                pass

        if not caps["npu"]["detected"]:
            # Fallback to PowerShell CIM
            cmd = "Get-CimInstance Win32_PnPEntity | Where-Object { $_.Name -match 'Hexagon|NPU|Neural' } | Select-Object -First 1 Name | ConvertTo-Json"
            res = subprocess.run(
                ["powershell", "-NoProfile", "-Command", cmd],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if res.returncode == 0 and res.stdout.strip():
                item = json.loads(res.stdout)
                caps["npu"]["detected"] = True
                caps["npu"]["device_name"] = item.get("Name")
    except Exception:
        pass

    # 3. ONNX Runtime QNN / DirectML / CUDA
    try:
        import onnxruntime as ort

        providers = ort.get_available_providers()
        caps["npu"]["qnn_available"] = "QNNExecutionProvider" in providers
        caps["gpu"]["directml_available"] = "DmlExecutionProvider" in providers
        caps["gpu"]["cuda_available"] = "CUDAExecutionProvider" in providers
    except ImportError:
        pass

    # DirectML DLL check
    if not caps["gpu"]["directml_available"]:
        try:
            dml = ctypes.windll.LoadLibrary("DirectML.dll")
            caps["gpu"]["directml_available"] = bool(dml)
        except OSError:
            pass

    # 4. GPU Detection via Registry
    try:
        import winreg

        gpu_key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}",
        )
        for i in range(10):
            try:
                sub_name = winreg.EnumKey(gpu_key, i)
                if sub_name.isdigit():
                    sub = winreg.OpenKey(gpu_key, sub_name)
                    desc, _ = winreg.QueryValueEx(sub, "DriverDesc")
                    ver, _ = winreg.QueryValueEx(sub, "DriverVersion")
                    caps["gpu"]["devices"].append({"name": desc, "driver_version": ver})
                    caps["gpu"]["detected"] = True
            except OSError:
                break
    except Exception:
        pass

    # Build description string
    hw_parts = []
    if caps["npu"]["detected"]:
        hw_parts.append(f"NPU: {caps['npu']['device_name']}")
    if caps["gpu"]["detected"] and caps["gpu"]["devices"]:
        hw_parts.append(f"GPU: {caps['gpu']['devices'][0]['name']}")
    if caps["cpu"]["avx2"]:
        hw_parts.append("AVX2: Enabled")

    summary_detail = " | ".join(hw_parts) if hw_parts else f"CPU Architecture: {platform.machine()}"

    gate = DiagnosticGateResult(
        gate_name="hardware_capabilities",
        status="INFO",
        title="Hardware Capabilities Discovery",
        detail=summary_detail,
        metadata=caps,
    )
    return gate, caps


def run_preflight_diagnostics(install_root: Path) -> PreFlightDiagnosticsReport:
    """Executes all pre-flight diagnostic gates and returns a complete structured report."""
    from quant_system import __version__

    gates: list[DiagnosticGateResult] = []

    # Gate 1: Socket Loopback
    gate_socket = check_loopback_socket(target_port=8080)
    gates.append(gate_socket)

    # Gate 2: Decimal Ledger Invariants
    gate_ledger = check_decimal_ledger_invariants()
    gates.append(gate_ledger)

    # Gate 3: Folder Write Permissions
    gate_folder = check_folder_write_access(install_root)
    gates.append(gate_folder)

    # Gate 4: Hardware Discovery
    gate_hw, hw_dict = detect_hardware_capabilities()
    gates.append(gate_hw)

    all_passed = all(g.status in ("PASS", "INFO") for g in gates)

    report = PreFlightDiagnosticsReport(
        timestamp_utc=datetime.now(UTC).isoformat(),
        install_root=str(install_root.resolve()),
        quantos_version=__version__,
        architecture=platform.machine(),
        all_passed=all_passed,
        gates=gates,
        hardware=hw_dict,
    )
    return report


def write_diagnostics_log(report: PreFlightDiagnosticsReport, install_root: Path) -> Path:
    """Writes human-readable and machine-readable logs to logs/setup_diagnostics.log."""
    log_dir = install_root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "setup_diagnostics.log"

    lines = [
        "=" * 80,
        "QuantOS System Setup Pre-Flight Diagnostics Log",
        f"Timestamp (UTC): {report.timestamp_utc}",
        f"Installation Root: {report.install_root}",
        f"QuantOS Version: {report.quantos_version}",
        f"System Architecture: {report.architecture}",
        "=" * 80,
        "",
    ]

    for g in report.gates:
        lines.append(f"[{g.status}] [{g.gate_name.upper()}] {g.title}")
        lines.append(f"       {g.detail}")
        if g.metadata:
            for k, v in g.metadata.items():
                lines.append(f"       * {k}: {v}")
        lines.append("")

    lines.append("-" * 80)
    overall_status = "READINESS_CERTIFIED — ALL MANDATORY GATES PASSED" if report.all_passed else "READINESS_FAILED"
    lines.append(f"OVERALL STATUS: {overall_status}")
    lines.append("-" * 80)
    lines.append("")
    lines.append("JSON PAYLOAD:")
    lines.append(json.dumps(asdict(report), indent=2))
    lines.append("")

    log_path.write_text("\n".join(lines), encoding="utf-8")
    return log_path
