param(
    # Optional Authenticode command, Inno Setup syntax: "$f" is replaced by the quoted file.
    # Example: -SignCommand 'signtool sign /fd sha256 /tr http://timestamp.digicert.com /td sha256 /a $f'
    [string]$SignCommand = "",
    [string]$Iscc = ""
)

# Compiles installer\quant_os_setup.iss into dist\QuantOS_v<version>_Setup.exe.
# Needs the PyInstaller bundle in dist\quantos (scripts\build-windows-release.ps1 steps 1-3).
# Needs Inno Setup 6.7 or newer: winget install --id JRSoftware.InnoSetup -e --scope user

$ErrorActionPreference = "Stop"
$projectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$issPath = Join-Path $projectRoot "installer\quant_os_setup.iss"

$candidates = @(
    $Iscc,
    (Get-Command "ISCC.exe" -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -First 1),
    (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"),
    (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
    (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe")
) | Where-Object { $_ -and (Test-Path -LiteralPath $_) }

$compiler = $candidates | Select-Object -First 1
if (-not $compiler) {
    throw "Inno Setup compiler (ISCC.exe) not found. Install it with: winget install --id JRSoftware.InnoSetup -e --scope user"
}

$studioExe = Join-Path $projectRoot "dist\quantos\quantos-studio.exe"
if (-not (Test-Path -LiteralPath $studioExe)) {
    throw "dist\quantos\quantos-studio.exe not found. Run scripts\build-windows-release.ps1 first."
}

Write-Host "  -> Inno Setup compiler: $compiler"
$arguments = @("/Qp")
if ($SignCommand) {
    $arguments += "/Squantos=$SignCommand"
    $arguments += "/DSignToolName=quantos"
    Write-Host "  -> Signing installer and uninstaller"
} else {
    Write-Host "  -> Unsigned build (pass -SignCommand to sign)" -ForegroundColor DarkYellow
}
$arguments += $issPath

& $compiler @arguments
if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup compilation failed with exit code $LASTEXITCODE"
}

$version = (Get-Item -LiteralPath $studioExe).VersionInfo.ProductVersion
$setupExe = Join-Path $projectRoot "dist\QuantOS_v$($version)_Setup.exe"
if (-not (Test-Path -LiteralPath $setupExe)) {
    throw "Expected installer not produced: $setupExe"
}
$sizeMb = (Get-Item -LiteralPath $setupExe).Length / 1MB
Write-Host ("  -> Installer: {0} ({1:N1} MB)" -f $setupExe, $sizeMb) -ForegroundColor Green
