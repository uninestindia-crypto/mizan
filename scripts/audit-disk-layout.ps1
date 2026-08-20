<#
    .SYNOPSIS
    Reports every QuantOS directory on the install drive and fails when any of them violates the
    layout contract in agent_context/DISK-LAYOUT.md.

    .DESCRIPTION
    Read-only. Never moves, creates, or deletes anything. Exits 1 when a violation is found so it
    can gate a slice, a handoff, or a scheduled job.

    .EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts/audit-disk-layout.ps1

    .EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts/audit-disk-layout.ps1 -Fast
#>
param(
    [switch]$Fast
)

$ErrorActionPreference = "Stop"
Import-Module (Join-Path $PSScriptRoot "quantos-layout.psm1") -Force

$layout = Get-QuantOsLayout -ModuleRoot $PSScriptRoot
$includeSize = -not $Fast

Write-Host "QuantOS disk layout audit"
Write-Host "  install root    : $($layout.InstallRoot)"
Write-Host "  workspaces root : $($layout.WorkspacesRoot)"
Write-Host ""

Write-Host "Canonical roots"
foreach ($entry in @($layout.InstallRoot, $layout.WorkspacesRoot)) {
    if (Test-Path -LiteralPath $entry) {
        $size = "not measured"
        if ($includeSize) { $size = Format-QuantOsSize -Bytes (Get-QuantOsDirectorySize -Path $entry) }
        Write-Host ("  OK      {0}  ({1})" -f $entry, $size)
    }
    else {
        Write-Host ("  MISSING {0}" -f $entry)
    }
}
Write-Host ""

Write-Host "Workspace buckets"
foreach ($bucket in (Get-QuantOsBucketNames)) {
    $path = Join-Path $layout.WorkspacesRoot $bucket
    if (Test-Path -LiteralPath $path) {
        $count = (Get-ChildItem -LiteralPath $path -Directory -Force -ErrorAction SilentlyContinue |
            Measure-Object).Count
        $size = "not measured"
        if ($includeSize) { $size = Format-QuantOsSize -Bytes (Get-QuantOsDirectorySize -Path $path) }
        Write-Host ("  {0,-20} {1,3} entries  ({2})" -f $bucket, $count, $size)
    }
    else {
        Write-Host ("  {0,-20} absent" -f $bucket)
    }
}
Write-Host ""

Write-Host "Registered Git worktrees"
foreach ($worktree in (Get-QuantOsRegisteredWorktrees -InstallRoot $layout.InstallRoot)) {
    $key = ConvertTo-ComparablePath -Path $worktree
    $installKey = ConvertTo-ComparablePath -Path $layout.InstallRoot
    $bucketKey = ConvertTo-ComparablePath -Path $layout.WorktreesBucket
    if ($key -eq $installKey -or $key.StartsWith($bucketKey + "\")) {
        Write-Host ("  OK    {0}" -f $worktree)
    }
    else {
        Write-Host ("  STRAY {0}" -f $worktree)
    }
}
Write-Host ""

$strays = @(Get-QuantOsStrayPaths -Layout $layout -IncludeSize:$includeSize)
if ($strays.Count -eq 0) {
    Write-Host "RESULT: PASS - no stray QuantOS directories."
    exit 0
}

Write-Host ("RESULT: FAIL - {0} layout violation(s)." -f $strays.Count)
Write-Host ""
foreach ($stray in $strays) {
    $size = "not measured"
    if ($includeSize) { $size = Format-QuantOsSize -Bytes $stray.Bytes }
    Write-Host ("  [{0}] {1}  ({2})" -f $stray.Kind, $stray.Path, $size)
    if ($stray.IsWorktree) {
        Write-Host "      registered Git worktree - relocate only with 'git worktree move', never a file move"
    }
    elseif ($stray.ContainsWorktree) {
        Write-Host "      contains a registered Git worktree - relocate the inner worktree with 'git worktree move' first"
    }
    elseif ($stray.IsGitClone) {
        Write-Host "      independent clone - safe to move into verification_clones"
    }
    else {
        Write-Host "      not a clone - belongs in scratch"
    }
}
Write-Host ""
Write-Host "Fix with: powershell -ExecutionPolicy Bypass -File scripts/organize-disk-layout.ps1 -Apply"
exit 1
