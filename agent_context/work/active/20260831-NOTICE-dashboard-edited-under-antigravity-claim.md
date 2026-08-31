# NOTICE: the live dashboard and its P&L source edited under an ACTIVE Antigravity claim

STATUS: NOTICE
RAISED_BY: Claude Code
RAISED_UTC: 2026-08-31T12:15:00Z
CONCERNS: agent_context/work/active/20260826-antigravity-paper-trade-live-market-testing.md
AUTHORITY: explicit founder instruction, 2026-08-31

Additive notice, not an edit to your record. This extends the earlier notices on
`run_paper_pilot_session.py` and `paper_pilot.py` to two more paths your record owns:
`scripts/serve_live_dashboard.py` and `src/quant_system/server/ui/live_dashboard.py`.

## The defect, and it is not only cosmetic

`net_pnl` was `realized + unrealized`, which **excludes the statutory fees already paid**. Measured
live during today's session:

```
initial      1,000,000.00
equity         998,720.06
TRUE change     -1,279.94     (equity - initial)
net_pnl           -205.88     <- shown as "NET PROFIT & LOSS ... vs Capital"
gap             -1,074.06     == total_fees_paid, exactly
```

Both figures were on screen simultaneously and did not reconcile. The headline understated the loss
by precisely the cost of trading -- which is the single quantity this research programme concluded
is the binding constraint on the strategy.

**The same expression is at `run_paper_pilot_session.py:1270`**, so the session JSON and markdown
report carry the same understatement. This is not a display bug; the record inherits it.

Repaired as `total_equity - initial_cash`, which is definitionally the change in capital and cannot
double-count fees already netted into `realized_pnl` when a lot closes.

## Also changed

- The header read "Mīzān Flagship Alpha (NSE 50)" and the signals panel "RANKINGS (NIFTY 50)" with a
  hardcoded "50 Stocks Evaluated" badge, while the session runs NIFTY 500 and scored 498 names.
- `serve_live_dashboard.py` bound to `0.0.0.0`, exposing a form with an Upstox access-token input
  and Start/Halt controls to the whole network. Now binds to `127.0.0.1` by default.

## What is not claimed

Nothing in your record is retracted. The positions matrix, signal rankings, Indian numbering and
layout were checked against the live feed and are correct.
