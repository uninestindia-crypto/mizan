<#
    .SYNOPSIS
    Cross-references live Git workspaces against the active work records that are supposed to claim
    them, and fails when the two disagree.

    .DESCRIPTION
    Read-only. Never moves, creates, or deletes anything.

    Enforces agent_context/PROTOCOL.md section 8. A claim is only real where every agent can see it,
    so the install root's agent_context/work/active/ is the single authoritative place to look. A
    record living inside a worktree is invisible from here and therefore claims nothing.

    Two violation classes, both exit 1:

      UNCLAIMED  a registered worktree or non-default branch that no active record names. Treat it
                 as a live agent whose claim you cannot see. Never remove, prune, delete, or merge
                 it on the strength of this finding.
      STALE      an active record naming a worktree path that no longer exists. The owning agent
                 must update or complete its record.

    .EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts/audit-agent-claims.ps1

    .EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts/audit-agent-claims.ps1 -DefaultBranch master
#>
param(
    [string]$DefaultBranch = "main"
)

$ErrorActionPreference = "Stop"
Import-Module (Join-Path $PSScriptRoot "quantos-layout.psm1") -Force

$layout = Get-QuantOsLayout -ModuleRoot $PSScriptRoot
$installRoot = $layout.InstallRoot
$activeDir = Join-Path $installRoot "agent_context\work\active"

Write-Host "QuantOS agent claim audit"
Write-Host "  install root : $installRoot"
Write-Host "  active records: $activeDir"
Write-Host ""

# --- collect claims -------------------------------------------------------------------------
$records = @()
if (Test-Path -LiteralPath $activeDir) {
    $records = @(Get-ChildItem -LiteralPath $activeDir -Filter "*.md" -File)
}

$claims = @()
foreach ($record in $records) {
    $line = Select-String -LiteralPath $record.FullName -Pattern "^WORKTREE_OR_BRANCH:" |
        Select-Object -First 1
    $claimed = if ($null -eq $line) { "" } else { $line.Line }
    $claims += [pscustomobject]@{
        Record = $record.Name
        Raw    = $claimed
    }
}

Write-Host "Active records"
if ($claims.Count -eq 0) {
    Write-Host "  none"
} else {
    foreach ($claim in $claims) {
        $shown = if ([string]::IsNullOrWhiteSpace($claim.Raw)) { "(no WORKTREE_OR_BRANCH field)" } else { $claim.Raw.Trim() }
        Write-Host ("  {0,-58} {1}" -f $claim.Record, $shown)
    }
}
Write-Host ""

$claimText = ($claims | ForEach-Object { $_.Raw }) -join "`n"

# A claim matches a workspace when the record's WORKTREE_OR_BRANCH mentions its path or branch.
# Path comparison is leaf-based so a relocated-but-still-registered worktree still matches.
function Test-Claimed {
    param([string]$Needle)
    if ([string]::IsNullOrWhiteSpace($Needle)) { return $false }
    return $claimText -match [regex]::Escape($Needle)
}

$violations = @()

# --- registered worktrees -------------------------------------------------------------------
Write-Host "Registered worktrees"
$worktrees = @(Get-QuantOsRegisteredWorktrees -InstallRoot $installRoot |
    Where-Object { (ConvertTo-ComparablePath -Path $_) -ne (ConvertTo-ComparablePath -Path $installRoot) })

if ($worktrees.Count -eq 0) {
    Write-Host "  none beyond the install root"
} else {
    foreach ($worktree in $worktrees) {
        $leaf = Split-Path -Path $worktree -Leaf
        if ((Test-Claimed -Needle $worktree) -or (Test-Claimed -Needle $leaf)) {
            Write-Host ("  OK        {0}" -f $worktree)
        } else {
            Write-Host ("  UNCLAIMED {0}" -f $worktree)
            $violations += "UNCLAIMED worktree: $worktree"
        }
    }
}
Write-Host ""

# --- local branches -------------------------------------------------------------------------
Write-Host "Local branches"
$branches = @()
$branchOutput = & git -C $installRoot branch --format="%(refname:short)" 2>$null
if ($LASTEXITCODE -eq 0) {
    $branches = @($branchOutput | ForEach-Object { $_.Trim() } |
        Where-Object { $_ -and $_ -ne $DefaultBranch })
}

if ($branches.Count -eq 0) {
    Write-Host "  none beyond $DefaultBranch"
} else {
    foreach ($branch in $branches) {
        if (Test-Claimed -Needle $branch) {
            Write-Host ("  OK        {0}" -f $branch)
        } else {
            Write-Host ("  UNCLAIMED {0}" -f $branch)
            $violations += "UNCLAIMED branch: $branch"
        }
    }
}
Write-Host ""

# --- stale claims ---------------------------------------------------------------------------
Write-Host "Claims naming a workspace"
$staleFound = $false
foreach ($claim in $claims) {
    if ([string]::IsNullOrWhiteSpace($claim.Raw)) { continue }
    foreach ($match in [regex]::Matches($claim.Raw, '[A-Za-z]:\\[^\s`"'']+')) {
        $path = $match.Value.TrimEnd('.', ',', '`', '"', "'")
        if ((ConvertTo-ComparablePath -Path $path) -eq (ConvertTo-ComparablePath -Path $installRoot)) {
            continue
        }
        $staleFound = $true
        if (Test-Path -LiteralPath $path) {
            Write-Host ("  OK    {0} -> {1}" -f $claim.Record, $path)
        } else {
            Write-Host ("  STALE {0} -> {1} (missing)" -f $claim.Record, $path)
            $violations += "STALE claim in $($claim.Record): $path no longer exists"
        }
    }
}
if (-not $staleFound) {
    Write-Host "  none reference a workspace outside the install root"
}
Write-Host ""

# --- result ---------------------------------------------------------------------------------
if ($violations.Count -eq 0) {
    Write-Host "RESULT: PASS - every workspace has a visible claim and every claim resolves."
    exit 0
}

Write-Host "RESULT: FAIL - $($violations.Count) finding(s)."
foreach ($violation in $violations) {
    Write-Host "  $violation"
}
Write-Host ""
if ($violations | Where-Object { $_ -like "UNCLAIMED*" }) {
    Write-Host "An UNCLAIMED workspace is a live agent whose claim you cannot see. Per PROTOCOL"
    Write-Host "section 8.3, do not remove, prune, delete, or merge it. Record the observation and"
    Write-Host "make contact. If the workspace is yours, write the claim in the install root."
}
if ($violations | Where-Object { $_ -like "STALE*" }) {
    Write-Host "A STALE claim means the owning agent must update or complete its own record."
    Write-Host "Do not delete another agent's record to clear this."
}
exit 1
