function Test-VCRedistInstalled {
    [CmdletBinding()]
    param()

    $regPaths = @(
        "HKLM:\SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\X64",
        "HKLM:\SOFTWARE\WOW6432Node\Microsoft\VisualStudio\14.0\VC\Runtimes\X64"
    )

    foreach ($path in $regPaths) {
        if (Test-Path $path) {
            $props = Get-ItemProperty -Path $path -ErrorAction SilentlyContinue
            if ($props -and $props.Installed -eq 1) {
                return [PSCustomObject]@{
                    Installed = $true
                    Version = $props.Version
                    Major = $props.Major
                    Minor = $props.Minor
                    Bld = $props.Bld
                    RegistryPath = $path
                }
            }
        }
    }

    return [PSCustomObject]@{
        Installed = $false
        Version = $null
        Major = $null
        Minor = $null
        Bld = $null
        RegistryPath = $null
    }
}

$result = Test-VCRedistInstalled
$result | Format-List
