# NOTICE: installer work edits two paths claimed by the release-manifest-integrity record

STATUS: ACTIVE (notice)  
FILED_BY: Claude Code, record `20260926-claude-professional-windows-installer.md`  
FILED_UTC: 2026-09-26  
AFFECTS: `20260824-1110Z-codex-release-manifest-integrity.md` (HANDOFF_REQUIRED),
`20260822-verifier-release.md` (IN_PROGRESS)

On explicit founder instruction, the install root `main` working tree gets these edits to claimed paths:

- `installer/quantos.spec`: adds `icon=` and a Windows version resource (`version=`) to both EXEs.
  Output exes change bytes; any pinned hash of `dist/quantos/*.exe` or of the release zip taken
  before this change no longer applies.
- `scripts/build-windows-release.ps1`: step 4 now compiles the Inno Setup installer
  (`scripts/build-windows-installer.ps1`) instead of the PyInstaller tkinter wizard. Steps 1-3
  (PyInstaller bundle, SBOM, manifest, zip) are untouched.

The codex branch `codex/release-manifest-integrity` also edits both files; expect a textual merge
conflict in step 4 and the EXE blocks. Nothing on that branch or in its worktree was touched.
