# Shared disk-layout contract for QuantOS.
# Imported by audit-disk-layout.ps1, organize-disk-layout.ps1, and new-workspace-clone.ps1.
# The layout itself is documented in agent_context/DISK-LAYOUT.md.

Set-StrictMode -Version Latest

function Get-QuantOsLayout {
    <#
        .SYNOPSIS
        Resolves the canonical QuantOS layout from the location of this module.
    #>
    param(
        [string]$ModuleRoot = $PSScriptRoot
    )

    $installRoot = [System.IO.Path]::GetFullPath((Join-Path $ModuleRoot ".."))
    $driveRoot = [System.IO.Path]::GetPathRoot($installRoot)
    $installLeaf = Split-Path -Path $installRoot -Leaf
    $workspacesRoot = Join-Path $driveRoot ($installLeaf + "_workspaces")

    return [pscustomobject]@{
        InstallRoot         = $installRoot
        DriveRoot           = $driveRoot
        InstallLeaf         = $installLeaf
        WorkspacesRoot      = $workspacesRoot
        ClonesBucket        = Join-Path $workspacesRoot "verification_clones"
        WorktreesBucket     = Join-Path $workspacesRoot "worktrees"
        ScratchBucket       = Join-Path $workspacesRoot "scratch"
        ArchiveBucket       = Join-Path $workspacesRoot "archive"
    }
}

function Get-QuantOsBucketNames {
    return @("verification_clones", "worktrees", "scratch", "archive")
}

function ConvertTo-ComparablePath {
    param([Parameter(Mandatory = $true)][string]$Path)

    $full = [System.IO.Path]::GetFullPath($Path)
    return $full.Replace("/", "\").TrimEnd("\").ToLowerInvariant()
}

function Get-QuantOsDirectorySize {
    param([Parameter(Mandatory = $true)][string]$Path)

    $measured = Get-ChildItem -LiteralPath $Path -Recurse -File -Force -ErrorAction SilentlyContinue |
        Measure-Object -Property Length -Sum
    # An empty directory yields no measurement object at all in Windows PowerShell 5.1, and
    # dereferencing it under Set-StrictMode throws. Treat both empty cases as zero bytes.
    if ($null -eq $measured) {
        return 0L
    }
    if ($null -eq $measured.Sum) {
        return 0L
    }
    return [int64]$measured.Sum
}

function Format-QuantOsSize {
    param([Parameter(Mandatory = $true)][int64]$Bytes)

    if ($Bytes -ge 1GB) { return "{0:N1} GB" -f ($Bytes / 1GB) }
    if ($Bytes -ge 1MB) { return "{0:N0} MB" -f ($Bytes / 1MB) }
    if ($Bytes -ge 1KB) { return "{0:N0} KB" -f ($Bytes / 1KB) }
    return "$Bytes B"
}

function Get-QuantOsRegisteredWorktrees {
    <#
        .SYNOPSIS
        Returns every path Git currently registers as a worktree of the install root.
        These must never be relocated with a plain file move.
    #>
    param([Parameter(Mandatory = $true)][string]$InstallRoot)

    $paths = @()
    $output = & git -C $InstallRoot worktree list --porcelain 2>$null
    if ($LASTEXITCODE -ne 0) {
        return $paths
    }
    foreach ($line in $output) {
        if ($line -like "worktree *") {
            $paths += [System.IO.Path]::GetFullPath($line.Substring(9).Trim())
        }
    }
    return $paths
}

function Get-QuantOsStrayPaths {
    <#
        .SYNOPSIS
        Finds every QuantOS directory that violates the layout contract.

        .DESCRIPTION
        Two violation classes are reported:
          RootStray    - a directory at the drive root whose name starts with the install leaf
                         but which is neither the install root nor the workspaces root.
          MisfiledItem - a directory directly under the workspaces root that is not one of the
                         approved buckets.
        Each result records whether Git registers the path as a worktree, because a registered
        worktree may only be relocated with `git worktree move`.
    #>
    param(
        [Parameter(Mandatory = $true)]$Layout,
        [switch]$IncludeSize
    )

    $results = @()
    $installKey = ConvertTo-ComparablePath -Path $Layout.InstallRoot
    $workspacesKey = ConvertTo-ComparablePath -Path $Layout.WorkspacesRoot
    $worktreeKeys = @()
    foreach ($w in (Get-QuantOsRegisteredWorktrees -InstallRoot $Layout.InstallRoot)) {
        $worktreeKeys += (ConvertTo-ComparablePath -Path $w)
    }
    $buckets = Get-QuantOsBucketNames

    $rootChildren = Get-ChildItem -LiteralPath $Layout.DriveRoot -Directory -Force -ErrorAction SilentlyContinue
    foreach ($child in $rootChildren) {
        if ($child.Name -notlike ($Layout.InstallLeaf + "*")) { continue }
        $key = ConvertTo-ComparablePath -Path $child.FullName
        if ($key -eq $installKey -or $key -eq $workspacesKey) { continue }

        $results += New-QuantOsStray -Path $child.FullName -Kind "RootStray" `
            -WorktreeKeys $worktreeKeys -IncludeSize:$IncludeSize
    }

    if (Test-Path -LiteralPath $Layout.WorkspacesRoot) {
        $workspaceChildren = Get-ChildItem -LiteralPath $Layout.WorkspacesRoot -Directory -Force -ErrorAction SilentlyContinue
        foreach ($child in $workspaceChildren) {
            if ($buckets -contains $child.Name) { continue }
            $results += New-QuantOsStray -Path $child.FullName -Kind "MisfiledItem" `
                -WorktreeKeys $worktreeKeys -IncludeSize:$IncludeSize
        }
    }

    return $results
}

function New-QuantOsStray {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Kind,
        [Parameter(Mandatory = $true)][AllowEmptyCollection()][string[]]$WorktreeKeys,
        [switch]$IncludeSize
    )

    $key = ConvertTo-ComparablePath -Path $Path
    $isWorktree = $WorktreeKeys -contains $key
    $containsWorktree = $false
    foreach ($w in $WorktreeKeys) {
        if ($w.StartsWith($key + "\")) { $containsWorktree = $true }
    }

    $bytes = -1L
    if ($IncludeSize) {
        $bytes = Get-QuantOsDirectorySize -Path $Path
    }

    return [pscustomobject]@{
        Path             = $Path
        Kind             = $Kind
        IsWorktree       = $isWorktree
        ContainsWorktree = $containsWorktree
        IsGitClone       = (Test-Path -LiteralPath (Join-Path $Path ".git"))
        Bytes            = $bytes
    }
}

Export-ModuleMember -Function Get-QuantOsLayout, Get-QuantOsBucketNames, ConvertTo-ComparablePath,
    Get-QuantOsDirectorySize, Format-QuantOsSize, Get-QuantOsRegisteredWorktrees,
    Get-QuantOsStrayPaths, New-QuantOsStray
