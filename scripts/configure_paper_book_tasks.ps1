# Apply the paper books' scheduled-task settings, and enable the tasks only when asked.
#
# Founder decision 2026-09-23, fix F4
# (agent_context/decisions/20260923-paper-books-system-test-end-date.md). Two scheduling settings
# lost paper sessions:
#
#   * `QuantOS-XSMonthly-PaperWatch` was refused by Windows (0x800710E0) from 2026-09-17 onward. It
#     would not start on battery, stopped if the laptop was unplugged, never started late after a
#     missed 16:00, and could not wake the machine, so the XS book's marks went a week stale.
#   * `QuantOS Mizan Paper Session` lost 2026-09-22. The 21 Sep session slept mid-afternoon, resumed
#     at the 22 Sep 09:00 wake, and finished ten seconds after that trigger. With
#     `MultipleInstances=IgnoreNew` the new day's run was dropped; `Queue` runs it as soon as the old
#     one exits.
#
# Only these settings change. Actions, triggers and principals stay exactly as their owners
# registered them (the XS task belongs to Hermes Agent). Without -Enable the tasks keep their
# current enabled state, which is disabled while the books are stopped.
#
#   powershell -ExecutionPolicy Bypass -File scripts/configure_paper_book_tasks.ps1
#   powershell -ExecutionPolicy Bypass -File scripts/configure_paper_book_tasks.ps1 -Enable

param([switch]$Enable)

$ErrorActionPreference = "Stop"

$wanted = [ordered]@{
    "QuantOS Mizan Paper Session"  = [ordered]@{ MultipleInstances = "Queue" }
    "QuantOS-XSMonthly-PaperWatch" = [ordered]@{
        DisallowStartIfOnBatteries = $false
        StopIfGoingOnBatteries     = $false
        StartWhenAvailable         = $true
        WakeToRun                  = $true
        MultipleInstances          = "Queue"
    }
}
# Snapshots whether the 09:00 trigger fired; it has no settings to correct, but it is part of the
# paper books' schedule and is enabled with them.
$companions = @("QuantOS Trigger Verification")

foreach ($name in $wanted.Keys) {
    $task = Get-ScheduledTask -TaskName $name
    foreach ($setting in $wanted[$name].GetEnumerator()) {
        $before = $task.Settings.($setting.Key)
        $task.Settings.($setting.Key) = $setting.Value
        Write-Host ("{0}: {1} {2} -> {3}" -f $name, $setting.Key, $before, $setting.Value)
    }
    Set-ScheduledTask -InputObject $task | Out-Null
}

if ($Enable) {
    foreach ($name in @($wanted.Keys) + $companions) {
        Enable-ScheduledTask -TaskName $name | Out-Null
        Write-Host "enabled: $name"
    }
}

# Verify from a fresh read rather than trusting the object that was written.
$failed = $false
foreach ($name in $wanted.Keys) {
    $settings = (Get-ScheduledTask -TaskName $name).Settings
    foreach ($setting in $wanted[$name].GetEnumerator()) {
        $actual = $settings.($setting.Key)
        if ("$actual" -ne "$($setting.Value)") {
            Write-Host ("MISMATCH {0}: {1} is {2}, wanted {3}" -f $name, $setting.Key, $actual, $setting.Value)
            $failed = $true
        }
    }
}
foreach ($name in @($wanted.Keys) + $companions) {
    Write-Host ("{0}: {1}" -f $name, (Get-ScheduledTask -TaskName $name).State)
}
if ($failed) { exit 1 }
Write-Host "settings verified"
