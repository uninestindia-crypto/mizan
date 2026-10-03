# NOTICE: branch `claude/retail-redesign` edits paths claimed by other active records

STATUS: NOTICE until the branch is merged or abandoned
FILED_BY: Claude Code, record `20260928-claude-retail-redesign-build.md`
FILED_UTC: 2026-09-30
WORKSPACE: `D:\quant_system_workspaces\worktrees\feature-retail-redesign-e787ac4-20260928-000443`
(branch `claude/retail-redesign`, based on main e787ac462)

Nothing below is on `main`. It is listed so that a merge is not a surprise to whoever owns these
paths, and so no test count or hash pinned elsewhere is trusted after the merge without re-measuring.

| Path | Change | Records that name it |
|---|---|---|
| `src/quant_system/server/app.py` | `/` route renamed `/classic`; `register_v2(app)` appended | UI/server records, real-journey API |
| `tests/test_ui_journeys.py` | three route strings `/` -> `/classic` | real-journey API records |
| `src/quant_system/server/static/index.html` | version strings v1.0.0 -> v2.0.0 (three) | UI records |
| `quantos_studio.py` | single-instance lock + native window via `quant_system.shell`; the pywebview block replaced | 2026-09-25 studio records (uncommitted edits exist in the install root) |
| `src/quant_system/__init__.py`, `pyproject.toml` | version 2.0.0; `pywebview>=5.4` (win32) | release records |
| `uv.lock` | +pywebview 6.2.1, pythonnet 3.2.0, clr-loader, cffi, pycparser, proxy-tools, bottle; quant-system 2.0.0 | release-manifest-integrity, verifier-release |
| `scripts/build-windows-release.ps1` | frontend build step (needs Node) and `-SkipFrontend` | release-manifest-integrity |
| `tests/test_windows_installer.py` | packaging-contract tests | none |

Numbers this merge changes: the repository test count (+149 new tests on the branch), the
`uv.lock` SHA-256, the package version in every SBOM/manifest, and the number of mypy source files.
`main` at e787ac462 measured 1,519 tests in `CURRENT.md`; the branch measured 2,108 passed at its own
HEAD before the last three test files were added.
