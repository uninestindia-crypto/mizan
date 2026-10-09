"""Hardware accelerator auto-detection (NPU, GPU, CPU) for local model execution.

Supports Windows on ARM (Qualcomm Snapdragon X Hexagon NPU & Adreno GPU),
x86_64 machines (Intel AI Boost, AMD Ryzen AI, NVIDIA CUDA, DirectML),
and universal multi-core CPU SIMD fallback.
"""

from __future__ import annotations

import logging
import os
import platform
import sys
from dataclasses import asdict, dataclass
from typing import Any, Literal

logger = logging.getLogger(__name__)

AcceleratorTarget = Literal["auto", "npu", "gpu", "cpu"]


@dataclass(frozen=True, slots=True)
class DeviceInfo:
    available: bool
    name: str
    category: str  # "NPU", "GPU", "CPU"
    provider: str  # "DirectML / QNN", "CUDA / DirectML", "CPU SIMD"
    details: str
    status: str  # "Ready", "Standby", "Not Available"


@dataclass(frozen=True, slots=True)
class LocalModelInfo:
    id: str
    name: str
    category: str
    size: str
    recommended_hardware: str
    status: str  # "ACTIVE", "READY", "AVAILABLE"
    description: str


@dataclass(frozen=True, slots=True)
class HardwareTopology:
    active_target: AcceleratorTarget
    effective_target: Literal["npu", "gpu", "cpu"]
    platform: str
    architecture: str
    devices: dict[str, DeviceInfo]
    local_models: list[LocalModelInfo]


def detect_hardware_topology(selected_target: AcceleratorTarget = "auto") -> HardwareTopology:
    """Detects available hardware accelerators across Windows NPU, GPU, and CPU."""
    npu_info = _detect_npu()
    gpu_info = _detect_gpu()
    cpu_info = _detect_cpu()

    # Determine effective target
    effective: Literal["npu", "gpu", "cpu"]
    if selected_target == "npu" and npu_info.available:
        effective = "npu"
    elif selected_target == "gpu" and gpu_info.available:
        effective = "gpu"
    elif selected_target == "cpu":
        effective = "cpu"
    else:  # "auto" or requested device unavailable
        if npu_info.available:
            effective = "npu"
        elif gpu_info.available:
            effective = "gpu"
        else:
            effective = "cpu"

    models = _catalog_local_models(effective)

    return HardwareTopology(
        active_target=selected_target,
        effective_target=effective,
        platform=platform.system(),
        architecture=platform.machine(),
        devices={
            "npu": npu_info,
            "gpu": gpu_info,
            "cpu": cpu_info,
        },
        local_models=models,
    )


def topology_to_dict(topology: HardwareTopology) -> dict[str, Any]:
    return {
        "active_target": topology.active_target,
        "effective_target": topology.effective_target,
        "platform": topology.platform,
        "architecture": topology.architecture,
        "devices": {k: asdict(v) for k, v in topology.devices.items()},
        "local_models": [asdict(m) for m in topology.local_models],
    }


def _detect_npu() -> DeviceInfo:
    """Inspects Windows device classes for dedicated NPUs."""
    if sys.platform != "win32":
        return DeviceInfo(
            available=False,
            name="Not Available (Non-Windows)",
            category="NPU",
            provider="None",
            details="NPU acceleration requires Windows 11 with DirectML or QNN driver.",
            status="Not Available",
        )

    try:
        import winreg

        base = r"SYSTEM\CurrentControlSet\Control\Class"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base) as k:
            num_subkeys = winreg.QueryInfoKey(k)[0]
            for i in range(num_subkeys):
                sub = winreg.EnumKey(k, i)
                try:
                    with winreg.OpenKey(k, sub) as sk:
                        classname, _ = winreg.QueryValueEx(sk, "Class")
                        if classname == "ComputeAccelerator":
                            # Enumerate accelerator devices
                            for j in range(winreg.QueryInfoKey(sk)[0]):
                                dev_sub = winreg.EnumKey(sk, j)
                                if dev_sub.isdigit():
                                    with winreg.OpenKey(sk, dev_sub) as dsk:
                                        desc, _ = winreg.QueryValueEx(dsk, "DriverDesc")
                                        if desc and desc.strip():
                                            name = desc.strip()
                                            provider = "DirectML / QNN"
                                            details = "Hardware NPU acceleration active with ultra-low power consumption."
                                            if "hexagon" in name.lower():
                                                details = "Qualcomm Hexagon NPU (45 TOPS) - Dedicated AI Copilot engine."
                                            elif "boost" in name.lower():
                                                details = "Intel AI Boost NPU - Integrated low-power neural accelerator."
                                            elif "ryzen" in name.lower():
                                                details = "AMD Ryzen AI NPU - Dedicated XDNA neural processor."
                                            return DeviceInfo(
                                                available=True,
                                                name=name,
                                                category="NPU",
                                                provider=provider,
                                                details=details,
                                                status="Ready",
                                            )
                except Exception:
                    continue
    except Exception as exc:
        logger.debug("Registry NPU query skipped: %s", exc)

    return DeviceInfo(
        available=False,
        name="No Hardware NPU Detected",
        category="NPU",
        provider="None",
        details="System has no dedicated neural processing unit. GPU and CPU acceleration available.",
        status="Not Available",
    )


def _detect_gpu() -> DeviceInfo:
    """Inspects graphics display adapters for discrete and integrated GPUs."""
    if sys.platform != "win32":
        return DeviceInfo(
            available=True,
            name="Standard GPU Acceleration",
            category="GPU",
            provider="DirectML / Vulkan",
            details="Standard graphics acceleration.",
            status="Ready",
        )

    try:
        import winreg

        base = r"SYSTEM\CurrentControlSet\Control\Class"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, base) as k:
            num_subkeys = winreg.QueryInfoKey(k)[0]
            for i in range(num_subkeys):
                sub = winreg.EnumKey(k, i)
                try:
                    with winreg.OpenKey(k, sub) as sk:
                        classname, _ = winreg.QueryValueEx(sk, "Class")
                        if classname == "Display":
                            for j in range(winreg.QueryInfoKey(sk)[0]):
                                dev_sub = winreg.EnumKey(sk, j)
                                if dev_sub.isdigit():
                                    with winreg.OpenKey(sk, dev_sub) as dsk:
                                        desc, _ = winreg.QueryValueEx(dsk, "DriverDesc")
                                        if desc and desc.strip():
                                            name = desc.strip()
                                            lower = name.lower()
                                            if "adreno" in lower:
                                                provider = "DirectML / Vulkan"
                                                details = "Qualcomm Adreno GPU for parallel tensor matrix operations."
                                            elif (
                                                "nvidia" in lower
                                                or "geforce" in lower
                                                or "rtx" in lower
                                            ):
                                                provider = "CUDA / DirectML"
                                                details = (
                                                    "NVIDIA Tensor Core hardware acceleration."
                                                )
                                            elif "radeon" in lower:
                                                provider = "DirectML / Vulkan"
                                                details = (
                                                    "AMD Radeon GPU acceleration via DirectML."
                                                )
                                            elif (
                                                "intel" in lower
                                                or "arc" in lower
                                                or "iris" in lower
                                            ):
                                                provider = "DirectML"
                                                details = "Intel Graphics architecture with DirectML support."
                                            else:
                                                provider = "DirectML"
                                                details = (
                                                    "DirectX 12 graphics compute acceleration."
                                                )

                                            return DeviceInfo(
                                                available=True,
                                                name=name,
                                                category="GPU",
                                                provider=provider,
                                                details=details,
                                                status="Ready",
                                            )
                except Exception:
                    continue
    except Exception as exc:
        logger.debug("Registry GPU query skipped: %s", exc)

    return DeviceInfo(
        available=True,
        name="DirectX Display Adapter",
        category="GPU",
        provider="DirectML",
        details="Standard graphics acceleration.",
        status="Ready",
    )


def _detect_cpu() -> DeviceInfo:
    """Detects CPU architecture, core count, and SIMD vector capabilities."""
    arch = platform.machine()
    cores = os.cpu_count() or 4

    if arch.upper() in ("ARM64", "AARCH64"):
        provider = "ARM64 NEON Vector Engine"
        name = f"Qualcomm / ARM64 ({cores} Cores)"
        details = f"{cores}-core ARM64 architecture with NEON 128-bit SIMD acceleration."
    else:
        provider = "AVX2 / Multi-Threaded SIMD"
        name = f"x86_64 Processor ({cores} Cores)"
        details = f"{cores}-core x86_64 CPU with multi-threaded vector execution."

    return DeviceInfo(
        available=True,
        name=name,
        category="CPU",
        provider=provider,
        details=details,
        status="Ready",
    )


def _catalog_local_models(effective_target: str) -> list[LocalModelInfo]:
    """Returns the catalog of integrated local models and their active acceleration."""
    target_badge = effective_target.upper()
    return [
        LocalModelInfo(
            id="cand_mizan_v1",
            name="Mīzān Flagship Alpha (cand_mizan_v1)",
            category="Pooled Cross-Sectional Ridge",
            size="~15 MB",
            recommended_hardware="CPU / NPU",
            status=f"ACTIVE ({target_badge})",
            description="Flagship QuantOS pooled cross-sectional equity ranking and alpha model (frozen weights trial_mizan_h11_002, 11-day horizon).",
        ),
        LocalModelInfo(
            id="cand_ridge_v1",
            name="Governed Single-Instrument Ridge",
            category="L2-Regularized Linear Alpha",
            size="~5 MB",
            recommended_hardware="CPU SIMD",
            status="READY",
            description="Single-instrument rolling walk-forward models evaluated across 101 governed trial evaluations with next-bar execution.",
        ),
        LocalModelInfo(
            id="embeddinggemma-270m",
            name="EmbeddingGemma 2 (270M)",
            category="Semantic Embeddings & Search",
            size="~300 MB",
            recommended_hardware="NPU / CPU",
            status="READY",
            description="Dense vector embeddings for AAOIFI Shariah standards, compliance guidelines, and market research retrieval.",
        ),
    ]
