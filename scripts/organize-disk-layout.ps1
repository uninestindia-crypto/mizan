<#
    .SYNOPSIS
    Moves stray QuantOS directories into the canonical workspace buckets defined in
    agent_context/DISK-LAYOUT.md.

    .DESCRIPTION
    Dry run by default: it prints the exact moves and changes nothing. Pass -Apply to execute.

    Safety rules this script never breaks:
      * The install root is never moved.
      * Nothing is ever deleted. Every action is a move, and a name collision aborts the move.
      * A directory Git registers as a worktree is never moved with a file operation. It is
        relocated with `git worktree move`, only when -MoveWorktrees is passed and only when its
        working tree is clean.

    .EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts/organize-disk-layout.ps1

    .EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts/organize-disk-layout.ps1 -Apply

    .EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts/organize-disk-layout.ps1 -Apply -MoveWorktrees
#>
param(
    [switch]$Apply,
    [switch]$MoveWorktrees
)

$ErrorActionPreference = "Stop"
Import-Module (Join-Path $PSScriptRoot "quantos-layout.psm1") -Force

$layout = Get-QuantOsLayout -ModuleRoot $PSScriptRoot
$mode = "DRY RUN"
if ($Apply) { $mode = "APPLY" }

Write-Host "QuantOS disk layout organizer [$mode]"
Write-Host "  install root    : $($layout.InstallRoot)"
Write-Host "  workspaces root : $($layout.WorkspacesRoot)"
Write-Host ""

$strays = @(Get-QuantOsStrayPaths -Layout $layout)
if ($strays.Count -eq 0) {
    Write-Host "Nothing to do - the layout already matches the contract."
    exit 0
}

function Resolve-TargetBucket {
    param([Parameter(Mandatory = $true)]$Stray)

    if ($Stray.IsWorktree) { return $layout.WorktreesBucket }
    if ($Stray.IsGitClone) { return $layout.ClonesBucket }
    return $layout.ScratchBucket
}

$moved = 0
$skipped = 0

foreach ($stray in $strays) {
    $bucket = Resolve-TargetBucket -Stray $stray
    $destination = Join-Path $bucket (Split-Path -Path $stray.Path -Leaf)

    Write-Host ("{0}" -f $stray.Path)
    Write-Host ("  -> {0}" -f $destination)

    if ($stray.ContainsWorktree -and -not $stray.IsWorktree) {
        Write-Host "  SKIPPED: contains a registered Git worktree. Move the inner worktree first:"
        Write-Host "           git -C `"$($layout.InstallRoot)`" worktree move <inner path> <new path>"
        $skipped++
        Write-Host ""
        continue
    }

    if ($stray.IsWorktree -and -not $MoveWorktrees) {
        Write-Host "  SKIPPED: registered Git worktree. Re-run with -MoveWorktrees once no agent is working in it."
        $skipped++
        Write-Host ""
        continue
    }

    if (Test-Path -LiteralPath $destination) {
        Write-Host "  SKIPPED: destination already exists. Resolve the name collision by hand."
        $skipped++
        Write-Host ""
        continue
    }

    if (-not $Apply) {
        Write-Host "  would move (dry run)"
        $moved++
        Write-Host ""
        continue
    }

    if (-not (Test-Path -LiteralPath $bucket)) {
        New-Item -ItemType Directory -Path $bucket -Force | Out-Null
    }

    if ($stray.IsWorktree) {
        $dirty = & git -C $stray.Path status --porcelain 2>$null
        if ($LASTEXITCODE -ne 0) {
            Write-Host "  SKIPPED: could not read Git status for the worktree."
            $skipped++
            Write-Host ""
            continue
        }
        if ($dirty) {
            Write-Host "  SKIPPED: worktree has uncommitted changes. It belongs to another agent; do not move it."
            $skipped++
            Write-Host ""
            continue
        }
        & git -C $layout.InstallRoot worktree move $stray.Path $destination
        if ($LASTEXITCODE -ne 0) {
            Write-Host "  FAILED: 'git worktree move' returned $LASTEXITCODE. Nothing was changed."
            $skipped++
            Write-Host ""
            continue
        }
        Write-Host "  moved with 'git worktree move' (registration preserved)"
        $moved++
        Write-Host ""
        continue
    }

    Move-Item -LiteralPath $stray.Path -Destination $destination -ErrorAction Stop
    Write-Host "  moved"
    $moved++
    Write-Host ""
}

Write-Host ("Summary: {0} move(s), {1} skipped." -f $moved, $skipped)
if (-not $Apply) {
    Write-Host "Dry run only. Re-run with -Apply to execute."
}
Write-Host "Verify with: powershell -ExecutionPolicy Bypass -File scripts/audit-disk-layout.ps1"
