# Dispatch Log

## 2026-09-25T10:39:02Z

You are the SWE Light orchestrator for this task.
Your working directory is: D:\quant_system\.agents\teamwork\swe_1\
The authoritative user request is recorded in: D:\quant_system\.agents\teamwork\ORIGINAL_REQUEST.md under header ## 2026-09-25T10:37:52Z.
Context is available at: D:\quant_system\.agents\teamwork\swe_1\context.md.

Task Summary:
This is a single self-contained fix; keep it small and focused.
Build a production-grade Windows setup installer (`QuantOS_v1.0.0_Setup.exe`) that packages the zero-console QuantOS Desktop Studio (`quantos-studio.exe`) as the primary consumer desktop application, enforces strict drive isolation (zero C: drive leakage), creates desktop shortcuts to Studio, preserves user research evidence on uninstall, and verifies cryptographic integrity via SBOM and release manifest.

Working directory: D:\quant_system
Integrity mode: development

Requirements:
- R1. Desktop Studio Multi-Binary Release Bundle (package ambos quantos-studio.exe and quantos.exe into dist/quantos).
- R2. Consumer-Grade Drive-Isolated Setup Wizard (QuantOS_v1.0.0_Setup.exe, drive isolation, Desktop shortcut to Studio, safe uninstaller preserving data/ and logs/).
- R3. Automated Packaging & Verification Pipeline (compile Studio and Engine into bundle, compile setup wizard, generate SBOM tied to uv.lock, SHA-256 release manifest).

Acceptance Criteria:
- dist/quantos/quantos-studio.exe and dist/quantos/quantos.exe build and present.
- dist/QuantOS_v1.0.0_Setup.exe standalone executable.
- sbom.json bound to uv.lock SHA-256.
- release-manifest.json and MANIFEST.sha256 accurate.
- Zero console window on Studio launch; runtime temporary files/caches/logs strictly on target drive.
- Clean shutdown of background server process on Studio window close.
- Uninstaller preserves data/ and logs/.
- Test gates:
  - pytest tests/test_release_packaging.py passes 100%
  - pytest tests/test_quantos_studio.py passes 100%
  - scripts/audit-disk-layout.ps1 and scripts/audit-agent-claims.ps1 exit 0

Follow repo startup sequence in AGENTS.md (active work record in agent_context/work/active/ before editing). Maintain progress.md in your working directory.
When finished, send a handoff / victory claim to the Sentinel.
