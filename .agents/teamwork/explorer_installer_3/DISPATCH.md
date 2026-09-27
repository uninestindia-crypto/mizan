## 2026-09-25T10:04:17Z

From: parent (6939d1c1-6756-4f85-95cf-a9f718ba5fed)
Task: Investigate drive isolation, environment scaffolding, and the integrated pre-flight diagnostics engine.
Specifically:
1. Drive Selection & Scaffolding:
   - Logic for smart installation drive selection: detecting all available fixed drives on Windows, checking if D:\ exists with sufficient free space (e.g., >= 2 GB) and selecting D:\QuantOS, otherwise falling back to C:\QuantOS, while allowing user customization.
   - Required isolated runtime directories: data/, logs/, tmp/.
   - Starter .env configuration file: inspect existing .env or configuration needs in QuantOS (src/quant_system/), enumerate default environment keys, placeholders, and user documentation.
   - Windows Shortcuts: examine how to create standard Windows Desktop shortcut (QuantOS.lnk) and Start Menu program entry pointing to quantos.exe (with icon, working directory set to install root, description).
2. Pre-Flight Diagnostics Engine:
   - Socket Loopback: test binding to 127.0.0.1 on local ports (e.g., checking port availability or binding a test socket).
   - Decimal Ledger Invariant Arithmetic: inspect QuantOS accounting requirements (Decimal usage, checking that float precision errors do not occur, verifying ledger balance invariant calculations).
   - Folder Write Access: test write and read verification in data/, logs/, tmp/.
   - Hardware Capabilities Detection:
     - Qualcomm Hexagon NPU detection (check WMI Win32_PnPEntity, Snapdragon / NPU device IDs, ONNX QNN execution provider availability).
     - GPU detection (WMI Win32_VideoController, NVIDIA/AMD/Intel, DirectX/DirectML).
     - CPU AVX2 detection (instruction set capabilities).
   - Diagnostics Logging & UI:
     - Logging output to logs/setup_diagnostics.log.
     - Visual green-badge readiness summary format and 1-click launch trigger (quantos.exe).

Deliver report at: D:\quant_system\.agents\teamwork\explorer_installer_3\report.md
Deliver handoff at: D:\quant_system\.agents\teamwork\explorer_installer_3\handoff.md
