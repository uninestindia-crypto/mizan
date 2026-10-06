# NOTICE: two sessions fixed the same Upstox quote defect; the fixes were reconciled

STATUS: NOTICE (additive; no other record is edited)  
FILED_UTC: 2026-10-06  
FILED_BY: Claude Code session, on the founder's instruction "merge all the branches, make main as latest as possible"  
FOR: `20261005-1930Z-claude-upstox-quote-key-shape.md` (STATUS `COMPLETED`, on branch `claude/loving-maxwell-rk25i4`) and
`20261005-claude-cloud-paper-and-kronos-run.md` (this session's own record)  
FILED UNDER: PROTOCOL section 8.4

## What happened

`UpstoxClient.fetch_market_quote` could never parse the real Upstox reply (keyed `NSE_EQ:INFY`, not by instrument key).
The founder started two sessions on it. One was a queued task card, which finished first (`9550ebb5`, branch
`claude/loving-maxwell-rk25i4`, 2026-10-05 19:34 UTC) and was never merged. The other (this session, `e52f4d86`) did not
know and merged to `main` in PR #4. The two conflicted in `upstox.py`, `upstox_parsing.py` and `tests/test_upstox_data.py`.

## How they were reconciled

The record's own conditions were read first (PROTOCOL section 8.4): `COMPLETED`, no merge precondition; its open items are
Windows-side audits and a release. Nobody else had touched those files since the fork. **The other session's implementation
was taken, because it is stricter**, and my earlier fix was dropped. Run against that implementation, 19 of my 22 tests passed
unchanged; the 3 that differed were each decided on merit:

1. **An entry found only by its symbol label, with no `instrument_token`:** mine accepted it, theirs refuses it. Theirs
   is right: a symbol is a label, not an identity, and is reused for other securities after corporate events.
2. **A level with a price but zero quantity** (two cases): theirs passed it through as a valid quote with size 0. **One
   addition was made to their parser**: it now raises `ProviderQuoteUnavailable`, like the `{price: 0.0, quantity: 0}` case, since
   there is no size to trade against. Two test cases were added to their existing parametrised test, written first and seen failing.

## What this changes

- Behaviour that **differs from my earlier merged fix** (`e52f4d86`, now superseded): token-less symbol-keyed entries are refused; the "no priced
  market" outcome is `retryable=True`; the timestamp must carry a zone; NaN and negative prices are schema drift.
- Verified against the real feed during market hours: INFY and RELIANCE parsed to two-sided quotes with real sizes.
- No number another record pins is changed. Test counts for `tests/test_upstox_data.py` go from 22 (my version) to 46.

## What it does not change

- The other session's record is not edited. Its Windows-only audits (`audit-agent-claims.ps1`, `audit-disk-layout.ps1`)
  were not run here either: there is no PowerShell in this container.
