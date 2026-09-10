"""Bounded feasibility test: can QuantOS reach the Snapdragon Hexagon NPU for model inference?

Scope and limits
----------------
This is a **feasibility probe**, not an optimisation. It answers one question with evidence:
whether NPU execution is reachable from the environment QuantOS actually runs in, and if not, what
exactly blocks it. It never changes a model, an accounting path, or a risk control.

The brief that commissioned it says: *"If NPU conversion fails or provides negligible benefit,
retain CPU execution and document the result."* Documenting the result is the deliverable, and a
negative is a real answer -- provided it is a measured one rather than an assumed one.

What is checked, in order, because each step gates the next
----------------------------------------------------------
1. **Is the NPU physically present and healthy?** Read from Windows PnP, not assumed from the SKU.
2. **What architecture is the Python process?** Read from the interpreter's own PE header, which is
   the definitive statement of what a binary was built for -- not from ``platform.machine()``, which
   reports the *hardware* and therefore says ``ARM64`` even inside an emulated x86-64 process.
3. **Is a QNN runtime present?** The Hexagon backend is reached through Qualcomm's QNN libraries
   (``QnnHtp.dll`` and friends). Without them there is no NPU path regardless of anything else.
4. **Do the ONNX Runtime execution providers actually offer an NPU?** Enumerated from the installed
   runtime, never inferred from a package name.
5. **A CPU baseline**, so any future NPU number has something honest to be compared against.

The structural constraint this probe exists to surface
------------------------------------------------------
Windows on ARM runs x86-64 processes under emulation. An emulated x86-64 process **cannot load ARM64
DLLs**, and the QNN HTP backend ships only as ARM64. So if the interpreter is x86-64, the NPU is
unreachable from it no matter what packages are installed -- and installing ``onnxruntime-qnn`` will
appear to succeed while providing no NPU execution provider at runtime. That failure mode is silent
and easy to mistake for "the NPU is slow", which is why this probe reports the interpreter
architecture before it reports any timing.
"""

from __future__ import annotations

import argparse
import json
import platform
import struct
import subprocess
import sys
import sysconfig
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent

PE_MACHINE = {
    0x8664: "AMD64",
    0xAA64: "ARM64",
    0x01C0: "ARM",
    0x014C: "I386",
}

QNN_BACKEND_LIBRARIES = ("QnnHtp.dll", "QnnHtpV73Stub.dll", "QnnSystem.dll", "QnnCpu.dll")
"""The Hexagon backend is reached through these. Absent, there is no NPU path at all."""


def pe_machine(path: Path) -> str:
    """The architecture a Windows binary was compiled for, from its own PE header.

    ``platform.machine()`` is not usable for this: it reports the processor, so an emulated x86-64
    Python on a Snapdragon returns ``ARM64`` and looks native when it is not.
    """
    try:
        head = path.read_bytes()[:1024]
        pe_offset = struct.unpack_from("<I", head, 0x3C)[0]
        machine = struct.unpack_from("<H", head, pe_offset + 4)[0]
    except (OSError, struct.error) as error:
        return f"UNREADABLE ({error})"
    return PE_MACHINE.get(machine, f"UNKNOWN(0x{machine:04x})")


def npu_devices() -> list[dict[str, str]]:
    """Compute accelerators Windows reports, with their status."""
    script = (
        "Get-PnpDevice -Class ComputeAccelerator -ErrorAction SilentlyContinue | "
        "Select-Object Status,FriendlyName,InstanceId | ConvertTo-Json -Compress"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as error:
        return [{"Status": "PROBE_FAILED", "FriendlyName": str(error), "InstanceId": ""}]
    text = result.stdout.strip()
    if not text:
        return []
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return [{"Status": "UNPARSEABLE", "FriendlyName": text[:200], "InstanceId": ""}]
    items = payload if isinstance(payload, list) else [payload]
    return [{k: str(v) for k, v in item.items()} for item in items]


def qnn_libraries() -> dict[str, str | None]:
    """Where each QNN backend library was found, if anywhere."""
    roots = [
        Path("C:/Windows/System32"),
        Path("C:/Program Files/Qualcomm"),
        *[Path(entry) for entry in sys.path if entry],
    ]
    found: dict[str, str | None] = {}
    for name in QNN_BACKEND_LIBRARIES:
        found[name] = None
        for root in roots:
            candidate = root / name
            if candidate.is_file():
                found[name] = candidate.as_posix()
                break
    return found


def onnx_providers() -> dict[str, Any]:
    """Execution providers the installed ONNX Runtime actually offers.

    Enumerated at runtime. A package called ``onnxruntime-qnn`` that installs cleanly still provides
    no ``QNNExecutionProvider`` when its native backend cannot load, and that is exactly the silent
    failure this reports.
    """
    try:
        import onnxruntime  # noqa: PLC0415
    except ImportError as error:
        return {"installed": False, "detail": str(error), "providers": []}
    return {
        "installed": True,
        "version": onnxruntime.__version__,
        "providers": list(onnxruntime.get_available_providers()),
        "npu_provider_present": any(
            name in onnxruntime.get_available_providers()
            for name in ("QNNExecutionProvider", "DmlExecutionProvider")
        ),
    }


def cpu_baseline(repeats: int = 20) -> dict[str, Any]:
    """A reproducible CPU number, so a future NPU claim has something to beat.

    Deliberately a plain dense matmul rather than a model forward pass: it needs no checkpoint, no
    network and no framework beyond what is already installed, so it reproduces anywhere. It is a
    floor for comparison, not a proxy for model latency.
    """
    try:
        import numpy  # noqa: PLC0415
    except ImportError as error:
        return {"available": False, "detail": str(error)}

    size = 512
    left = numpy.random.default_rng(20260910).standard_normal((size, size), dtype=numpy.float32)
    right = numpy.random.default_rng(20260911).standard_normal((size, size), dtype=numpy.float32)
    left @ right  # warm up BLAS so the first call's setup is not charged to the measurement
    started = time.perf_counter()
    for _ in range(repeats):
        product = left @ right
    elapsed = time.perf_counter() - started
    flops = 2.0 * size**3 * repeats
    return {
        "available": True,
        "numpy_version": numpy.__version__,
        "matrix_size": size,
        "repeats": repeats,
        "seconds_total": round(elapsed, 6),
        "milliseconds_each": round(elapsed / repeats * 1000, 4),
        "gflops": round(flops / elapsed / 1e9, 2),
        "result_finite": bool(numpy.isfinite(product).all()),
    }


def verdict(report: dict[str, Any]) -> tuple[str, list[str]]:
    """The bounded conclusion, with every blocker named."""
    blockers: list[str] = []
    interpreter = report["interpreter"]
    hardware = report["hardware"]

    if not hardware["npu_devices"]:
        blockers.append("no compute accelerator is reported by Windows")
    elif not any(device.get("Status") == "OK" for device in hardware["npu_devices"]):
        blockers.append("an NPU is present but Windows does not report it as OK")

    if interpreter["pe_machine"] != "ARM64":
        blockers.append(
            f"the Python interpreter is {interpreter['pe_machine']}, not ARM64. Windows on ARM runs "
            f"x86-64 processes under emulation, and an emulated x86-64 process cannot load the "
            f"ARM64 QNN HTP backend. No package installation changes this"
        )

    if not any(report["qnn_libraries"].values()):
        blockers.append("no QNN backend library is present anywhere on the search path")

    onnx = report["onnx_runtime"]
    if not onnx.get("installed"):
        blockers.append("onnxruntime is not installed in this environment")
    elif not onnx.get("npu_provider_present"):
        blockers.append(
            f"onnxruntime offers no NPU execution provider; it has {onnx.get('providers')}"
        )

    if blockers:
        return "NPU_UNREACHABLE", blockers
    return "NPU_REACHABLE_PENDING_CONVERSION", []


def run(args: argparse.Namespace) -> int:
    executable = Path(sys.executable)
    report: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "hardware": {
            "processor": platform.processor(),
            "reported_machine": platform.machine(),
            "npu_devices": npu_devices(),
        },
        "interpreter": {
            "executable": executable.as_posix(),
            "version": sys.version,
            "pe_machine": pe_machine(executable),
            "sysconfig_platform": sysconfig.get_platform(),
            "processor_architecture_env": None,
        },
        "qnn_libraries": qnn_libraries(),
        "onnx_runtime": onnx_providers(),
        "cpu_baseline": cpu_baseline(),
    }
    import os

    report["interpreter"]["processor_architecture_env"] = os.environ.get("PROCESSOR_ARCHITECTURE")

    outcome, blockers = verdict(report)
    report["verdict"] = outcome
    report["blockers"] = blockers

    print("=== NPU feasibility probe ===")
    print(f"processor         : {report['hardware']['processor']}")
    for device in report["hardware"]["npu_devices"]:
        print(f"accelerator       : [{device.get('Status')}] {device.get('FriendlyName')}")
    print(
        f"interpreter       : {report['interpreter']['pe_machine']} "
        f"(sysconfig {report['interpreter']['sysconfig_platform']}, "
        f"platform.machine() reports {report['hardware']['reported_machine']})"
    )
    print(
        f"QNN libraries     : {sum(1 for v in report['qnn_libraries'].values() if v)} of "
        f"{len(QNN_BACKEND_LIBRARIES)} found"
    )
    print(f"onnxruntime       : {report['onnx_runtime'].get('providers') or 'not installed'}")
    baseline = report["cpu_baseline"]
    if baseline.get("available"):
        print(
            f"CPU baseline      : {baseline['milliseconds_each']} ms per 512^3 matmul "
            f"({baseline['gflops']} GFLOP/s)"
        )
    print(f"\nVERDICT           : {outcome}")
    for blocker in blockers:
        print(f"  BLOCKER         : {blocker}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(f"\nwritten           : {args.out}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT_DIR / "reports/short_horizon/npu-feasibility-probe.json",
    )
    return run(parser.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
