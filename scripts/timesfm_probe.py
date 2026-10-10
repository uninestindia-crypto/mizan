"""Pin, load and measure google/timesfm-3.0-pytorch in an isolated environment.

What this is for
----------------
Before TimesFM can be a challenger in the short-horizon study, three things have to be *measured*
rather than assumed: that the checkpoint loads at all on this machine, which exact revision loaded,
and what it costs to run. A forecast comparison whose model cannot be pinned is not reproducible, and
one whose resource cost is unknown cannot be scheduled.

Run it with the isolated interpreter, not the QuantOS one::

    D:/quant_system_workspaces/scratch/timesfm-probe-20260910/Scripts/python.exe \
        scripts/timesfm_probe.py

Why isolated
------------
`torch` and `timesfm` are **not** QuantOS dependencies and must not become them for a research
screen. Installing them into `.venv` would change `pyproject.toml` and `uv.lock`, which are
coordinated paths, and would put a 300 MB framework into the dependency set of a platform that does
not use it. The isolated environment lives under `quant_system_workspaces/scratch/` per the disk
layout contract.

Licence
-------
TimesFM 3.0's default licence is **non-commercial and non-production**. This probe exists for the
founder's personal, non-production research within that licence. Nothing here routes an order,
informs a live-money decision, or trains another model. Version 2.5 is Apache-2.0 and is the route to
investigate if this line of work ever needs a commercial path.

What is deliberately not done
-----------------------------
**No fine-tuning.** The declared trial is zero-shot, and fine-tuning would be a different candidate
against a different multiplicity count. The probe loads frozen weights and calls them.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import struct
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT_DIR = Path(__file__).resolve().parent.parent

CHECKPOINT = "google/timesfm-3.0-pytorch"
"""The declared checkpoint. Its resolved revision hash is recorded with every result."""

PE_MACHINE = {0x8664: "AMD64", 0xAA64: "ARM64", 0x01C0: "ARM", 0x014C: "I386"}


def interpreter_facts() -> dict[str, Any]:
    """What this process actually is, read from the binary rather than from the processor.

    ``platform.machine()`` reports the *hardware*, so an emulated x86-64 Python on a Snapdragon
    returns ``ARM64`` and looks native when it is not. The PE header is the statement about the
    binary. This matters for interpreting every timing below: an emulated build is not measuring the
    silicon's capability.
    """
    executable = Path(sys.executable)
    try:
        head = executable.read_bytes()[:1024]
        pe_offset = struct.unpack_from("<I", head, 0x3C)[0]
        machine = PE_MACHINE.get(struct.unpack_from("<H", head, pe_offset + 4)[0], "UNKNOWN")
    except (OSError, struct.error):
        machine = "UNREADABLE"
    import sysconfig  # noqa: PLC0415

    return {
        "executable": executable.as_posix(),
        "pe_machine": machine,
        "sysconfig_platform": sysconfig.get_platform(),
        "reported_machine": platform.machine(),
        "processor_architecture_env": os.environ.get("PROCESSOR_ARCHITECTURE"),
        "python_version": sys.version.split()[0],
        "emulated": machine == "AMD64" and platform.machine() in ("ARM64", "AMD64"),
    }


def peak_memory_mb() -> float | None:
    """Peak working set of this process, in MiB.

    ``GetProcessMemoryInfo`` lives in ``psapi`` on older Windows and is re-exported from
    ``kernel32`` as ``K32GetProcessMemoryInfo`` on current ones. The first version of this tried only
    ``psapi`` and silently returned ``None`` on this machine, which reported "peak memory: None" next
    to a real measurement and looked like the model used none. Both entry points are tried.
    """
    import ctypes  # noqa: PLC0415
    from ctypes import wintypes  # noqa: PLC0415

    class Counters(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("PageFaultCount", wintypes.DWORD),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    counters = Counters()
    counters.cb = ctypes.sizeof(Counters)
    try:
        kernel32 = ctypes.windll.kernel32
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        handle = kernel32.GetCurrentProcess()
    except (AttributeError, OSError):
        return None
    for library, symbol in (
        ("kernel32", "K32GetProcessMemoryInfo"),
        ("psapi", "GetProcessMemoryInfo"),
    ):
        try:
            function = getattr(getattr(ctypes.windll, library), symbol)
        except (AttributeError, OSError):
            continue
        # Without explicit argtypes, ctypes marshals the HANDLE as a 32-bit int and the call fails
        # silently on 64-bit Windows -- which is what made this return None next to a real timing.
        function.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
        function.restype = wintypes.BOOL
        if function(handle, ctypes.byref(counters), counters.cb):
            return float(round(counters.PeakWorkingSetSize / (1024 * 1024), 1))
    return None


def probe(context_length: int, horizons: tuple[int, ...], repeats: int) -> dict[str, Any]:
    """Load the pinned checkpoint and measure a forecast at each declared horizon."""
    report: dict[str, Any] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "checkpoint": CHECKPOINT,
        "fine_tuned": False,
        "interpreter": interpreter_facts(),
        "context_length": context_length,
        "horizons": list(horizons),
        "repeats": repeats,
    }

    try:
        import numpy  # noqa: PLC0415
        import torch  # type: ignore[import-not-found]  # noqa: PLC0415
    except ImportError as error:
        report["status"] = "DEPENDENCIES_MISSING"
        report["detail"] = str(error)
        return report

    report["versions"] = {"torch": torch.__version__, "numpy": numpy.__version__}
    report["torch_threads"] = torch.get_num_threads()
    report["cuda_available"] = torch.cuda.is_available()

    try:
        import timesfm  # type: ignore[import-not-found]  # noqa: PLC0415
    except ImportError as error:
        report["status"] = "TIMESFM_MISSING"
        report["detail"] = str(error)
        return report

    report["versions"]["timesfm"] = getattr(timesfm, "__version__", "unknown")

    started = time.perf_counter()
    try:
        # TimesFM3Forecaster is the 3.0 high-level API. The 2.5 class loads a *different*
        # architecture: pointing it at the 3.0 checkpoint fails with missing state_dict keys
        # ("tokenizer.hidden_layer.weight" and friends), which is how this was found.
        model = timesfm.TimesFM3Forecaster.from_pretrained(CHECKPOINT)
    except Exception as error:  # noqa: BLE001 - the failure itself is a reportable result
        report["status"] = "CHECKPOINT_LOAD_FAILED"
        report["detail"] = f"{type(error).__name__}: {error}"
        report["available_attributes"] = sorted(
            name for name in dir(timesfm) if not name.startswith("_")
        )
        return report
    report["load_seconds"] = round(time.perf_counter() - started, 3)
    report["peak_memory_mb_after_load"] = peak_memory_mb()
    report["resolved_revision"] = _resolved_revision()

    # A deterministic synthetic series. The point is the cost of a forward pass, not its accuracy --
    # accuracy is measured against real NSE bars in the study itself, not here.
    generator = numpy.random.default_rng(20260910)
    series = numpy.cumsum(generator.standard_normal(context_length)).astype(numpy.float32)

    timings: dict[str, Any] = {}
    for horizon in horizons:
        try:
            # Warm up first: the first call pays lazy graph and allocator setup that would
            # otherwise be charged to the measurement.
            model.predict(context=series, horizon=horizon)
            started = time.perf_counter()
            for _ in range(repeats):
                output = model.predict(context=series, horizon=horizon, return_quantiles=True)
            elapsed = time.perf_counter() - started
            # ForecastOutput exposes `forecast` (point) and `quantiles` (horizon x 9 levels).
            point = numpy.asarray(output.forecast)
            quantiles = numpy.asarray(output.quantiles)
            timings[str(horizon)] = {
                "seconds_total": round(elapsed, 4),
                "milliseconds_each": round(elapsed / repeats * 1000, 2),
                "point_shape": list(point.shape),
                "quantile_shape": list(quantiles.shape),
                "finite": bool(numpy.isfinite(point).all()),
            }
        except Exception as error:  # noqa: BLE001
            timings[str(horizon)] = {"failed": f"{type(error).__name__}: {error}"}

    report["forecast_timings"] = timings
    report["batch_throughput"] = _batch_throughput(model, series, numpy, horizon=max(horizons))
    report["peak_memory_mb"] = peak_memory_mb()
    report["status"] = (
        "OK" if any("failed" not in v for v in timings.values()) else "FORECAST_FAILED"
    )
    return report


def _batch_throughput(
    model: Any, series: Any, numpy: Any, *, horizon: int, sizes: tuple[int, ...] = (1, 8, 32, 128)
) -> dict[str, Any]:
    """Per-series cost at several batch sizes.

    This is the number that decides whether a full-universe TimesFM arm is computable at all, so it
    is measured rather than assumed. A single-series call pays fixed per-call overhead that batching
    amortises; how much it amortises is a property of this build on this machine.
    """
    out: dict[str, Any] = {}
    generator = numpy.random.default_rng(20260911)
    for size in sizes:
        contexts = [
            numpy.cumsum(generator.standard_normal(len(series))).astype(numpy.float32)
            for _ in range(size)
        ]
        try:
            list(model.predict_batch(contexts=contexts, horizon=horizon))
            started = time.perf_counter()
            outputs = list(model.predict_batch(contexts=contexts, horizon=horizon))
            elapsed = time.perf_counter() - started
            out[str(size)] = {
                "seconds_total": round(elapsed, 4),
                "milliseconds_per_series": round(elapsed / size * 1000, 2),
                "outputs": len(outputs),
            }
        except Exception as error:  # noqa: BLE001
            out[str(size)] = {"failed": f"{type(error).__name__}: {error}"}
    return out


def _resolved_revision() -> str | None:
    """The exact commit of the checkpoint that was downloaded, from the HF cache layout."""
    try:
        from huggingface_hub import (
            constants,  # type: ignore[import-not-found,unused-ignore]  # noqa: PLC0415
        )

        cache = Path(constants.HF_HUB_CACHE)
    except Exception:  # noqa: BLE001
        cache = Path.home() / ".cache" / "huggingface" / "hub"
    folder = cache / f"models--{CHECKPOINT.replace('/', '--')}" / "snapshots"
    if not folder.is_dir():
        return None
    snapshots = sorted(folder.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
    return snapshots[0].name if snapshots else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--context-length", type=int, default=512)
    parser.add_argument(
        "--horizons",
        type=int,
        nargs="+",
        default=[1, 2, 3],
        help="Forecast horizons in sessions -- the three declared holds.",
    )
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument(
        "--out", type=Path, default=ROOT_DIR / "reports/short_horizon/timesfm-probe.json"
    )
    args = parser.parse_args()

    report = probe(args.context_length, tuple(args.horizons), args.repeats)

    print("=== TimesFM probe ===")
    print(f"checkpoint   : {report['checkpoint']} (fine-tuned: {report['fine_tuned']})")
    interpreter = report["interpreter"]
    print(f"interpreter  : {interpreter['pe_machine']} ({interpreter['sysconfig_platform']})")
    print(f"versions     : {report.get('versions')}")
    print(f"status       : {report['status']}")
    if report.get("detail"):
        print(f"detail       : {report['detail']}")
    if report.get("resolved_revision"):
        print(f"revision     : {report['resolved_revision']}")
    if report.get("load_seconds") is not None:
        print(
            f"load         : {report['load_seconds']}s, peak "
            f"{report.get('peak_memory_mb_after_load')} MiB"
        )
    for horizon, timing in (report.get("forecast_timings") or {}).items():
        print(f"  horizon {horizon:>2} : {timing}")
    for size, timing in (report.get("batch_throughput") or {}).items():
        print(f"  batch {size:>4} : {timing}")
    print(f"peak memory  : {report.get('peak_memory_mb')} MiB")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(f"\nwritten      : {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
