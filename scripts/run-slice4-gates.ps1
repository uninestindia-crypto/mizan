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
    # The focused suite is selected by pattern, not by an explicit file list. An explicit list
    # silently excludes every test file added after it was written, which is how the Blocker 2,
    # Blocker 3 and Major 2 regressions all ended up outside this gate while it still reported
    # green. Patterns fail open into the suite rather than out of it.
    $focusedPatterns = @(
        "test_modeling_*.py",
        "test_multiplicity.py",
        "test_evidence_publish_atomicity.py"
    )
    $testsRoot = Join-Path $projectRoot "tests"
    $focusedTests = @(
        foreach ($pattern in $focusedPatterns) {
            Get-ChildItem -Path $testsRoot -Filter $pattern -File |
                ForEach-Object { "tests/$($_.Name)" }
        }
    ) | Sort-Object -Unique
    if ($focusedTests.Count -eq 0) {
        throw "Focused Slice 4 suite matched no test files under $testsRoot"
    }
    Write-Host "[gate] Slice 4 focused tests ($($focusedTests.Count) files)"
    & $python -m pytest @focusedTests -q
    if ($LASTEXITCODE -ne 0) {
        throw "Slice 4 focused tests failed with exit code $LASTEXITCODE"
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

    Invoke-Gate "Slice 4 Code Craft" {
        node scripts/check-code.mjs `
            src/quant_system/modeling `
            src/quant_system/data/market_data_evidence.py
    }
    Invoke-Gate "Slice 4 Test Craft" {
        node scripts/check-tests.mjs `
            tests/modeling_fixtures.py `
            tests/modeling_training_fixtures.py `
            tests/test_modeling_features.py `
            tests/test_modeling_labels.py `
            tests/test_modeling_partitions.py `
            tests/test_modeling_provider_replay.py `
            tests/test_modeling_preprocessing.py `
            tests/test_modeling_ridge.py `
            tests/test_modeling_metrics.py `
            tests/test_modeling_trials.py `
            tests/test_modeling_validation.py `
            tests/test_modeling_training_replay.py
    }
} finally {
    Pop-Location
}

Write-Host "Slice 4 gates passed."
