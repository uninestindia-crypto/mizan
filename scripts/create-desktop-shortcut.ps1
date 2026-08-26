# ==============================================================================
# Create Desktop Shortcut for QuantOS Studio
# ==============================================================================
param(
    [string]$TargetDir = "$PSScriptRoot\.."
)

$ErrorActionPreference = "Stop"
$resolvedTargetDir = [System.IO.Path]::GetFullPath($TargetDir)
$vbsPath = Join-Path $resolvedTargetDir "QuantOS-Studio.vbs"
$desktopPath = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktopPath "QuantOS Studio.lnk"

if (-not (Test-Path -LiteralPath $vbsPath)) {
    Write-Error "QuantOS-Studio.vbs not found at: $vbsPath"
    exit 1
}

$wshShell = New-Object -ComObject WScript.Shell
$shortcut = $wshShell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = "wscript.exe"
$shortcut.Arguments = "`"$vbsPath`""
$shortcut.WorkingDirectory = $resolvedTargetDir
$shortcut.Description = "QuantOS Studio — Quantitative Research & Risk Engine"
$shortcut.Save()

Write-Host "[SUCCESS] Created Desktop Shortcut: $shortcutPath" -ForegroundColor Green
