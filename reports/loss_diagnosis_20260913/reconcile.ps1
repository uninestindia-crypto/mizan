param([string]$InstallRoot = 'D:\quant_system')

$ErrorActionPreference = 'Stop'
$sourcePaths = @(
    'logs/paper_runs/live_paper_status.json',
    'logs/paper_runs/portfolio_state.json',
    'logs/xs_monthly_new/paper_watch/state.json'
)
$sources = @()
$documents = @()
foreach ($relativePath in $sourcePaths) {
    $sourcePath = Join-Path $InstallRoot $relativePath
    $beforeHash = (Get-FileHash -LiteralPath $sourcePath -Algorithm SHA256).Hash
    $documents += Get-Content -LiteralPath $sourcePath -Raw | ConvertFrom-Json
    $afterHash = (Get-FileHash -LiteralPath $sourcePath -Algorithm SHA256).Hash
    if ($beforeHash -ne $afterHash) { throw "Source changed while reading: $relativePath" }
    $sources += [ordered]@{path=$relativePath; sha256=$afterHash}
}
$status = $documents[0]
$portfolio = $documents[1].payload
$xs = $documents[2]
$invariant = [Globalization.CultureInfo]::InvariantCulture
function To-Amount($Value) { [decimal]::Parse([string]$Value, $invariant) }
function To-Text([decimal]$Value) { $Value.ToString($invariant) }

[decimal]$entry = 0
[decimal]$marketValue = 0
foreach ($holding in $portfolio.holdings) {
    $entry += (To-Amount $holding.quantity) * (To-Amount $holding.average_cost)
}
foreach ($position in $status.positions_detail) { $marketValue += To-Amount $position.market_value }
$cash = To-Amount $portfolio.cash
$fees = To-Amount $portfolio.total_fees
$initial = To-Amount $status.initial_cash
$equity = $cash + $marketValue
$gross = $marketValue - $entry
$net = $equity - $initial
if ($entry + $cash + $fees -ne $initial) { throw 'Initial cash identity failed' }
if ($gross - $fees -ne $net) { throw 'Gross less fees identity failed' }
if ($equity -ne (To-Amount $status.total_equity)) { throw 'Saved equity mismatch' }
if ($net -ne (To-Amount $status.net_pnl)) { throw 'Saved net P&L mismatch' }

[decimal]$xsEntry = 0
[decimal]$xsMarketValue = 0
foreach ($leg in $xs.open) {
    $xsEntry += (To-Amount $leg.shares) * (To-Amount $leg.entry_open)
    $xsMarketValue += To-Amount $leg.market_value
}
$heg = @($xs.open | Where-Object symbol -eq 'HEG')
if ($heg.Count -ne 1) { throw 'Expected one HEG leg' }
$hegEntry = (To-Amount $heg[0].shares) * (To-Amount $heg[0].entry_open)
$hegParentValue = To-Amount $heg[0].market_value
$xsInitial = To-Amount $xs.capital
$xsCash = To-Amount $xs.cash
if ($xsEntry + $xsCash -ne $xsInitial) { throw 'XS initial cash identity failed' }
$xsGross = $xsMarketValue - $xsEntry
$otherGross = $xsGross - ($hegParentValue - $hegEntry)
$costRatio = To-Amount $xs.rule.cost_ratio
$pricedEntry = $xsEntry - $hegEntry

# Canonical decimal text preserves the source precision. This script writes only stdout.
[ordered]@{
    sources=$sources
    method='Independent decimal reconciliation of saved snapshots; no prices fetched and no book mutated.'
    flagship=[ordered]@{
        mark_timestamp=$status.timestamp_ist
        positions=$portfolio.holdings.Count
        initial=To-Text $initial
        entry=To-Text $entry
        cash=To-Text $cash
        paid_lifetime_fees=To-Text $fees
        market_value=To-Text $marketValue
        equity=To-Text $equity
        marked_price_pnl=To-Text $gross
        net_pnl_after_paid_fees=To-Text $net
        return_percent=To-Text ($net / $initial * 100)
    }
    xs_monthly=[ordered]@{
        mark_dates=@($xs.open.asof_date | Sort-Object -Unique)
        funded_positions=@($xs.open | Where-Object { (To-Amount $_.shares) -gt 0 }).Count
        closed_positions=@($xs.closed).Count
        initial=To-Text $xsInitial
        cash=To-Text $xsCash
        entry=To-Text $xsEntry
        raw_parent_only_market_value=To-Text $xsMarketValue
        raw_gross_pnl=To-Text $xsGross
        heg_entry=To-Text $hegEntry
        heg_parent_value=To-Text $hegParentValue
        heg_apparent_pnl=To-Text ($hegParentValue - $hegEntry)
        other_positions_gross_pnl=To-Text $otherGross
        round_trip_cost_ratio=To-Text $costRatio
        modeled_round_trip_reserve_all_entry=To-Text ($xsEntry * $costRatio)
        other_positions_cost_reserved_pnl=To-Text ($otherGross - $pricedEntry * $costRatio)
        full_economic_nav='UNKNOWN: resulting-company entitlement has no verified valuation in this snapshot'
    }
} | ConvertTo-Json -Depth 8
