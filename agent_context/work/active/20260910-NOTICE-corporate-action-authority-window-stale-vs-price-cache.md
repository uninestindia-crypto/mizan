# NOTICE: the corporate-action authority ends 2026-08-21 while prices are ingested daily, so any action after that date is structurally invisible

STATUS: NOTICE (additive; no other record or path is edited)
FILED_UTC: 2026-09-10
FILED_BY: Claude Code (read-only diagnosis at founder request)
SEVERITY: **P2 Major for both paper books.** Not a defect in any published research result.

## Who this is addressed to

- `20260910-codex-mizan-loss-diagnosis.md` (ACTIVE, Codex) — this is a cause of the XS book's
  reported loss. Codex's `Next safe action` is to trace both books' P&L; this notice supplies one
  measured cause so the diagnosis does not have to rediscover it.
- `20260903-hermes-xs-monthly-screen-new.md` (ACTIVE, Hermes) — owns
  `logs/xs_monthly_new/` and `src/quant_system/research_xs_monthly/`. The affected leg is in that
  book's state. **Nothing under either claim has been read-modified; this record is additive only.**

## The defect

Every dataset manifest in `data/evidence/market-cache/nifty500-refresh-20230828-20260827` carries:

```
"adjustment": {"method": "PROVIDER_UNSPECIFIED", "status": "RAW"}
"corporate_action_authority": {"effective_from": "2016-08-22", "effective_to": "2026-08-21", ...}
```

Bars are **RAW** (unadjusted), and the corporate-action authority that would let a consumer adjust
them **stops at 2026-08-21**. The price cache is refreshed daily and currently holds bars through
**2026-09-09**. That is a 19-calendar-day window, widening by one session per day, in which prices
are ingested but **no authority covers them**. A corporate action in that window cannot be detected
by any consumer, because the evidence needed to detect it does not exist in the repository.

## It has already fired, and it is the whole of one book's reported loss

`HEG` gapped from a 2026-09-04 close of 728.25 to a 2026-09-07 open of 260.00 — **-64.3% overnight
on 3,615,221 shares** — then resumed ordinary trading at the new level (-5.00%, +1.60%). That is the
signature of a re-based price series, not a crash.

`data/evidence/market-cache/.../corporate-actions/nse-corporate-actions-HEG.json` holds 4 records,
the most recent a 2026-07-22 dividend. It contains no 2026-09-07 event **and structurally cannot**:
its `effective_to` is 2026-08-21.

Measured effect on the XS-Monthly paper book (`logs/xs_monthly_new/paper_watch/state.json`,
99 open legs, 0 closed, asof 2026-09-09):

| | Value |
|---|---:|
| Book gross return | **-0.2235%** |
| HEG leg alone | **-6,084.00** = **-0.608 pp of NAV** |
| Book gross **excluding HEG** | **+0.4870%** |
| Legs positive | 57 / 99 |
| Median leg | +0.597% |

**The book's entire reported loss is this one unadjusted corporate action.** Without it the basket
is up. This is not a claim that the momentum rule works — 99 legs over 7 sessions establishes
nothing either way — it is a claim that the reported number does not measure the rule.

## Frequency, measured rather than assumed

Overnight gaps >25% across all 499 cached symbols, 2023-09 to 2026-09:

| Date | Symbol | Gap | prev_close -> open | ratio |
|---|---|---:|---|---:|
| 2024-02-14 | FORCEMOT | +31.3% | 3352.35 -> 4400.00 | 0.762 |
| 2025-04-07 | SIEMENS | -50.3% | 4928.15 -> 2450.00 | 2.011 |
| 2025-05-22 | ABFRL | -63.6% | 268.95 -> 98.00 | 2.744 |
| 2025-10-14 | TMPV | -39.5% | 660.75 -> 400.00 | 1.652 |
| 2026-04-30 | VEDL | -62.6% | 773.60 -> 289.50 | 2.672 |
| 2026-09-07 | HEG | -64.3% | 728.25 -> 260.00 | 2.801 |

**6 events in 3 years across 499 names — roughly 2 per year.** Rare, but each one that is held costs
an equal-weight book ~0.6 pp of NAV, which is larger than either book's entire P&L to date. The rate
is low; the per-event impact is not.

## Second-order risk, stated but NOT measured

A trailing-window ranker scoring RAW closes will read a corporate action inside its formation window
as a genuine ~-60% momentum reading. For a top-20% long screen that suppresses the name (harmless
direction), but for any reversion-signed model — which is what `mizan_cross_sectional_ridge` is,
7 of 8 coefficients negative per `20260825-1500Z-claude-mizan-pooled-model.md` — the same reading
becomes a strong **buy**. I have not measured whether this has selected any name in either book, and
I am not claiming it has. It is named so whoever owns the repair sizes it rather than assuming it.

## What I did not do

No file under any active claim was modified. No cache was rebuilt, no authority refetched, no
strategy, model, test, or configuration changed. This is a read-only observation with a reproduction.

## Reproduction

```
python - <<'PY'
import json,gzip,os,glob
base='data/evidence/market-cache/nifty500-refresh-20230828-20260827'
for mp in glob.glob(base+'/store/datasets/*/manifest.json'):
    m=json.load(open(mp)); md=m.get('metadata',{})
    mh=md.get('mapping_history') or [{}]
    if mh[0].get('symbol')!='HEG': continue
    print(md['adjustment'], md['corporate_action_authority']['effective_to'])
    bp=os.path.join(base,'store',m['blobs'][0]['relative_path'])
    if not os.path.exists(bp): continue
    for l in gzip.open(bp,'rt'):
        r=json.loads(l)
        if '2026-09-04' <= r['exchange_date'] <= '2026-09-08':
            print(r['exchange_date'], r['open'], r['close'], r['volume'])
    break
PY
```

## Suggested repair, for whoever owns the cache

Not proposed as a change here, because the cache and both books are under other agents' claims.

1. Refresh the corporate-action authority on the **same cadence as the price cache**, so
   `effective_to` never trails the newest bar. The gap, not the adjustment method, is the root cause.
2. Fail closed: a consumer marking a position whose bar date exceeds its authority's `effective_to`
   should raise typed detail rather than mark silently. Today it marks silently, which is how a
   -0.608 pp phantom loss reached a book without any guard firing.
3. A ratio detector (|overnight gap| > 25% with no authority record) is a cheap backstop, but it is a
   detector, not a substitute for (1).
