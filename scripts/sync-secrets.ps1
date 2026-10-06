# QuantOS / Mizan Safe GitHub Secrets Sync Tool
# Syncs local gitignored .env to GitHub Codespaces & Actions encrypted secrets
# Zero credentials or secret values are ever printed or committed to Git.

[CmdletBinding()]
param(
    [Parameter()]
    [string]$Repo = "uninestindia-crypto/mizan",

    [Parameter()]
    [ValidateSet("all", "codespaces", "actions")]
    [string]$Target = "all",

    [Parameter()]
    [string]$EnvFile = ".env"
)

$ErrorActionPreference = "Stop"
$projectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$envPath = Join-Path $projectRoot $EnvFile

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " QuantOS / Mizan Safe Secrets Sync" -ForegroundColor Cyan
Write-Host " Target Repo: $Repo" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Pre-flight checks
if (-not (Test-Path -LiteralPath $envPath)) {
    Write-Error "ERROR: Environment file not found at: $envPath"
    exit 1
}

$ghCmd = Get-Command gh -ErrorAction SilentlyContinue
if (-not $ghCmd) {
    Write-Error "ERROR: GitHub CLI ('gh') is not installed or not in PATH."
    exit 1
}

# Verify gh authentication
$authStatus = & gh auth status 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Error "ERROR: GitHub CLI is not authenticated. Run 'gh auth login' first."
    exit 1
}

# Count valid key-value pairs without revealing any secret values
$keyLines = Get-Content -LiteralPath $envPath | Where-Object { $_ -match "^[A-Za-z0-9_]+=" }
$keyCount = ($keyLines | Measure-Object).Count

Write-Host "[INFO] Found $keyCount variables in $EnvFile." -ForegroundColor Green
Write-Host "[INFO] Encrypting and uploading to GitHub encrypted vault..." -ForegroundColor Yellow

# 2. Upload to GitHub Secrets
try {
    if ($Target -in @("all", "codespaces")) {
        Write-Host "  -> Syncing to GitHub Codespaces secrets..." -ForegroundColor Gray
        & gh secret set -f $envPath --app codespaces --repo $Repo
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to set Codespaces secrets."
        }
        Write-Host "  [OK] Codespaces secrets updated successfully." -ForegroundColor Green
    }

    if ($Target -in @("all", "actions")) {
        Write-Host "  -> Syncing to GitHub Actions secrets..." -ForegroundColor Gray
        & gh secret set -f $envPath --app actions --repo $Repo
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to set Actions secrets."
        }
        Write-Host "  [OK] Actions secrets updated successfully." -ForegroundColor Green
    }

    Write-Host "`n[SUCCESS] All $keyCount secrets are synced and encrypted in GitHub." -ForegroundColor Green
    Write-Host "[VERIFY] Current encrypted secrets on GitHub:" -ForegroundColor Cyan
    & gh secret list --app codespaces --repo $Repo

} catch {
    Write-Error "Secret sync failed: $_"
    exit 1
}
