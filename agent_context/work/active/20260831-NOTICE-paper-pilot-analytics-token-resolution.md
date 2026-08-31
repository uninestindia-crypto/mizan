# NOTICE: scripts/run_paper_pilot_session.py token resolution changed under an ACTIVE Antigravity claim

STATUS: NOTICE  
RAISED_BY: Claude Code  
RAISED_UTC: 2026-08-31T06:40:00Z  
CONCERNS: `agent_context/work/active/20260826-antigravity-paper-trade-live-market-testing.md`  
RELATED: `agent_context/work/active/20260831-claude-upstox-token-semantics.md` (the measurement)  
AUTHORITY: explicit founder instruction, 2026-08-31 ("I write a coordination notice and make the change")

This is an additive notice, not an edit to your record, and not an accusation. PROTOCOL section 3
forbids rewriting another agent's record; section 8.4 makes a uniquely named notice the way to
reach you. This is the third such notice against this file.

## Section 8.4 preconditions checked before editing

Your record states `Blockers and conflicts: None` and `Next safe action: Present full market close
reconciliation and daily performance report to the user`. Neither names a gate, certification, or
review that must land before this file changes, and neither pins a number this change would
invalidate. Your recorded evidence — session `paper_ses_20260826_132755_IST`, equity
Rs 9,99,300.63, P&L Rs -345.55, 0.00 Paisa discrepancy — is a completed historical session and is
untouched by a change to which environment variable supplies the token.

## What changed under your claim

`assert_upstox_usable()` and `fetch_upstox_live_quotes()` now resolve the quote credential from
`UPSTOX_ANALYTICS_TOKEN` first, falling back to `UPSTOX_ACCESS_TOKEN`.

## Why — measured, not assumed

Upstox issues a free **Analytics Token**, one per user, roughly one year of validity. Measured
against the live API on 2026-08-31 with the founder's own token:

| Probe (analytics token) | Result |
|---|---|
| `v2/market-quote/quotes`, 10 batched — this file's exact call pattern | **HTTP 200**, all 10 with depth + volume |
| `v2/market-quote/quotes`, single instrument | HTTP 200 |
| `v2/market-quote/ltp` | HTTP 200 |
| `v3/historical-candle/intraday/.../minutes/1` | HTTP 200 |
| `v2/user/profile` | HTTP 401 `UDAPI1221` — static-IP restricted |

Token claims: `exp` 2027-08-23 03:30 IST (356 days remaining), `isExtended`,
`isMultiClient: False`, `isPlusPlan: True`.

The standard access token expires 03:30 IST the morning after issue, and Upstox V2 issues no
refresh token — so it must be renewed by hand every trading day. Before this change,
`UPSTOX_ANALYTICS_TOKEN` appeared **zero times** in all Python source, so a valid year-long token
sitting in `.env` was invisible and the session aborted anyway. Simulated directly:

```
analytics token in env: True
RESULT: session ABORTS -> QuoteFeedError
  UPSTOX_ACCESS_TOKEN expired at 2026-08-31 11:04 IST, 1:00:00 ago...
  there is no second feed to fall back to.
```

An unattended daily schedule that dies whenever the operator forgets a manual step is not an
unattended schedule.

## What this does NOT change

- **The expiry guard stays.** Your file's comment records that it caught eight days of sessions
  running on a substitute feed under a "CONFIGURED" banner. That guard is correct and is
  preserved; it now validates whichever token was actually selected, and names it in the error.
- **The single-source rule stays.** No fallback feed is introduced. The pilot still uses Upstox or
  does not trade.
- No change to `paper_pilot.py`, `serve_live_dashboard.py`, `view_live_pnl.py`, `server/app.py`,
  `data/universe.py`, or `logs/paper_runs/`.

## What you should be aware of

- `--upstox-token` on the CLI, and the `upstox_token=` parameter, still override everything. Their
  behaviour is unchanged.
- The static-IP restriction on `/user/profile` means a deployment from a different IP than the
  development machine should re-probe before trusting the analytics token there. Quotes, batched
  quotes and intraday candles were unaffected from this machine.
- The corrections in the two prior notices remain open and are not addressed here.

## What is not claimed

Nothing in your record is retracted, and no judgement is made about whether your work was correct
at the revision you wrote it against.
