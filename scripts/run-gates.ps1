<#
.SYNOPSIS
    Run every repository gate locally, in the same order and at the same strictness as CI.

.DESCRIPTION
    ci/gates-workflow.yml cannot be activated yet: pushing to .github/workflows/ needs a token with
    the `workflow` OAuth scope, which this environment's token lacks. That block is about hosting
    the gate, not about the gate itself -- so this runs the identical command set on demand.

    Use it before pushing, before claiming a tree is green, and before citing any figure as a gate
    result. It is also the fallback if CI is never activated, because branch protection needs a paid
    plan on a private repository and may not arrive.

    Every step here matches a step in ci/gates-workflow.yml. If you change one, change both, or the
    local answer and the CI answer stop meaning the same thing.

.PARAMETER SkipSlow
    Skip the reverse-order suite, which roughly doubles runtime. Use it for a fast inner loop, never
    for a result you intend to cite -- reverse order is what catches tests that only pass because an
    earlier test left state behind.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts/run-gates.ps1
    powershell -ExecutionPolicy Bypass -File scripts/run-gates.ps1 -SkipSlow
#>

param([switch]$SkipSlow)

$ErrorActionPreference = "Continue"
$results = [System.Collections.ArrayList]::new()
$python = if (Test-Path ".venv/Scripts/python.exe") { ".venv/Scripts/python.exe" } else { "python" }

function Invoke-Gate {
    param([string]$Name, [scriptblock]$Command, [switch]$Optional)

    Write-Host ""
    Write-Host "--- $Name" -ForegroundColor Cyan
    & $Command 2>&1 | ForEach-Object { Write-Host "    $_" }
    $code = $LASTEXITCODE

    $status = if ($code -eq 0) { "PASS" } elseif ($Optional) { "SKIP" } else { "FAIL" }
    [void]$results.Add([pscustomobject]@{ Gate = $Name; Status = $status; Exit = $code })
}

Write-Host "QuantOS repository gates" -ForegroundColor White
Write-Host "Mirrors ci/gates-workflow.yml. Interpreter: $python"

Invoke-Gate "Ruff lint"        { & $python -m ruff check . }
Invoke-Gate "Ruff format"      { & $python -m ruff format --check . }
Invoke-Gate "Strict mypy"      { & $python -m mypy src launcher.py scripts }
Invoke-Gate "Tests, normal"    { & $python -m pytest tests/ -q --no-header }

if (-not $SkipSlow) {
    Invoke-Gate "Tests, reverse" {
        $files = Get-ChildItem tests/test_*.py | Sort-Object Name -Descending | ForEach-Object { $_.FullName }
        & $python -m pytest @files -q --no-header
    }
} else {
    [void]$results.Add([pscustomobject]@{ Gate = "Tests, reverse"; Status = "SKIP"; Exit = 0 })
    Write-Host ""
    Write-Host "--- Tests, reverse  SKIPPED by -SkipSlow. Do not cite this run as a gate result." -ForegroundColor Yellow
}

Invoke-Gate "Craft self-tests" {
    node scripts/check-code.mjs --self-test
    if ($LASTEXITCODE -eq 0) { node scripts/check-tests.mjs --self-test }
}
Invoke-Gate "Claim audit"      { powershell -ExecutionPolicy Bypass -File scripts/audit-agent-claims.ps1 }
Invoke-Gate "Disk layout"      { powershell -ExecutionPolicy Bypass -File scripts/audit-disk-layout.ps1 }
Invoke-Gate "Evidence inventory" { & $python scripts/evidence_manifest.py --check } -Optional

Write-Host ""
Write-Host "SUMMARY" -ForegroundColor White
$results | ForEach-Object {
    $colour = switch ($_.Status) { "PASS" { "Green" } "FAIL" { "Red" } default { "Yellow" } }
    Write-Host ("  {0,-22} {1}" -f $_.Gate, $_.Status) -ForegroundColor $colour
}

$failed = @($results | Where-Object { $_.Status -eq "FAIL" })
Write-Host ""
if ($failed.Count -gt 0) {
    Write-Host "$($failed.Count) gate(s) FAILED. This tree is not green." -ForegroundColor Red
    exit 1
}
Write-Host "All gates pass." -ForegroundColor Green
exit 0
