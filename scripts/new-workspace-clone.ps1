<#
    .SYNOPSIS
    Creates a QuantOS verification clone or agent worktree in the canonical workspace bucket.

    .DESCRIPTION
    Use this instead of cloning by hand. Hand-rolled clones are what put four throwaway copies at
    the root of D:. This script always writes below the workspaces root, always uses a name that
    records purpose, label, revision, and creation time, and prints the path it created.

    Clone mode produces an independent detached clone: correct for clean-state verification and
    Red Team runs, because it cannot touch the primary checkout.

    Worktree mode produces a registered Git worktree on its own branch: correct for concurrent
    development, because it shares object storage and stays visible in `git worktree list`.

    .EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts/new-workspace-clone.ps1 -Purpose verify -Label slice4

    .EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts/new-workspace-clone.ps1 -Purpose redteam -Label slice4-final -Revision 6a17d5e

    .EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts/new-workspace-clone.ps1 -Kind Worktree -Purpose feature -Label data-provenance -Branch claude/truthful-data-source
#>
param(
    [ValidateSet("Clone", "Worktree")]
    [string]$Kind = "Clone",

    [Parameter(Mandatory = $true)]
    [ValidateSet("verify", "redteam", "mutation", "audit", "feature", "scratch")]
    [string]$Purpose,

    [Parameter(Mandatory = $true)]
    [ValidatePattern('^[a-z0-9][a-z0-9-]*$')]
    [string]$Label,

    [string]$Revision = "HEAD",

    [string]$Branch
)

$ErrorActionPreference = "Stop"
Import-Module (Join-Path $PSScriptRoot "quantos-layout.psm1") -Force

$layout = Get-QuantOsLayout -ModuleRoot $PSScriptRoot

$resolved = & git -C $layout.InstallRoot rev-parse --short=7 $Revision 2>$null
if ($LASTEXITCODE -ne 0) {
    throw "Revision is not resolvable in $($layout.InstallRoot): $Revision"
}
$shortRevision = $resolved.Trim()
$stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMdd-HHmmss")
$name = "$Purpose-$Label-$shortRevision-$stamp"

if ($Kind -eq "Worktree") {
    $bucket = $layout.WorktreesBucket
}
else {
    $bucket = $layout.ClonesBucket
}
$destination = Join-Path $bucket $name

if (-not (Test-Path -LiteralPath $bucket)) {
    New-Item -ItemType Directory -Path $bucket -Force | Out-Null
}
if (Test-Path -LiteralPath $destination) {
    throw "Destination already exists: $destination"
}

if ($Kind -eq "Worktree") {
    if (-not $Branch) {
        throw "Worktree mode requires -Branch, so the worktree never shares a branch with the primary checkout."
    }
    & git -C $layout.InstallRoot worktree add -b $Branch $destination $Revision
    if ($LASTEXITCODE -ne 0) {
        throw "'git worktree add' failed with exit code $LASTEXITCODE"
    }
}
else {
    & git clone --no-checkout $layout.InstallRoot $destination
    if ($LASTEXITCODE -ne 0) {
        throw "'git clone' failed with exit code $LASTEXITCODE"
    }
    # A fresh clone does not inherit core.longpaths and this repository has
    # evidence paths longer than 260 characters.
    & git -C $destination config core.longpaths true
    if ($LASTEXITCODE -ne 0) {
        throw "'git config core.longpaths' failed with exit code $LASTEXITCODE"
    }
    & git -C $destination -c core.longpaths=true checkout --detach $shortRevision
    if ($LASTEXITCODE -ne 0) {
        throw "'git checkout --detach' failed with exit code $LASTEXITCODE"
    }
}

Write-Host ""
Write-Host "Created $($Kind.ToLowerInvariant()): $destination"
Write-Host "  revision : $shortRevision"
if ($Branch) { Write-Host "  branch   : $Branch" }
Write-Host ""
Write-Host "Reminder: record this path in your agent_context/work/active record, and delete or"
Write-Host "archive it when the run is certified. Run scripts/audit-disk-layout.ps1 before handoff."
