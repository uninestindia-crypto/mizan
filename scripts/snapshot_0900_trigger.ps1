# Snapshot, at 09:05 IST, of whether the 09:00 paper-session trigger actually fired.
#
# Written because the question is only answerable in a narrow window. `LastRunTime` on
# `QuantOS Mizan Paper Session` shows 09:00 if the trigger fired -- but the Session Supervisor
# starts a session itself later in the morning whenever the trigger did not, and that overwrites
# the same field. By 11:00 the two outcomes look identical.
#
# Context: on 2026-09-03, 09-04 and 09-07 the machine was asleep across 09:00 and never woke.
# `Allow wake timers` was Enable on AC and **Disable on DC**, so Windows refused WakeToRun outright
# whenever the laptop was on battery. DC was set to Enable on 2026-09-07; this snapshot is how that
# change gets verified rather than assumed.

$ErrorActionPreference = "Continue"
$root = "D:\quant_system"
$out = Join-Path $root "logs\trigger_verification.log"
if (-not (Test-Path -LiteralPath (Split-Path $out))) {
    New-Item -ItemType Directory -Path (Split-Path $out) -Force | Out-Null
}

function Emit { param([string]$m) Add-Content -Path $out -Value $m -Encoding utf8; Write-Host $m }

$now = Get-Date
Emit ("=" * 78)
Emit "SNAPSHOT $($now.ToString('yyyy-MM-dd HH:mm:ss zzz'))"

$info = Get-ScheduledTaskInfo -TaskName "QuantOS Mizan Paper Session" -ErrorAction SilentlyContinue
if ($info) {
    Emit "  task LastRunTime      : $($info.LastRunTime)"
    Emit "  task LastTaskResult   : $($info.LastTaskResult)"
    Emit "  task NextRunTime      : $($info.NextRunTime)"
    $firedToday = ($info.LastRunTime -ne $null) -and ($info.LastRunTime.Date -eq $now.Date) -and ($info.LastRunTime.Hour -lt 10)
    Emit "  VERDICT               : $(if ($firedToday) { 'TRIGGER FIRED at 09:00 - wake timer worked' } else { 'TRIGGER DID NOT FIRE - still relying on the supervisor' })"
} else {
    Emit "  task not found"
}

$log = Join-Path $root ("logs\paper_runs\scheduled_{0}.log" -f $now.ToString('yyyyMMdd'))
if (Test-Path -LiteralPath $log) {
    $first = (Get-Content -LiteralPath $log -TotalCount 1)
    Emit "  session log first line: $first"
} else {
    Emit "  session log           : none yet for today"
}

# Was the machine asleep across 09:00? The direct evidence for the wake-timer question.
try {
    $pt = Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='Microsoft-Windows-Power-Troubleshooter'; StartTime=$now.Date} -MaxEvents 3 -ErrorAction Stop
    foreach ($e in $pt) {
        $line = (($e.Message -split "`n") | Where-Object { $_ -match 'Wake Time|Sleep Time' }) -join ' | '
        Emit "  power event $($e.TimeCreated.ToString('HH:mm:ss')): $line"
    }
} catch {
    Emit "  power events          : none today (machine did not sleep/wake)"
}

$ac = (powercfg /q SCHEME_CURRENT SUB_SLEEP BD3B718A-0680-4D9D-8AB2-E1D2B4AC806D 2>&1 | Select-String "Current AC").ToString().Trim()
$dc = (powercfg /q SCHEME_CURRENT SUB_SLEEP BD3B718A-0680-4D9D-8AB2-E1D2B4AC806D 2>&1 | Select-String "Current DC").ToString().Trim()
Emit "  wake timers           : $ac / $dc"
