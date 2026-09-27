# Context for SWE Light Task

## Mission
Build a production-grade Windows setup installer (`QuantOS_v1.0.0_Setup.exe`) that packages the zero-console QuantOS Desktop Studio (`quantos-studio.exe`) as the primary consumer desktop application, enforces strict drive isolation (zero C: drive leakage), creates desktop shortcuts to Studio, preserves user research evidence on uninstall, and verifies cryptographic integrity via SBOM and release manifest.

## Working Directory
- Project Root: D:\quant_system
- Agent Working Directory: D:\quant_system\.agents\teamwork\swe_1
- Original Request: D:\quant_system\.agents\teamwork\ORIGINAL_REQUEST.md (under section `## 2026-09-25T10:37:52Z`)

## Constraints & Requirements
- Read and follow AGENTS.md startup sequence and rules (create active work record in agent_context/work/active/ before editing).
- Keep changes focused on the installer, desktop studio release packaging, drive isolation, shortcut generation, uninstaller preservation, SBOM, and release manifest.
- Ensure all automated test gates pass:
  - `pytest tests/test_release_packaging.py`
  - `pytest tests/test_quantos_studio.py`
  - `scripts/audit-disk-layout.ps1`
  - `scripts/audit-agent-claims.ps1`
