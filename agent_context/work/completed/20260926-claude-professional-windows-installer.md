# Active work: professional Windows installer (Inno Setup, icon, version info)

STATUS: COMPLETED (unsigned; signing needs the founder's certificate)  
OWNER: Claude Code session (founder-instructed: "build it then", 2026-09-26)  
TOOL: Claude Code  
STARTED_UTC: 2026-09-26  
STARTING_REVISION: d445b29f7 (main, install root, dirty tree from other sessions)  
WORKTREE_OR_BRANCH: `D:\quant_system` on `main` (shared checkout, no worktree)

## Objective

Replace the hand-drawn tkinter setup wizard as the shipped `QuantOS_v<version>_Setup.exe` with a
compiled Inno Setup installer that behaves like a first-party Windows installer.

## Owned paths

- `installer/quant_os_setup.iss` (rewritten; no active claim)
- `installer/assets/**` (new: icon + wizard images)
- `installer/quantos_version_resource.py` (new)
- `scripts/build-windows-installer.ps1` (new)
- `tests/test_windows_installer.py` (new)
- `installer/quantos.spec` — claimed by `20260824-1110Z-codex-release-manifest-integrity.md`
  (HANDOFF_REQUIRED); edited on founder instruction, additive only (icon + version resource)
- `scripts/build-windows-release.ps1` — same claim; step 4 + two params only
- `dist/**`, `build/**` (regenerated build output)
- this record, and `20260926-NOTICE-installer-build-changes-release-spec.md`

## Non-goals

- `installer/setup_gui.py` and `installer/setup_installer.spec` untouched (they carry ~450
  uncommitted lines from the 2026-09-25 sessions). They are no longer built; deleting them is the
  founder's call.
- No changes to `src/quant_system/release/**` or `tests/test_release_packaging.py`.
- No signing performed; no commit.

## Decision rationale

Inno Setup over MSI/MSIX: a script already existed, VS Code ships on it, it provides rollback,
Restart Manager, HKCU uninstall registration, /VERYSILENT and /LOG natively, and 6.7 adds
`WizardStyle=modern dynamic windows11`. MSIX would require a signing certificate before a single
test install. Default folder keeps the founder's drive-isolation intent (first *fixed*, writable,
non-system drive with >= 2 GB free) but excludes removable and network drives; otherwise
`{autopf}` (per-user Programs). The Inno version gate lives in the .iss (`#if Ver < EncodeVer(6,7,0)`)
because ISCC.exe carries no version resource (all fields read 0.0.0.0).

Only the installer and uninstaller get signed via `-SignCommand`. Signing the app exes must happen
between PyInstaller and the manifest step (step 2/3 of the release script), otherwise the manifest
hashes stop matching; not done because it is untestable without a certificate.

## Commands and outcomes

| Command | Result | Evidence/notes |
|---|---|---|
| `winget install --id JRSoftware.InnoSetup -e --scope user` | PASS | Inno Setup 6.7.3, winget hash-verified (founder approved download) |
| `scripts\build-windows-release.ps1` | Steps 1-3 PASS | 266 files, 155.62 MB, zip + SBOM + manifest regenerated at d445b29f7 |
| `scripts\build-windows-installer.ps1` | PASS | `dist\QuantOS_v1.0.0_Setup.exe` 45.8 MB (old tkinter setup: 90 MB) |
| VersionInfo on Setup, quantos-studio.exe, quantos.exe | PASS | Company/Product/Version 1.0.0/Copyright present on all three |
| Setup manifest DPI awareness | PASS | declared (old setup: absent) |
| Silent install `/VERYSILENT /DIR=<scratch>` | PASS | 7.5 s, 271 files; HKCU `..._is1` DisplayName/Version/Publisher/Icon/Size; Start menu lnk; desktop lnk on `C:\Users\teenl\OneDrive\Desktop` |
| Silent uninstall `unins000.exe /VERYSILENT` | PASS | exes, `_internal`, `tmp\`, shortcuts, registry removed; `data\` and `logs\` files kept |
| Interactive wizard screenshot at 150% scaling | PASS | crisp, native Win11 style, default `D:\QuantOS`, "At least 160.6 MB" computed |
| `pytest tests/test_windows_installer.py tests/test_release_packaging.py` | PASS | 39 passed |
| `ruff check .` / `ruff format --check .` | PASS | 759 files |
| `scripts/audit-agent-claims.ps1`, `scripts/audit-disk-layout.ps1` | PASS | exit 0 both |
| full `pytest tests/` | see Stop point | |

## Files changed

- `installer/quant_os_setup.iss`: rewritten installer
- `installer/assets/quantos.ico` (16-256 px), `wizard-large-*.png`, `wizard-small-*.png`: new
- `installer/quantos_version_resource.py`: VSVersionInfo from `quant_system.__version__`
- `installer/quantos.spec`: `icon=` + `version=` on both EXEs
- `scripts/build-windows-installer.ps1`: new; `scripts/build-windows-release.ps1`: step 4 -> Inno,
  `-SkipInstaller`, `-SignCommand`
- `tests/test_windows_installer.py`: new, 20 tests

## Blockers and conflicts

- Signing needs a code-signing certificate (or Azure Trusted Signing account) from the founder.
- Codex branch `codex/release-manifest-integrity` edits the same spec/script; NOTICE filed.

## Stop point

Installer built, installed, uninstalled and verified. Committed on `main` on founder instruction
("commit it") in the commit that moves this record to `completed/`; not pushed.

`installer/quantos.spec` in that commit also carries the `quantos-studio.exe` Analysis/EXE/COLLECT
block written by the 2026-09-25 sessions (`20260925-1043Z-implementer-windows-setup-studio-installer.md`,
COMPLETED) and never committed. The installer's Start menu target depends on it, so it could not be
split out. `quantos_studio.py`, `installer/setup_gui.py` and the other 2026-09-25 edits were left
uncommitted and untouched.

## Next safe action

Founder: obtain a signing certificate, then run
`scripts\build-windows-release.ps1 -SignCommand 'signtool sign /fd sha256 /tr <timestamp-url> /td sha256 /a $f'`.
