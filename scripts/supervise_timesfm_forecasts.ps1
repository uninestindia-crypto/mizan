# Keep the TimesFM forecast generation running until it produces its final output.
#
# Why this exists
# ---------------
# The generation is a ~2.5 hour CPU-bound run holding ~2.5 GB. In this session it has been killed
# twice by process teardown and once lost 27 minutes of work because the generator wrote only at the
# end. The generator now checkpoints to JSON Lines and resumes, so an interruption costs at most the
# last few dates -- but something still has to notice it stopped and start it again.
#
# This is that something. It relaunches on any non-success exit, resuming from the checkpoint, and
# stops as soon as the final JSON exists. A bounded attempt count keeps a genuinely broken run from
# looping forever: if the generator cannot get past whatever is killing it, that is a fact to report,
# not a thing to retry indefinitely.
#
# It does NOT survive a session teardown -- it is an ordinary process and dies with everything else.
# Its job is crashes, OOM kills and transient failures. A teardown still needs a human or an agent to
# start it again, which is one command:
#
#   powershell -ExecutionPolicy Bypass -File scripts/supervise_timesfm_forecasts.ps1

param(
    [string]$Python = "D:/quant_system_workspaces/scratch/timesfm-probe-20260910/Scripts/python.exe",
    [string]$Out    = "reports/short_horizon/timesfm-forecasts.json",
    [string]$Log    = "reports/short_horizon/timesfm-generation.log",
    [int]$MaxAttempts = 20,
    [int]$BackoffSeconds = 15
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$partial = [System.IO.Path]::ChangeExtension($Out, $null) + "partial.jsonl"

for ($attempt = 1; $attempt -le $MaxAttempts; $attempt++) {

    if (Test-Path $Out) {
        Write-Output "COMPLETE: $Out already exists after $($attempt - 1) attempt(s)."
        exit 0
    }

    $resumed = 0
    if (Test-Path $partial) {
        $resumed = (Get-Content $partial | Measure-Object -Line).Lines
    }
    Write-Output "attempt $attempt/$MaxAttempts - resuming from $resumed checkpointed forecast(s)"

    # Stderr is merged into the log rather than redirected away: a silent kill leaves no traceback,
    # and the log is the only place the reason would appear.
    & $Python -u scripts/generate_timesfm_forecasts.py --out $Out *>> $Log
    $code = $LASTEXITCODE

    if (Test-Path $Out) {
        Write-Output "COMPLETE: $Out written on attempt $attempt (exit $code)."
        exit 0
    }

    Write-Output "attempt $attempt ended without output (exit $code); retrying in $BackoffSeconds s"
    Start-Sleep -Seconds $BackoffSeconds
}

Write-Output "GIVING UP after $MaxAttempts attempts. The checkpoint is preserved at $partial."
Write-Output "This is a reportable failure, not a transient one - read $Log before retrying."
exit 1
