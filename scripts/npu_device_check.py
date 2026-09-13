"""NPU Device Discovery and Verification Probe for Qualcomm Snapdragon Hexagon NPU.

Verifies:
1. Native ARM64 binary architecture of the Python interpreter (PE 0xAA64).
2. Availability of ONNX Runtime QNN ExecutionProvider.
3. Successful initialization and tensor execution on the Hexagon Tensor Processor (HTP).
"""

from __future__ import annotations

import json
import platform
import struct
import sys
import time


def get_pe_machine_type(executable_path: str) -> str:
    """Reads the PE machine type from the binary header."""
    try:
        with open(executable_path, "rb") as f:
            dos_header = f.read(64)
            if len(dos_header) < 64 or dos_header[:2] != b"MZ":
                return "NOT_PE"
            pe_offset = struct.unpack("<I", dos_header[60:64])[0]
            f.seek(pe_offset)
            pe_signature = f.read(4)
            if pe_signature != b"PE\x00\x00":
                return "INVALID_PE"
            machine_bytes = f.read(2)
            machine = struct.unpack("<H", machine_bytes)[0]
            if machine == 0xAA64:
                return "ARM64"
            elif machine == 0x8664:
                return "AMD64"
            elif machine == 0x014C:
                return "I386"
            else:
                return f"UNKNOWN_0x{machine:04X}"
    except Exception as exc:
        return f"ERROR_{exc}"


def run_probe() -> dict[str, object]:
    result: dict[str, object] = {
        "python_executable": sys.executable,
        "python_version": sys.version,
        "platform_machine": platform.machine(),
        "pe_machine_type": get_pe_machine_type(sys.executable),
        "is_native_arm64": get_pe_machine_type(sys.executable) == "ARM64",
        "onnxruntime_installed": False,
        "onnxruntime_version": None,
        "available_providers": [],
        "qnn_provider_available": False,
        "qnn_htp_initialized": False,
        "npu_gemm_latency_ms": None,
        "npu_status": "PENDING",
    }

    try:
        import onnxruntime as ort  # type: ignore[import-not-found]  # optional NPU dep, deliberately not in uv.lock

        result["onnxruntime_installed"] = True
        result["onnxruntime_version"] = ort.__version__

        try:
            import onnxruntime_qnn as qnn  # type: ignore[import-not-found]  # optional NPU dep, deliberately not in uv.lock

            ort.register_execution_provider_library("QNNExecutionProvider", qnn.get_library_path())
        except ImportError:
            pass

        providers = ort.get_available_providers()
        result["available_providers"] = providers
        result["qnn_provider_available"] = "QNNExecutionProvider" in providers

        devices = ort.get_ep_devices()
        npu_devices = [d for d in devices if d.device.type == ort.OrtHardwareDeviceType.NPU]
        result["npu_hardware_detected"] = len(npu_devices) > 0

        if result["qnn_provider_available"] and npu_devices:
            # Test QNN ExecutionProvider with Hexagon HTP backend
            try:
                import numpy as np
                from onnx import (  # type: ignore[import-not-found]  # optional NPU dep, deliberately not in uv.lock
                    TensorProto,
                    helper,
                )

                # Build a simple GEMM ONNX model in memory: Y = A * B
                N = 256
                input_a = helper.make_tensor_value_info("A", TensorProto.FLOAT, [N, N])
                input_b = helper.make_tensor_value_info("B", TensorProto.FLOAT, [N, N])
                output_y = helper.make_tensor_value_info("Y", TensorProto.FLOAT, [N, N])

                node_def = helper.make_node(
                    "MatMul",
                    inputs=["A", "B"],
                    outputs=["Y"],
                )
                graph_def = helper.make_graph(
                    [node_def],
                    "matmul_test",
                    [input_a, input_b],
                    [output_y],
                )
                opset = helper.make_opsetid("", 21)
                model_def = helper.make_model(
                    graph_def, opset_imports=[opset], producer_name="npu_probe"
                )
                model_bytes = model_def.SerializeToString()

                # Session options targeting Hexagon NPU
                so = ort.SessionOptions()
                so.add_provider_for_devices([npu_devices[0]], {"htp_performance_mode": "burst"})
                session = ort.InferenceSession(
                    model_bytes,
                    sess_options=so,
                )

                active_providers = session.get_providers()
                result["session_active_providers"] = active_providers
                result["qnn_htp_initialized"] = "QNNExecutionProvider" in active_providers

                # Run inference test
                a_val = np.random.randn(N, N).astype(np.float32)
                b_val = np.random.randn(N, N).astype(np.float32)

                # Warmup
                for _ in range(5):
                    session.run(None, {"A": a_val, "B": b_val})

                t0 = time.perf_counter()
                repeats = 50
                for _ in range(repeats):
                    session.run(None, {"A": a_val, "B": b_val})
                t1 = time.perf_counter()

                latency_ms = ((t1 - t0) / repeats) * 1000.0
                result["npu_gemm_latency_ms"] = round(latency_ms, 3)
                result["npu_status"] = "ACTIVE_ON_HEXAGON_HTP"
            except Exception as qnn_err:
                result["qnn_error"] = str(qnn_err)
                result["npu_status"] = "QNN_INIT_FAILED"
        else:
            result["npu_status"] = "QNN_PROVIDER_OR_NPU_MISSING"

    except ImportError as imp_err:
        result["npu_status"] = f"ONNXRUNTIME_NOT_INSTALLED_{imp_err}"

    return result


if __name__ == "__main__":
    probe_results = run_probe()
    print(json.dumps(probe_results, indent=2))
