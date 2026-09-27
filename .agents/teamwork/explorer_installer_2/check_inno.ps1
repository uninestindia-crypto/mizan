$paths = @(
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe",
    "C:\Program Files (x86)\Inno Setup 5\ISCC.exe",
    (Get-Command iscc.exe -ErrorAction SilentlyContinue).Source
)

$found = $false
foreach ($p in $paths) {
    if ($p -and (Test-Path $p)) {
        Write-Host "Found Inno Setup at: $p"
        $found = $true
        & $p /? | Select-Object -First 3
    }
}

if (-not $found) {
    Write-Host "ISCC.exe not found in standard paths."
}
