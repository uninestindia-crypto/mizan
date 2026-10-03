# Keep the XS-Monthly paper book observable and its daily run from being silently skipped.
#
# The second book -- Rs 10,00,000 notional, 99 open legs, a 21-session hold entered 2026-09-02 --
# had nothing watching it. Its 16:00 run was skipped on 2026-09-07 (the task's LastRunTime jumped
# 09-04 to 09-08) and its dashboard on :8091 was not running at all.
#
# EVERY XS-MONTHLY PATH IS UNDER HERMES AGENT'S ACTIVE CLAIM
# (`agent_context/work/active/20260903-hermes-xs-monthly-screen-new.md`), so this script is written
# to supervise without touching what it does not own:
#
#   * It never terminates a process. The flagship dashboard supervisor stops a hung server and
#     restarts it, which is safe on a process this agent owns. Doing that to another agent's
#     process is not: an agent between operations looks exactly like a hung one. Here, a port that
#     is listening but not answering is logged and left alone.
#   * It never invokes `run_xs_monthly_paper_watch.py` directly, because that would append to
#     `logs/xs_monthly_new/`, a claimed path. It starts Hermes' own scheduled task instead, so the
#     run happens exactly as they configured it and writes only where they intended.
#   * ONE attempt per day, never a retry loop. Same reasoning as R7-05 on the flagship book: a
#     re-run can advance state that should advance once. Hermes' history suggests theirs is
#     idempotent -- two `opened 99` entries on 2026-09-03 left 99 open legs, not 198 -- but
#     "suggests" is not "established", and it is not this agent's book to establish it on.

param(
    [string]$ProjectRoot = "D:\Quant OS\quant_system",
    [int]$Port = 8091,
    [string]$WatchTask = "QuantOS-XSMonthly-PaperWatch",
    [int]$EarliestHour = 16,
    [int]$LatestHour = 22
)

$ErrorActionPreference = "Continue"
$logFile = Join-Path $ProjectRoot "logs\xs_watch_supervisor.log"
if (-not (Test-Path -LiteralPath (Split-Path $logFile))) {
    New-Item -ItemType Directory -Path (Split-Path $logFile) -Force | Out-Null
}

function Write-Log {
    param([string]$Message)
    $line = "[{0}] {1}" -f (Get-Date).ToString("yyyy-MM-dd HH:mm:ss zzz"), $Message
    Write-Host $line
    Add-Content -Path $logFile -Value $line -Encoding utf8
}

function Test-Answers {
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/" -TimeoutSec 5 -UseBasicParsing
        return ($r.StatusCode -eq 200)
    } catch { return $false }
}

# --- 1. The dashboard ------------------------------------------------------------------------
if (-not (Test-Answers)) {
    $listening = $null
    try { $listening = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction Stop } catch { }

    if ($listening) {
        # Deliberately no recovery. See the header: this is not our process to kill.
        Write-Log "Port $Port is listening (PID $($listening[0].OwningProcess)) but not answering. Left alone -- it is under Hermes Agent's active claim. Raise it with them."
    } else {
        $python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
        if (Test-Path -LiteralPath $python) {
            Write-Log "XS dashboard not running; starting it on $Port."
            Start-Process -FilePath $python `
                -ArgumentList "scripts\serve_xs_watch_dashboard.py", "--port", "$Port" `
                -WorkingDirectory $ProjectRoot -WindowStyle Hidden
            for ($i = 0; $i -lt 8; $i++) {
                Start-Sleep -Seconds 2
                if (Test-Answers) { Write-Log "XS dashboard is answering on $Port."; break }
            }
            if (-not (Test-Answers)) { Write-Log "ERROR: started the XS dashboard but it did not answer within 16s." }
        } else {
            Write-Log "ERROR: no interpreter at $python"
        }
    }
}

# --- 2. The daily run ------------------------------------------------------------------------
$now = Get-Date
if ($now.Hour -ge $EarliestHour -and $now.Hour -lt $LatestHour) {
    $info = Get-ScheduledTaskInfo -TaskName $WatchTask -ErrorAction SilentlyContinue
    if (-not $info) {
        Write-Log "ERROR: scheduled task '$WatchTask' not found; cannot verify the daily run."
    } elseif ($info.LastRunTime -ne $null -and $info.LastRunTime.Date -eq $now.Date) {
        # Ran today. Silent: this is the normal case every evening.
    } else {
        $task = Get-ScheduledTask -TaskName $WatchTask -ErrorAction SilentlyContinue
        if ($task -and $task.State -eq "Running") {
            Write-Log "'$WatchTask' is running right now; leaving it."
        } else {
            Write-Log "'$WatchTask' has not run today (LastRunTime $($info.LastRunTime)). Starting Hermes' own task once."
            Start-ScheduledTask -TaskName $WatchTask
        }
    }
}
