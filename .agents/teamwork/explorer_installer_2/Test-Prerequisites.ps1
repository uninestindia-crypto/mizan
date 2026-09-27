<#
.SYNOPSIS
    QuantOS Automated Prerequisite Detection, Verification & Diagnostic Harness
.DESCRIPTION
    Validates VC++ 2015-2022 x64 and Edge WebView2 Evergreen Runtime detection,
    Microsoft download endpoint reachability, and offline fallback mechanics.
#>

[CmdletBinding()]
param(
    [switch]$CheckOnly = $true,
    [string]$OfflineSourceDir = ""
)

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "  QuantOS Prerequisite Detection & Network Verification Harness" -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan

# ----------------------------------------------------------------------
# 1. VC++ 2015-2022 x64 Detection
# ----------------------------------------------------------------------
Write-Host "`n[1] Checking VC++ 2015-2022 x64 Redistributable..." -ForegroundColor Yellow

$vcFound = $false
$vcVersion = $null
$vcPaths = @(
    "HKLM:\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\X64",
    "HKLM:\SOFTWARE\WOW6432Node\Microsoft\VisualStudio\14.0\VC\Runtimes\X64"
)

foreach ($regPath in $vcPaths) {
    if (Test-Path $regPath) {
        $props = Get-ItemProperty -Path $regPath -ErrorAction SilentlyContinue
        if ($props -and $props.Installed -eq 1) {
            $vcFound = $true
            $vcVersion = $props.Version
            Write-Host "  [FOUND] Registry Path : $regPath" -ForegroundColor Green
            Write-Host "  [FOUND] Installed     : $($props.Installed)" -ForegroundColor Green
            Write-Host "  [FOUND] Version       : $($props.Version)" -ForegroundColor Green
            Write-Host "  [FOUND] Major/Minor   : $($props.Major).$($props.Minor).$($props.Bld)" -ForegroundColor Green
            break
        }
    }
}

if (-not $vcFound) {
    Write-Host "  [MISSING] VC++ 2015-2022 x64 Redistributable is NOT installed." -ForegroundColor Red
}

# ----------------------------------------------------------------------
# 2. Microsoft Edge WebView2 Evergreen Detection
# ----------------------------------------------------------------------
Write-Host "`n[2] Checking Microsoft Edge WebView2 Evergreen Runtime..." -ForegroundColor Yellow

$wvFound = $false
$wvVersion = $null
$wvScope = $null
$wvGuid = "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"

$wvLocations = @(
    @{ Hive = "HKLM (WOW6432Node)"; Path = "HKLM:\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\$wvGuid" },
    @{ Hive = "HKLM (Native)";      Path = "HKLM:\SOFTWARE\Microsoft\EdgeUpdate\Clients\$wvGuid" },
    @{ Hive = "HKCU (User)";        Path = "HKCU:\SOFTWARE\Microsoft\EdgeUpdate\Clients\$wvGuid" }
)

foreach ($loc in $wvLocations) {
    if (Test-Path $loc.Path) {
        $props = Get-ItemProperty -Path $loc.Path -ErrorAction SilentlyContinue
        if ($props -and $props.pv) {
            $v = [string]$props.pv
            if ($v.Trim() -ne "" -and $v.Trim() -ne "0.0.0.0") {
                $wvFound = $true
                $wvVersion = $v
                $wvScope = $loc.Hive
                Write-Host "  [FOUND] Scope         : $($loc.Hive)" -ForegroundColor Green
                Write-Host "  [FOUND] Registry Path : $($loc.Path)" -ForegroundColor Green
                Write-Host "  [FOUND] Version (pv)  : $v" -ForegroundColor Green
                if ($props.location) {
                    Write-Host "  [FOUND] Install Dir   : $($props.location)" -ForegroundColor Green
                }
                break
            }
        }
    }
}

if (-not $wvFound) {
    Write-Host "  [MISSING] Microsoft Edge WebView2 Evergreen Runtime is NOT installed." -ForegroundColor Red
}

# ----------------------------------------------------------------------
# 3. Microsoft Official Endpoint Reachability (HEAD requests only)
# ----------------------------------------------------------------------
Write-Host "`n[3] Testing Connectivity to Official Microsoft Runtime Endpoints..." -ForegroundColor Yellow

$endpoints = @(
    @{
        Name = "VC++ 2015-2022 x64 Official Aka.ms"
        Url  = "https://aka.ms/vs/17/release/vc_redist.x64.exe"
    },
    @{
        Name = "WebView2 Evergreen Bootstrapper Official Fwlink"
        Url  = "https://go.microsoft.com/fwlink/p/?LinkId=2124703"
    },
    @{
        Name = "WebView2 Evergreen Standalone x64 Official Fwlink"
        Url  = "https://go.microsoft.com/fwlink/p/?LinkId=2124701"
    }
)

foreach ($ep in $endpoints) {
    try {
        $req = [System.Net.HttpWebRequest]::Create($ep.Url)
        $req.Method = "HEAD"
        $req.AllowAutoRedirect = $true
        $req.Timeout = 8000
        $resp = $req.GetResponse()
        $sizeMb = [math]::Round($resp.ContentLength / (1024 * 1024), 2)
        Write-Host "  [ONLINE] $($ep.Name)" -ForegroundColor Green
        Write-Host "           Status: $($resp.StatusCode) ($([int]$resp.StatusCode)) | Size: $sizeMb MB" -ForegroundColor DarkGray
        Write-Host "           Target: $($resp.ResponseUri.AbsoluteUri)" -ForegroundColor DarkGray
        $resp.Close()
    } catch {
        Write-Host "  [OFFLINE / BLOCKED] $($ep.Name)" -ForegroundColor Red
        Write-Host "                      Error: $($_.Exception.Message)" -ForegroundColor DarkGray
    }
}

# ----------------------------------------------------------------------
# 4. Summary & Readiness Assessment
# ----------------------------------------------------------------------
Write-Host "`n======================================================================" -ForegroundColor Cyan
Write-Host "  Prerequisite Readiness Assessment" -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "  VC++ 2015-2022 (x64) : $(if ($vcFound) {'PRESENT (Ready)'} else {'MISSING (Install Required)'})" -ForegroundColor $(if ($vcFound) {'Green'} else {'Red'})
Write-Host "  WebView2 Evergreen   : $(if ($wvFound) {'PRESENT (Ready)'} else {'MISSING (Install Required)'})" -ForegroundColor $(if ($wvFound) {'Green'} else {'Red'})
Write-Host "======================================================================`n" -ForegroundColor Cyan
