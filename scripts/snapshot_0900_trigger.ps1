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

# Read the power events FIRST, so the mechanism can be reported beside the verdict rather than
# asserted. An earlier version of this script printed "TRIGGER FIRED at 09:00 - wake timer worked".
# The first half was measured; the second half was an assumption written before there was evidence
# for it, and it was wrong to state as fact. Two changes were in play -- `Allow wake timers` on DC
# (2026-09-07) and `Lid close action` on AC (2026-09-09) -- and this snapshot cannot separate them.
# What it CAN observe is whether the machine slept at all, which distinguishes the two mechanisms:
# waking shortly before 09:00 is a wake timer doing the work; never sleeping is the lid change
# holding the machine awake.
#
# Pick the wake that is relevant to the 09:00 trigger, not merely the most recent one. The first
# version took the latest event of the day and reported a 12-second sleep/wake blip at 09:27 -- a
# real event, but one that happened long after the session had already started, so it said nothing
# about whether the machine was awake at 09:00. The relevant wake is the LAST one at or before
# 09:00 (plus a minute of slack for a wake that lands just after the trigger time).
$sleptToday = $false
$wokeAt = $null
$cutoff = $now.Date.AddHours(9).AddMinutes(1)
try {
    $pt = Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='Microsoft-Windows-Power-Troubleshooter'; StartTime=$now.Date} -MaxEvents 10 -ErrorAction Stop
    foreach ($e in $pt) {
        $sleptToday = $true
        if ($e.TimeCreated -le $cutoff) {
            if ($wokeAt -eq $null -or $e.TimeCreated -gt $wokeAt) { $wokeAt = $e.TimeCreated }
        }
    }
} catch {
    $sleptToday = $false
}

$info = Get-ScheduledTaskInfo -TaskName "QuantOS Mizan Paper Session" -ErrorAction SilentlyContinue
if ($info) {
    Emit "  task LastRunTime      : $($info.LastRunTime)"
    Emit "  task LastTaskResult   : $($info.LastTaskResult)"
    Emit "  task NextRunTime      : $($info.NextRunTime)"

    $firedToday = ($info.LastRunTime -ne $null) -and ($info.LastRunTime.Date -eq $now.Date) -and ($info.LastRunTime.Hour -lt 10)

    # Measured. States what happened, and nothing about why.
    Emit "  VERDICT               : $(if ($firedToday) { 'TRIGGER FIRED at 09:00' } else { 'TRIGGER DID NOT FIRE - the supervisor will start the session late' })"

    # Observed, and labelled as an observation. Attribution between the two fixes stays open.
    if (-not $sleptToday) {
        Emit "  MECHANISM (observed)  : machine did not sleep at all today - it was held awake"
    } elseif ($wokeAt -eq $null) {
        Emit "  MECHANISM (observed)  : machine was awake through 09:00 - it only slept later in the day"
    } else {
        $target = $now.Date.AddHours(9)
        $delta = [int]($target - $wokeAt).TotalSeconds
        if ($firedToday -and $delta -ge 0 -and $delta -lt 1800) {
            Emit "  MECHANISM (observed)  : machine slept, then woke $delta s before 09:00 - a wake timer fired"
        } else {
            Emit "  MECHANISM (observed)  : machine slept and woke at $($wokeAt.ToString('HH:mm:ss')) - $(if ($firedToday) { 'unclear' } else { 'too late for the 09:00 trigger' })"
        }
    }
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

try {
    $pt2 = Get-WinEvent -FilterHashtable @{LogName='System'; ProviderName='Microsoft-Windows-Power-Troubleshooter'; StartTime=$now.Date} -MaxEvents 3 -ErrorAction Stop
    foreach ($e in $pt2) {
        $line = (($e.Message -split "`n") | Where-Object { $_ -match 'Wake Time|Sleep Time' }) -join ' | '
        Emit "  power event $($e.TimeCreated.ToString('HH:mm:ss')): $line"
    }
} catch {
    Emit "  power events          : none today (machine did not sleep/wake)"
}

$ac = (powercfg /q SCHEME_CURRENT SUB_SLEEP BD3B718A-0680-4D9D-8AB2-E1D2B4AC806D 2>&1 | Select-String "Current AC").ToString().Trim()
$dc = (powercfg /q SCHEME_CURRENT SUB_SLEEP BD3B718A-0680-4D9D-8AB2-E1D2B4AC806D 2>&1 | Select-String "Current DC").ToString().Trim()
Emit "  wake timers           : $ac / $dc"
