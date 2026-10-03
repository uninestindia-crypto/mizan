# Ensure the QuantOS live dashboard is up. Safe to run repeatedly.
#
# Registered as a scheduled task that fires at logon and repeats, because the dashboard has died
# twice for reasons that were nothing to do with its code:
#
#   2026-09-01  the single-threaded server hung on a keep-alive client -- process alive, port
#               listening, every request unanswered. Repaired by ThreadingTCPServer.
#   2026-09-02  the process was simply gone after the machine slept at 23:49. Nothing owned
#               restarting it, because it had been started by hand.
#
# Idempotency matters more than usual here. `ThreadedDashboardServer.allow_reuse_address` is true,
# and on Windows SO_REUSEADDR lets a second socket bind a port another socket already holds -- so a
# careless "just start it again" every five minutes would quietly accumulate servers all answering
# on 8080. Hence: probe first, and only ever start one.

param(
    [int]$Port = 8080,
    [string]$ProjectRoot = "D:\Quant OS\quant_system"
)

$ErrorActionPreference = "Continue"
$logFile = Join-Path $ProjectRoot "logs\dashboard_supervisor.log"

function Write-Log {
    param([string]$Message)
    $line = "[{0}] {1}" -f (Get-Date).ToString("yyyy-MM-dd HH:mm:ss zzz"), $Message
    Write-Host $line
    Add-Content -Path $logFile -Value $line -Encoding utf8
}

function Test-DashboardAnswers {
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/" -TimeoutSec 5 -UseBasicParsing
        return ($r.StatusCode -eq 200)
    } catch {
        return $false
    }
}

function Get-OurDashboardProcesses {
    # Only ever our own process: matched on the script name in the command line, never on the port
    # alone. A task that kills whatever holds a port is a task that one day kills something else.
    Get-CimInstance Win32_Process -Filter "Name like '%python%'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -like "*serve_live_dashboard.py*" }
}

if (-not (Test-Path -LiteralPath (Split-Path $logFile))) {
    New-Item -ItemType Directory -Path (Split-Path $logFile) -Force | Out-Null
}

if (Test-DashboardAnswers) {
    exit 0
}

# Not answering. Distinguish "dead" from "hung": a hung server still holds the port.
$listening = $null
try {
    $listening = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction Stop
} catch {
    $listening = $null
}

if ($listening) {
    $ours = @(Get-OurDashboardProcesses)
    if ($ours.Count -eq 0) {
        Write-Log "Port $Port is held by PID $($listening[0].OwningProcess), which is not one of ours. Doing nothing."
        exit 2
    }
    Write-Log "Dashboard is listening but not answering (hung). Stopping our PID(s): $($ours.ProcessId -join ', ')"
    foreach ($proc in $ours) {
        Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
    }
    Start-Sleep -Seconds 2
}

Write-Log "Dashboard not answering on $Port; starting it."
$python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    Write-Log "ERROR: no interpreter at $python"
    exit 1
}
Start-Process -FilePath $python `
    -ArgumentList "scripts\serve_live_dashboard.py", "--port", "$Port" `
    -WorkingDirectory $ProjectRoot -WindowStyle Hidden

# Verify rather than assume. A start that silently fails is the failure this task exists to prevent.
for ($i = 0; $i -lt 10; $i++) {
    Start-Sleep -Seconds 2
    if (Test-DashboardAnswers) {
        Write-Log "Dashboard is answering on $Port."
        exit 0
    }
}
Write-Log "ERROR: started the dashboard but it did not answer within 20s."
exit 1
