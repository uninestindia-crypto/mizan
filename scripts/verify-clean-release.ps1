param(
    [string]$PythonEnvironment = ".venv",
    [string]$ReleaseBundlePath = "dist/quantos",
    [string]$InstallStagingDir = "tmp/clean-install-test",
    [string]$EvidenceDir = "tmp/clean-install-evidence",
    [switch]$PreserveStaging = $false
)

$ErrorActionPreference = "Stop"
$projectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$environmentRoot = [System.IO.Path]::GetFullPath((Join-Path $projectRoot $PythonEnvironment))
$python = Join-Path $environmentRoot "Scripts\python.exe"

if (-not (Test-Path -LiteralPath $python)) {
    $python = "python"
}

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "  QuantOS Clean Release & Evidence Preservation Verification Gate" -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan

Push-Location $projectRoot
try {
    $bundleFullPath = [System.IO.Path]::GetFullPath((Join-Path $projectRoot $ReleaseBundlePath))
    if (-not (Test-Path $bundleFullPath)) {
        # Fallback to QuantOS capitalized
        $altBundle = [System.IO.Path]::GetFullPath((Join-Path $projectRoot "dist/QuantOS"))
        if (Test-Path $altBundle) {
            $bundleFullPath = $altBundle
        } else {
            throw "Release bundle not found at: $bundleFullPath"
        }
    }

    $stagingFullPath = [System.IO.Path]::GetFullPath((Join-Path $projectRoot $InstallStagingDir))
    $evidenceFullPath = [System.IO.Path]::GetFullPath((Join-Path $projectRoot $EvidenceDir))
    $lockFullPath = [System.IO.Path]::GetFullPath((Join-Path $projectRoot "uv.lock"))

    Write-Host "`n[CONFIG] Release Bundle:   $bundleFullPath" -ForegroundColor Yellow
    Write-Host "[CONFIG] Staging Install:  $stagingFullPath" -ForegroundColor Yellow
    Write-Host "[CONFIG] Evidence Root:    $evidenceFullPath" -ForegroundColor Yellow
    Write-Host "[CONFIG] Lock File:        $lockFullPath" -ForegroundColor Yellow

    $verifyScript = @"
import sys
from pathlib import Path
from quant_system.release.verifier import verify_clean_release

bundle_path = Path(r'$bundleFullPath')
staging_path = Path(r'$stagingFullPath')
evidence_path = Path(r'$evidenceFullPath')
lock_path = Path(r'$lockFullPath')

report = verify_clean_release(
    bundle_dir=bundle_path,
    install_staging_dir=staging_path,
    evidence_dir=evidence_path,
    lock_path=lock_path,
)

print('\n--- VERIFICATION STEP RESULTS ---')
for step in report.steps:
    status_tag = '[PASS]' if step.passed else '[FAIL]'
    print(f'{status_tag} {step.name}')
    print(f'       Details: {step.details}')

print('\n--- SUMMARY ---')
print(f'Total Gates:  {report.total_steps}')
print(f'Passed Gates: {report.passed_steps}')
print(f'Failed Gates: {report.failed_steps}')
print(f'Final Status: {report.summary_message}')

if not report.all_passed:
    sys.exit(1)
"@

    & $python -c "$verifyScript"
    if ($LASTEXITCODE -ne 0) {
        throw "Clean release verification FAILED with exit code $LASTEXITCODE"
    }

    if (-not $PreserveStaging) {
        Write-Host "`n[CLEANUP] Cleaning up temporary test staging directories..." -ForegroundColor DarkGray
        if (Test-Path $stagingFullPath) { Remove-Item -Recurse -Force $stagingFullPath }
        if (Test-Path $evidenceFullPath) { Remove-Item -Recurse -Force $evidenceFullPath }
        Write-Host "  -> Temporary test staging cleaned."
    }

    Write-Host "`n======================================================================" -ForegroundColor Cyan
    Write-Host "  [VERIFICATION COMPLETE] Clean Release and Evidence Preserved 100%!" -ForegroundColor Green
    Write-Host "======================================================================" -ForegroundColor Cyan

} finally {
    Pop-Location
}
