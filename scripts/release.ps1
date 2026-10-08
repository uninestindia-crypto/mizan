<#
.SYNOPSIS
  Cut a QuantOS release: bump the version everywhere, build the installer, tag, and publish on GitHub.

.DESCRIPTION
  This is the standing release routine (agent_context/decisions/20261004-release-cadence.md). Run it when
  `python scripts/release_status.py` says a release is due, or when the founder asks for one.

  Steps: check the tree and `gh` -> decide the version -> run the gates -> bump every version file ->
  commit "chore(release): vX.Y.Z" -> build the installer from that commit -> checksums and notes ->
  tag -> push -> `gh release create` with the installer, the portable zip, the SBOM and the checksums.

  The installed app then shows an "update available" notice (within hours, or at once from
  Settings > About > Check now).

.PARAMETER Version
  Explicit X.Y.Z. Without it the version is chosen from the commits since the last tag.
.PARAMETER Bump
  major | minor | patch. Overrides the suggestion when no -Version is given.
.PARAMETER Force
  Release even though release_status says none is due.
.PARAMETER DryRun
  Print the plan (version, notes) and stop before changing anything.
.PARAMETER NoPublish
  Do everything locally (bump, commit, build, tag) but do not push or publish.
.PARAMETER SkipTests
  Skip the lint, type and test gates. Only for a release made right after the gates were run.
.PARAMETER CoAuthor
  A "Co-Authored-By: ..." trailer line to add to the release commit.
#>
param(
    [string]$Version = "",
    [ValidateSet("", "major", "minor", "patch")][string]$Bump = "",
    [switch]$Force,
    [switch]$DryRun,
    [switch]$NoPublish,
    [switch]$SkipTests,
    [string]$CoAuthor = ""
)

$ErrorActionPreference = "Stop"
$root = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
Push-Location $root

function Step($text) { Write-Host "`n== $text" -ForegroundColor Cyan }
function Fail($text) { Write-Host "`nRELEASE STOPPED: $text" -ForegroundColor Red; Pop-Location; exit 1 }
function Native($label) { if ($LASTEXITCODE -ne 0) { Fail "$label failed (exit code $LASTEXITCODE)." } }

$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) { $python = "python" }

try {
    # ------------------------------------------------------------------ 1. preconditions
    Step "Checking the repository"
    $branch = (git rev-parse --abbrev-ref HEAD).Trim()
    if ($branch -ne "main") { Fail "Releases are cut from main; this is '$branch'." }
    $dirty = git status --porcelain --untracked-files=no
    if ($dirty) { Fail "There are uncommitted changes to tracked files. Commit or stash them first:`n$dirty" }
    git fetch origin main --quiet; Native "git fetch"
    $behind = [int](git rev-list --count HEAD..origin/main)
    if ($behind -gt 0) { Fail "main is $behind commit(s) behind origin/main. Pull first." }
    if (-not $DryRun -and -not $NoPublish) {
        gh auth status *> $null
        if ($LASTEXITCODE -ne 0) { Fail "The GitHub CLI is not signed in. Run: gh auth login" }
    }

    # ------------------------------------------------------------------ 2. is a release due, and which version
    Step "Deciding the version"
    $status = (& $python scripts/release_status.py --json) | ConvertFrom-Json; Native "release_status"
    Write-Host ("Last release: {0}; user-visible changes since: {1}; due: {2}" -f $status.last_tag, $status.user_visible, $status.due)
    if (-not $status.due -and -not $Force) { Fail "No release is due yet. Use -Force to release anyway." }
    $problems = & $python scripts/bump_version.py --check
    if ($LASTEXITCODE -eq 0) { $problems = $null }  # exit 0 means the files already agree
    if (-not $Version) {
        $kind = if ($Bump) { $Bump } else { $status.suggested_bump }
        $Version = (& $python scripts/bump_version.py --next $kind).Trim(); Native "bump_version --next"
    }
    if ($Version -notmatch '^\d+\.\d+\.\d+$') { Fail "'$Version' is not a version like 2.1.0." }
    $tag = "v$Version"
    if (git tag --list $tag) { Fail "Tag $tag already exists." }
    $notes = (& $python scripts/release_notes.py $Version --since $status.last_tag) -join "`n"
    Write-Host "`nVersion: $Version  (previous: $($status.last_tag))"
    if ($problems) { Write-Host "Version files that disagree today (the bump will make them agree):`n$($problems -join "`n")" -ForegroundColor Yellow }
    Write-Host "`n----- release notes -----`n$notes`n-------------------------"
    if ($DryRun) { Write-Host "`nDry run: nothing was changed." -ForegroundColor Green; Pop-Location; exit 0 }

    # ------------------------------------------------------------------ 3. gates
    if (-not $SkipTests) {
        Step "Gates: lint, types, tests (tracked files only, so another agent's unfinished file cannot block this)"
        $tracked = @(git ls-files "*.py")
        # --force-exclude keeps pyproject's excludes (.agents, dist, ...) in force for an explicit file list, as in CI.
        & $python -m ruff check --force-exclude @tracked; Native "ruff check"
        & $python -m ruff format --check --force-exclude @tracked; Native "ruff format"
        $typed = @(git ls-files "src/*.py" "scripts/*.py" "launcher.py")
        & $python -m mypy @typed; Native "mypy"
        & $python -m pytest tests -q -p no:cacheprovider; Native "pytest"
    } else {
        Write-Host "`nGates skipped (-SkipTests)." -ForegroundColor Yellow
    }

    # ------------------------------------------------------------------ 4. bump and commit
    Step "Bumping every version file to $Version"
    & $python scripts/bump_version.py $Version; Native "bump_version"
    $carriers = @("pyproject.toml", "src/quant_system/__init__.py", "frontend/package.json", "frontend/package-lock.json",
                  "src/quant_system/server/static/index.html", "uv.lock") | Where-Object { Test-Path -LiteralPath $_ }
    git add -- @carriers
    $message = "chore(release): v$Version`n`nRelease $Version. See the GitHub release notes for what changed."
    if ($CoAuthor) { $message += "`n`n$CoAuthor" }
    git commit -q -m $message; Native "git commit"
    $sha = (git rev-parse --short HEAD).Trim()
    Write-Host "Committed $sha"

    # ------------------------------------------------------------------ 5. build from the release commit
    Step "Building the installer (this takes several minutes)"
    & (Join-Path $PSScriptRoot "build-windows-release.ps1"); Native "build-windows-release"
    $setup = "dist\MizanQuantOS_v${Version}_Setup.exe"
    if (-not (Test-Path -LiteralPath $setup)) {
        $setup = "dist\QuantOS_v${Version}_Setup.exe"
    }
    $zip = "dist\quantos-v${Version}-windows-x86_64.zip"
    $sbom = "dist\quantos-sbom.json"
    foreach ($artifact in @($setup, $zip, $sbom)) {
        if (-not (Test-Path -LiteralPath $artifact)) { Fail "The build did not produce $artifact." }
    }
    $sums = "dist\SHA256SUMS-v$Version.txt"
    $lines = foreach ($artifact in @($setup, $zip, $sbom)) {
        "{0}  {1}" -f (Get-FileHash -Algorithm SHA256 -LiteralPath $artifact).Hash.ToLower(), (Split-Path $artifact -Leaf)
    }
    Set-Content -LiteralPath $sums -Value $lines -Encoding ascii
    $notesFile = "dist\RELEASE_NOTES_v$Version.md"
    $footer = @"

## Install

Download ``QuantOS_v${Version}_Setup.exe`` and run it. The installer is not code-signed yet, so Windows SmartScreen may
ask you to confirm ("More info", then "Run anyway"). Your data and settings are kept when you update over an older install.

## Checksums (SHA-256)

``````
$($lines -join "`n")
``````
"@
    Set-Content -LiteralPath $notesFile -Value ($notes + "`n" + $footer) -Encoding utf8

    # ------------------------------------------------------------------ 6. tag and publish
    Step "Tagging $tag"
    git tag -a $tag -m "Mizan Quant OS v$Version"; Native "git tag"
    if ($NoPublish) {
        Write-Host "`n-NoPublish: built and tagged locally. To publish: git push origin main $tag ; then gh release create." -ForegroundColor Yellow
        Pop-Location; exit 0
    }
    Step "Publishing"
    git push origin main; Native "git push main"
    git push origin $tag; Native "git push tag"
    gh release create $tag $setup $zip $sbom $sums --title "Mizan Quant OS v$Version" --notes-file $notesFile --latest; Native "gh release create"
    $url = (gh release view $tag --json url -q .url)
    Write-Host "`nReleased Mizan Quant OS v$Version  $url" -ForegroundColor Green
    Write-Host "Installed apps will offer the update within hours, or at once from Settings > About > Check now."
}
catch {
    Write-Host "`nRELEASE STOPPED: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "If a release commit was made but nothing was pushed, undo it with: git reset --soft HEAD~1 (and delete a local tag with: git tag -d v$Version)."
    Pop-Location
    exit 1
}
Pop-Location
