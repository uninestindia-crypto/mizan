param(
    [string]$PythonEnvironment = ".venv"
)

$ErrorActionPreference = "Stop"
$projectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$environmentRoot = [System.IO.Path]::GetFullPath((Join-Path $projectRoot $PythonEnvironment))
$python = Join-Path $environmentRoot "Scripts\python.exe"
$detectSecrets = Join-Path $environmentRoot "Scripts\detect-secrets.exe"
$vulture = Join-Path $environmentRoot "Scripts\vulture.exe"

if (-not (Test-Path -LiteralPath $python)) {
    throw "Python environment is missing: $environmentRoot"
}

function Invoke-Gate {
    param(
        [string]$Name,
        [scriptblock]$Command
    )

    Write-Host "[gate] $Name"
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Name failed with exit code $LASTEXITCODE"
    }
}

Push-Location $projectRoot
try {
    Invoke-Gate "Ruff lint" { & $python -m ruff check . }
    Invoke-Gate "Ruff format" { & $python -m ruff format --check . }
    Invoke-Gate "Strict Mypy" { & $python -m mypy src }
    Invoke-Gate "Repository tests and coverage" {
        & $python -m pytest --cov=quant_system --cov-report=term --cov-fail-under=80 -q
    }
    Invoke-Gate "Dead-code scan" {
        & $vulture src tests launcher.py installer `
            --min-confidence 80 `
            --exclude "*/test_*.py,*/__pycache__/*"
    }

    Write-Host "[gate] Application secret scan"
    $excludedSecretFiles = '(^|[\\/])(\.venv|build|dist|tmp|logs|\.git|\.agents|\.mypy_cache|\.pytest_cache|\.ruff_cache|__pycache__)([\\/]|$)|(^|[\\/])uv\.lock$|(^|[\\/])\.coverage$'
    $secretJson = & $detectSecrets scan --all-files --no-verify `
        --exclude-files $excludedSecretFiles .
    if ($LASTEXITCODE -ne 0) {
        throw "Application secret scan failed with exit code $LASTEXITCODE"
    }
    $secretScan = $secretJson | ConvertFrom-Json
    $secretCount = 0
    $secretScan.results.PSObject.Properties | ForEach-Object {
        $secretCount += @($_.Value).Count
    }
    if ($secretCount -ne 0) {
        throw "Application secret scan found $secretCount candidate secret(s)"
    }
    Write-Host "Application secret scan found 0 candidate secrets."

    Invoke-Gate "Slice 1 Code Craft" {
        node scripts/check-code.mjs `
            src/quant_system/data/market_data.py `
            src/quant_system/data/market_data_evidence.py `
            src/quant_system/data/upstox_http.py `
            src/quant_system/data/upstox_parsing.py `
            src/quant_system/data/upstox_failures.py `
            src/quant_system/data/upstox.py
    }
    Invoke-Gate "Slice 1 Test Craft" {
        node scripts/check-tests.mjs `
            tests/test_upstox_data.py `
            tests/test_upstox_v3_acquisition.py
    }
} finally {
    Pop-Location
}

Write-Host "Slice 1 gates passed."
