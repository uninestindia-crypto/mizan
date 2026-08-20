# QuantOS — Windows Task Scheduler Daily Automation Setup Script
# Run this PowerShell script as Administrator to register a daily scheduled task.

param(
    [string]$TaskName = "QuantOS_Daily_Pipeline",
    [string]$DailyTime = "17:00", # 5:00 PM IST (post NSE market close)
    [string]$PythonEnvPath = ".venv"
)

$ErrorActionPreference = "Stop"
$projectRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot ".."))
$environmentRoot = [System.IO.Path]::GetFullPath((Join-Path $projectRoot $PythonEnvPath))
$pythonExe = Join-Path $environmentRoot "Scripts\python.exe"
$pipelineScript = Join-Path $projectRoot "scripts\daily_pipeline.py"

if (-not (Test-Path -LiteralPath $pythonExe)) {
    throw "Python executable not found at: $pythonExe. Run 'uv sync' or set up .venv first."
}

if (-not (Test-Path -LiteralPath $pipelineScript)) {
    throw "Daily pipeline script not found at: $pipelineScript"
}

Write-Host "=========================================================="
Write-Host "QuantOS Windows Task Scheduler Daily Setup"
Write-Host "=========================================================="
Write-Host "Project Root: $projectRoot"
Write-Host "Python Executable: $pythonExe"
Write-Host "Scheduled Daily Time: $DailyTime"
Write-Host "Task Name: $TaskName"
Write-Host "----------------------------------------------------------"

# Define Action
$action = New-ScheduledTaskAction `
    -Execute $pythonExe `
    -Argument "`"$pipelineScript`"" `
    -WorkingDirectory $projectRoot

# Define Daily Trigger
$trigger = New-ScheduledTaskTrigger `
    -Daily `
    -At $DailyTime

# Define Settings (wake computer if possible, don't stop on battery)
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 2)

# Unregister existing task if it exists
$existingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existingTask) {
    Write-Host "Removing existing scheduled task: $TaskName..."
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}

# Register the new scheduled task
Write-Host "Registering scheduled task: $TaskName..."
Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description "QuantOS Automated Daily Machine Learning Training & Backtesting Pipeline"

Write-Host "=========================================================="
Write-Host "SUCCESS: $TaskName is registered to run daily at $DailyTime."
Write-Host "You can test-run it immediately with:"
Write-Host "  Start-ScheduledTask -TaskName `"$TaskName`""
Write-Host "=========================================================="
