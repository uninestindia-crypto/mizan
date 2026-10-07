param(
    [string]$PythonEnvironment = ".venv",
    [switch]$SkipPyInstaller = $false,
    [switch]$Clean = $false,
    [switch]$SkipInstaller = $false,
    [switch]$SkipFrontend = $false,
    [string]$SignCommand = "",
    [string]$OutputDir = "dist/quantos"
)

$ErrorActionPreference = "Stop"
$projectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$environmentRoot = [System.IO.Path]::GetFullPath((Join-Path $projectRoot $PythonEnvironment))
$python = Join-Path $environmentRoot "Scripts\python.exe"

if (-not (Test-Path -LiteralPath $python)) {
    $python = "python"
}

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "  QuantOS Windows x64 Release Packaging Pipeline" -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan

Push-Location $projectRoot
try {
    # 1. Clean build artifacts if requested
    if ($Clean) {
        Write-Host "`n[STEP 1] Cleaning prior build and dist artifacts..." -ForegroundColor Yellow
        $buildDir = Join-Path $projectRoot "build"
        $distDir = Join-Path $projectRoot "dist"
        if (Test-Path $buildDir) { Remove-Item -Recurse -Force $buildDir }
        if (Test-Path $distDir) { Remove-Item -Recurse -Force $distDir }
        Write-Host "  -> Cleaned build/ and dist/ directories."
    }

    # 1b. Build the web interface into src\quant_system\server\static\app (bundled by the PyInstaller spec)
    $frontendDir = Join-Path $projectRoot "frontend"
    $builtIndex = Join-Path $projectRoot "src\quant_system\server\static\app\index.html"
    if (-not $SkipFrontend -and (Test-Path -LiteralPath (Join-Path $frontendDir "package.json"))) {
        Write-Host "`n[STEP 1b] Building the QuantOS web interface (frontend)..." -ForegroundColor Yellow
        $npm = (Get-Command "npm.cmd" -ErrorAction SilentlyContinue | Select-Object -First 1).Source
        if (-not $npm) {
            throw "Node.js (npm) is required to build the web interface. Install the LTS version from https://nodejs.org and re-run."
        }
        Push-Location $frontendDir
        try {
            if (-not (Test-Path -LiteralPath (Join-Path $frontendDir "node_modules"))) {
                & $npm ci --no-audit --no-fund
                if ($LASTEXITCODE -ne 0) { throw "npm ci failed with exit code $LASTEXITCODE" }
            }
            & $npm run build
            if ($LASTEXITCODE -ne 0) { throw "Frontend build failed with exit code $LASTEXITCODE" }
        } finally {
            Pop-Location
        }
        Write-Host "  -> Web interface built." -ForegroundColor Green
    }
    if (-not (Test-Path -LiteralPath $builtIndex)) {
        throw "The web interface is not built ($builtIndex missing). Run without -SkipFrontend, or build frontend/ first."
    }

    # 2. PyInstaller standalone compilation
    if (-not $SkipPyInstaller) {
        Write-Host "`n[STEP 2] Running PyInstaller standalone compiler (quantos.exe)..." -ForegroundColor Yellow
        $specPath = Join-Path $projectRoot "installer\quantos.spec"
        if (-not (Test-Path $specPath)) {
            $specPath = Join-Path $projectRoot "quant_system.spec"
        }
        Write-Host "  -> Using spec: $specPath"

        & $python -m PyInstaller --noconfirm --distpath (Join-Path $projectRoot "dist") $specPath
        if ($LASTEXITCODE -ne 0) {
            throw "PyInstaller compilation failed with exit code $LASTEXITCODE"
        }
        Write-Host "  -> PyInstaller compilation completed." -ForegroundColor Green
    } else {
        Write-Host "`n[STEP 2] Skipping PyInstaller compilation (--SkipPyInstaller)." -ForegroundColor DarkGray
    }

    # 2b. Stage visual assets and seed data into dist\quantos for portable distribution
    $distDir = Join-Path $projectRoot "dist\quantos"
    if (Test-Path $distDir) {
        $distAssets = Join-Path $distDir "assets"
        $srcAssets = Join-Path $projectRoot "installer\assets"
        if (-not (Test-Path $srcAssets)) { $srcAssets = Join-Path $projectRoot "assets" }
        if (Test-Path $srcAssets) {
            if (-not (Test-Path $distAssets)) { New-Item -ItemType Directory -Path $distAssets -Force | Out-Null }
            Copy-Item -Path (Join-Path $srcAssets "*") -Destination $distAssets -Recurse -Force
            Write-Host "  -> Staged visual assets into dist\quantos\assets." -ForegroundColor Green
        }
        $distShariah = Join-Path $distDir "data\shariah"
        $srcShariah = Join-Path $projectRoot "data\shariah"
        if (Test-Path $srcShariah) {
            if (-not (Test-Path $distShariah)) { New-Item -ItemType Directory -Path $distShariah -Force | Out-Null }
            Copy-Item -Path (Join-Path $srcShariah "*") -Destination $distShariah -Recurse -Force
            Write-Host "  -> Staged shariah seed data into dist\quantos\data\shariah." -ForegroundColor Green
        }
        $distConfigs = Join-Path $distDir "configs"
        $srcConfigs = Join-Path $projectRoot "configs"
        if (Test-Path $srcConfigs) {
            if (-not (Test-Path $distConfigs)) { New-Item -ItemType Directory -Path $distConfigs -Force | Out-Null }
            Copy-Item -Path (Join-Path $srcConfigs "*") -Destination $distConfigs -Recurse -Force
            Write-Host "  -> Staged configuration data into dist\quantos\configs." -ForegroundColor Green
        }
    }

    # 3. Generate SBOM and Cryptographic Release Manifest
    Write-Host "`n[STEP 3] Generating Software Bill of Materials (SBOM) and Release Manifest..." -ForegroundColor Yellow
    $buildScript = @"
import sys
from pathlib import Path
from quant_system.release.builder import build_release

project_root = Path(r'$projectRoot')
dist_dir = project_root / 'dist'
res = build_release(
    project_root=project_root,
    output_dir=dist_dir,
    run_pyinstaller=False,
)
if not res.success:
    print(f'[ERROR] Build failed: {res.errors}')
    sys.exit(1)

print(f'[INFO] Release Version:     {res.version}')
print(f'[INFO] Git Commit SHA:      {res.git_commit_sha}')
print(f'[INFO] uv.lock SHA-256:     {res.uv_lock_sha256}')
print(f'[INFO] Total Files:         {res.total_files}')
print(f'[INFO] Total Size:          {res.total_bytes / (1024 * 1024):.2f} MB')
print(f'[INFO] SBOM Location:       {res.sbom_file}')
print(f'[INFO] Manifest Location:   {res.manifest_file}')
if res.zip_archive:
    print(f'[INFO] Portable Zip:        {res.zip_archive}')
"@

    & $python -c "$buildScript"
    if ($LASTEXITCODE -ne 0) {
        throw "Release manifest / SBOM generation failed with exit code $LASTEXITCODE"
    }

    # 4. Compile the Windows installer (Inno Setup) -> dist\QuantOS_v<version>_Setup.exe
    if (-not $SkipInstaller) {
        Write-Host "`n[STEP 4] Compiling Windows installer (Inno Setup)..." -ForegroundColor Yellow
        & (Join-Path $PSScriptRoot "build-windows-installer.ps1") -SignCommand $SignCommand
        Write-Host "  -> Installer compiled." -ForegroundColor Green
    } else {
        Write-Host "`n[STEP 4] Skipping installer compilation (-SkipInstaller)." -ForegroundColor DarkGray
    }

    Write-Host "`n======================================================================" -ForegroundColor Cyan
    Write-Host "  [BUILD COMPLETE] QuantOS Windows x64 Release Packaged Successfully!" -ForegroundColor Green
    Write-Host "======================================================================" -ForegroundColor Cyan

} finally {
    Pop-Location
}
