# Setup script to register the QuantOS Daily Auto-Sync task in Windows Task Scheduler

param(
    [string]$TaskName = "QuantOS-DailyAutoSync",
    [string]$DailyTime = "23:00"  # 11:00 PM daily
)

$ErrorActionPreference = "Stop"
$projectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$syncScript = Join-Path $projectRoot "scripts\daily_auto_sync.ps1"

Write-Host "Registering Windows Scheduled Task '$TaskName' to run daily at $DailyTime..."
Write-Host "Target script: $syncScript"

try {
    $timeParts = $DailyTime.Split(":")
    $hour = [int]$timeParts[0]
    $minute = [int]$timeParts[1]
    $triggerTime = (Get-Date).Date.AddHours($hour).AddMinutes($minute)

    $action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-ExecutionPolicy Bypass -WindowStyle Hidden -File `"$syncScript`""
    $trigger = New-ScheduledTaskTrigger -Daily -At $triggerTime
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

    # Unregister existing task if present
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue

    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Description "QuantOS Daily Automated Git Commit and Sync to Private GitHub Remote"
    Write-Host "Successfully registered Windows Scheduled Task '$TaskName'."
    Write-Host "Task will trigger daily at $DailyTime."
} catch {
    Write-Error "Failed to register Scheduled Task: $_"
    exit 1
}
