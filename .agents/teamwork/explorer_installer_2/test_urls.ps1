$urls = @(
    "https://go.microsoft.com/fwlink/p/?LinkId=2124701",
    "https://go.microsoft.com/fwlink/?linkid=2124701",
    "https://go.microsoft.com/fwlink/p/?LinkId=2124707"
)

foreach ($u in $urls) {
    try {
        $req = [System.Net.HttpWebRequest]::Create($u)
        $req.Method = "HEAD"
        $req.AllowAutoRedirect = $true
        $req.Timeout = 10000
        $resp = $req.GetResponse()
        [PSCustomObject]@{
            OriginalUrl = $u
            FinalUrl = $resp.ResponseUri.AbsoluteUri
            StatusCode = [int]$resp.StatusCode
            ContentLength = $resp.ContentLength
            ContentType = $resp.ContentType
        } | Format-List
        $resp.Close()
    } catch {
        [PSCustomObject]@{
            OriginalUrl = $u
            Error = $_.Exception.Message
        } | Format-List
    }
}
