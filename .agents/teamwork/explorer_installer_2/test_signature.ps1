$paths = @(
    "C:\Program Files (x86)\Microsoft\EdgeWebView\Application\153.0.4234.48\Installer\setup.exe",
    "C:\Windows\System32\vcruntime140.dll"
)
foreach ($p in $paths) {
    if (Test-Path $p) {
        $sig = Get-AuthenticodeSignature $p
        [PSCustomObject]@{
            Path = $p
            Status = $sig.Status
            Signer = $sig.SignerCertificate.Subject
            Issuer = $sig.SignerCertificate.Issuer
            TimeStamper = $sig.TimeStamperCertificate.Subject
        } | Format-List
    }
}
