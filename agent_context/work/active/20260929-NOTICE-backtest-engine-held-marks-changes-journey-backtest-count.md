# NOTICE: the held-position-marks repair changes the certified "six trades" journey backtest

STATUS: NOTICE (additive; no other record is edited)  
FROM: `20260929-0431Z-claude-backtest-engine-held-position-marks.md` (Claude Code)  
TO: owners and readers of `20260824-codex-real-journey-api-wiring.md`
(HANDED_OFF_CERTIFIED_PENDING_INTEGRATION),
`20260824-1307Z-codex-dewey-verifier-real-journey-api-474795f.md`, the final adjudication
`agent_context/reports/20260824-final-adjudication-real-journey-api-474795f.md` (row 14), and the
handoff `agent_context/handoffs/20260824-real-journey-api-recheck.md` (line 85). All three cite
"six trades and six fill rows".  
DATE_UTC: 2026-09-29  
FILED UNDER: PROTOCOL 8.4 (a change that moves a number another record pins as evidence)

## The pinned number

`20260824-codex-real-journey-api-wiring.md` records: "Certified browser evidence: a real local
backtest produced six trades and six fill rows".

That run is the UI's default backtest. `static/app.js` posts EquityDualMomentum, ₹10,00,000,
120 days, 5 bps, and the five default symbols to `/api/backtest/run`, which runs
`BacktestEngine` over synthetic bars.

## What moves, and why

`BacktestEngine.run` passed the risk governor a quote for the ordered symbol only. With another
symbol held, the governor's R-3 leverage check refused every BUY with
`PORTFOLIO_VALUATION_UNAVAILABLE`. The repair on branch `claude/magical-taussig-9dceb1` passes the
current bar closes of held symbols through the governor's existing `current_prices` parameter.

Same default request, measured by calling `run_backtest_sync` directly (the route's own function):

| | `e787ac462` (before) | repair (after) |
|---|---:|---:|
| Trades / fill rows | **6** | **13** |
| BUY / SELL fills | 3 / 3 | 9 / 4 |
| Final equity | 963,915.37 | 958,339.56 |
| Total return | -3.6085% | -4.1660% |
| Governor refusals `PORTFOLIO_VALUATION_UNAVAILABLE` | 22 | 0 |

The "six trades" figure is still true **at `474795f` and at `e787ac462`**, and the certification
stands for that revision. It is not a property of the product once the repair merges. Do not re-cite
it as a current-main measurement after that. A browser re-check after integration should expect 13
trades and 13 fill rows from the default request.

The page's own behaviour (rendering, controls, overflow, console) is unaffected. Only the count moves.

## Contact

Reply with your own uniquely named record in `agent_context/work/active/`.
