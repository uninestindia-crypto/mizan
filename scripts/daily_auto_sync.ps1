# QuantOS Daily Automated Git Commit, Sync, and Push Script
# Runs daily to synchronize all changes, training data, models, and context to the private GitHub repository.

param(
    [switch]$Force
)

$ErrorActionPreference = "Continue"
$projectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
Set-Location $projectRoot

$logsDir = Join-Path $projectRoot "logs"
if (-not (Test-Path -LiteralPath $logsDir)) {
    New-Item -ItemType Directory -Path $logsDir -Force | Out-Null
}
$logFile = Join-Path $logsDir "auto_sync.log"

function Write-Log {
    param([string]$Message)
    $timestamp = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss zzz")
    $line = "[$timestamp] $Message"
    Write-Host $line
    Add-Content -Path $logFile -Value $line -Encoding utf8
}

Write-Log "=== Starting QuantOS Daily Auto-Sync ==="

# 1. Verify Git repository and remote
$remoteUrl = git config --get remote.origin.url
if (-not $remoteUrl) {
    Write-Log "ERROR: No git remote 'origin' configured. Aborting sync."
    exit 1
}
Write-Log "Remote origin: $remoteUrl"

# 2. Fetch latest changes from remote
Write-Log "Fetching remote changes..."
git fetch origin main 2>&1 | Out-String | ForEach-Object { if ($_.Trim()) { Write-Log "  $_" } }

# 3. Check for local modifications or untracked files
$statusOutput = git status --porcelain
if ($statusOutput) {
    Write-Log "Local changes detected:"
    $statusOutput | Out-String | ForEach-Object { if ($_.Trim()) { Write-Log "  $_" } }

    # Stage all tracked and new files (strictly respects .gitignore)
    Write-Log "Staging changes (respecting .gitignore)..."
    git add -A

    $changeSummary = (git diff --staged --stat | Out-String).Trim()
    $timestamp = (Get-Date).ToUniversalTime().ToString("yyyy-MM-dd HH:mm:ss 'UTC'")
    $commitMsg = "sync: daily automated checkpoint [$timestamp]"

    Write-Log "Creating commit: $commitMsg"
    git commit -m $commitMsg 2>&1 | Out-String | ForEach-Object { if ($_.Trim()) { Write-Log "  $_" } }
} else {
    Write-Log "No local changes to commit. Working tree is clean."
}

# 4. Pull and rebase against remote main to prevent divergence
Write-Log "Synchronizing with origin/main..."
$pullResult = git pull --rebase --autostash origin main 2>&1 | Out-String
Write-Log "Pull result: $pullResult"

# 5. Push all commits to remote
Write-Log "Pushing to remote origin main..."
$pushResult = git push origin main 2>&1 | Out-String
Write-Log "Push result: $pushResult"

if ($LASTEXITCODE -eq 0) {
    Write-Log "=== QuantOS Daily Auto-Sync Completed Successfully ==="
    exit 0
} else {
    Write-Log "WARNING: Push exited with code $LASTEXITCODE"
    exit $LASTEXITCODE
}
