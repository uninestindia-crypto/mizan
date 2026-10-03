# Ensure today's paper session has been started. Safe to run repeatedly; starts at most one per day.
#
# Why this exists: on 2026-09-02 the `QuantOS Mizan Paper Session` task did not fire at 09:00. The
# machine was awake -- it had woken at 00:11 and was in use by 03:00 -- so the Modern Standby
# wake-timer explanation does not fit. `NextRunTime` had already rolled to the following day and
# `NumberOfMissedRuns` was 0, so Task Scheduler did not consider the trigger missed either. The root
# cause is still unknown, because the TaskScheduler/Operational log is disabled and enabling it
# needs elevation. This task does not diagnose that. It makes it survivable.
#
# THE GUARD THAT MATTERS: this starts a session only when today's log file does not exist at all.
#
# Not "if no session is running", and not "if the last run failed". Red Team round seven, finding
# R7-05: every run on the same trading day advances `sessions_held` again -- driven on a copy of the
# real book, three runs on one date took it 2 -> 3 -> 4 -> 5. The model holds for ten sessions, so a
# retry loop would retire positions that had never been held. Until R7-05 is repaired, "exactly one
# attempt per day, and a human decides about the second" is the only safe rule, and a crashed
# session is deliberately NOT restarted.

param(
    [string]$ProjectRoot = "D:\Quant OS\quant_system",
    [string]$UniverseName = "NIFTY500",
    [int]$EarliestHour = 9,
    [int]$LatestHour = 15
)

$ErrorActionPreference = "Continue"
$logFile = Join-Path $ProjectRoot "logs\session_supervisor.log"

function Write-Log {
    param([string]$Message)
    $line = "[{0}] {1}" -f (Get-Date).ToString("yyyy-MM-dd HH:mm:ss zzz"), $Message
    Write-Host $line
    Add-Content -Path $logFile -Value $line -Encoding utf8
}

if (-not (Test-Path -LiteralPath (Split-Path $logFile))) {
    New-Item -ItemType Directory -Path (Split-Path $logFile) -Force | Out-Null
}

# 1. A session already running is the normal case for most of the day. Silent, or the log fills with
#    288 identical lines a day.
#
#    Scoped to $ProjectRoot, not matched machine-wide. An unscoped match was the first version, and
#    driving it caught the flaw: a session running from any checkout on the machine -- a Red Team
#    clone, a second working tree -- would satisfy this guard and suppress the real one forever.
$running = @(Get-CimInstance Win32_Process -Filter "Name like '%python%'" -ErrorAction SilentlyContinue |
    Where-Object {
        $_.CommandLine -like "*$ProjectRoot*" -and
        ($_.CommandLine -like "*run_scheduled_paper_session*" -or $_.CommandLine -like "*run_paper_pilot_session*")
    })
if ($running.Count -gt 0) { exit 0 }

# 2. Today's log existing means an attempt was already made today -- finished, refused, or crashed.
#    See the header: one attempt per day is deliberate.
$today = Get-Date
$todayLog = Join-Path $ProjectRoot ("logs\paper_runs\scheduled_{0}.log" -f $today.ToString("yyyyMMdd"))
if (Test-Path -LiteralPath $todayLog) { exit 0 }

# 3. Outside the window there is nothing useful to start.
if ($today.Hour -lt $EarliestHour -or $today.Hour -ge $LatestHour) { exit 0 }

# 4. Trading day, decided by the session's own authority rather than a second copy of the rule here.
$python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    Write-Log "ERROR: no interpreter at $python"
    exit 1
}
# The probe goes to a temp file rather than `python -c`. Passing it inline looked fine and was
# broken: PowerShell strips double quotes when it builds a native command line, so Python received
# `sys.path.insert(0, scripts)` and died on NameError -- which this script read as "not a trading
# day" and silently declined to start anything. A guard that fails closed for the wrong reason is
# indistinguishable from one that works, every day except the one that matters.
$probeFile = Join-Path $env:TEMP ("quantos_tradingday_{0}.py" -f [guid]::NewGuid().ToString('N'))
$probeLines = @(
    'import sys, importlib.util',
    'from datetime import date',
    'sys.path.insert(0, "scripts")',
    'sys.path.insert(0, "src")',
    'spec = importlib.util.spec_from_file_location("sched", "scripts/run_scheduled_paper_session.py")',
    'm = importlib.util.module_from_spec(spec)',
    'spec.loader.exec_module(m)',
    'try:',
    '    m.require_trading_day(date.today())',
    'except Exception:',
    '    raise SystemExit(1)',
    'raise SystemExit(0)'
)
Set-Content -Path $probeFile -Value $probeLines -Encoding utf8
Push-Location $ProjectRoot
& $python $probeFile
$isTradingDay = ($LASTEXITCODE -eq 0)
Pop-Location
Remove-Item -LiteralPath $probeFile -Force -ErrorAction SilentlyContinue
if (-not $isTradingDay) { exit 0 }

Write-Log "No session and no log for $($today.ToString('yyyy-MM-dd')); the 09:00 task did not run. Starting one."
Start-Process -FilePath "cmd.exe" `
    -ArgumentList "/c", (Join-Path $ProjectRoot "scripts\run_scheduled_paper_session.cmd") `
    -WorkingDirectory $ProjectRoot -WindowStyle Hidden

Start-Sleep -Seconds 20
if (Test-Path -LiteralPath $todayLog) {
    Write-Log "Session started; log is at $todayLog"
    exit 0
}
Write-Log "ERROR: started the session but no log appeared within 20s."
exit 1
