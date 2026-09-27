function Test-WebView2Installed {
    [CmdletBinding()]
    param()

    $guid = "{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
    $locations = @(
        @{ Hive = "HKLM"; Path = "HKLM:\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\$guid"; Scope = "Machine (WOW6432Node)" },
        @{ Hive = "HKLM"; Path = "HKLM:\SOFTWARE\Microsoft\EdgeUpdate\Clients\$guid"; Scope = "Machine (Native)" },
        @{ Hive = "HKCU"; Path = "HKCU:\SOFTWARE\Microsoft\EdgeUpdate\Clients\$guid"; Scope = "User" }
    )

    foreach ($loc in $locations) {
        if (Test-Path $loc.Path) {
            $props = Get-ItemProperty -Path $loc.Path -ErrorAction SilentlyContinue
            if ($props -and $props.pv) {
                $ver = [string]$props.pv
                if ($ver.Trim() -ne "" -and $ver.Trim() -ne "0.0.0.0") {
                    return [PSCustomObject]@{
                        Installed = $true
                        Version = $ver
                        Scope = $loc.Scope
                        RegistryPath = $loc.Path
                        InstallLocation = $props.location
                    }
                }
            }
        }
    }

    return [PSCustomObject]@{
        Installed = $false
        Version = $null
        Scope = $null
        RegistryPath = $null
        InstallLocation = $null
    }
}

$result = Test-WebView2Installed
$result | Format-List
