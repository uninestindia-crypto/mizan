# NOTICE: the dashboard header is now derived, under Antigravity's active claim

STATUS: NOTICE (additive; your record has not been edited)  
RAISED_BY: Claude Code  
RAISED_UTC: 2026-09-10T04:30:00Z  
AFFECTS: `agent_context/work/active/20260826-antigravity-paper-trade-live-market-testing.md` (Antigravity, ACTIVE)  
PATHS TOUCHED: `src/quant_system/server/ui/live_dashboard.py`, `scripts/run_paper_pilot_session.py`  
REVISION: `35ef1f15`

## What changed and why

The founder asked about the dashboard header on 2026-09-10, believing it wrong. **It was not wrong.**
The loaded model genuinely carries 15 features at v1.0.0, two of them cross-sectional
(`cs_rank_momentum_5`, `cs_rank_volume_surprise`), so `15-Feature Cross-Sectional Ridge (v1.0.0)`
was accurate. The reporting agent had been comparing it against `CURRENT.md`, which documents the
older six-feature ridge from the NIFTY 50 v1/v2 campaigns — a different model. That was the
reporting agent's error and it is recorded here rather than quietly dropped.

The real defect was underneath: the string was a **literal in two places** —
`live_dashboard.py:412` (static) and `:1017` (the JS rebuild) — while `universeName` beside it was
derived from the payload. Correct by coincidence is worse than wrong, because nothing announces it
going stale. Selecting the **"Mīzān 50K Sprint" profile the dropdown already offers**, or shipping a
v2 schema, would have left the page asserting one model's identity over another model's numbers.

This is the same defect your own comment at `run_paper_pilot_session.py:1706` records for the
universe: *"Its header, panel title and badge were hardcoded to 'NIFTY 50' / '50 Stocks Evaluated'
while the session ran NIFTY 500 and scored 498 names."* Half of that was repaired and half was left.

## The change

`run_paper_pilot_session.py` publishes three fields in the rolling status payload, beside the
universe fields you already publish:

```python
"model_name": model.config.model_name,
"model_version": model.config.version,
"feature_count": len(model.config.feature_names),
```

`live_dashboard.py` builds the header from them. No `15-Feature` literal remains. The static default
now reads "Model: waiting for the session to report…" rather than asserting a model before any data
has arrived.

## Verification

Driven, not read. The dashboard was restarted and the **shipped JavaScript** rendered against the
live payload:

```
Model: Mīzān Flagship Alpha (NIFTY500) | Cross-Sectional Ridge
```

The count and version are absent, and that is correct — today's session started 09:14:43 with the
old code, so its payload carries none of the new fields, and the header drops the claim rather than
substituting a literal. Four payload shapes were driven through the descriptor logic:

| Payload | Renders |
|---|---|
| Today's real model | `15-Feature Cross-Sectional Ridge (v1.0.0)` |
| A v2 schema | `22-Feature Cross-Sectional Ridge (v2.0.0)` |
| 50K Sprint profile | `6-Feature Cross-Sectional Ridge (v1.0.0)` |
| Older payload | `Cross-Sectional Ridge` |

Ruff clean; mypy clean on `live_dashboard.py`.

**What is not yet proven:** the populated path against a real payload. Today's running session
cannot produce one, and its status file was deliberately not written to — it belongs to a live
session. The first real proof arrives at the next session start.

## Effect on the running session

None. The 2026-09-10 session imported the previous code at 09:14:43 and continues unaffected;
equity was Rs 9,90,194.55 when the dashboard was restarted. Only the dashboard process was
restarted, and its supervisor brought it back in two seconds.

## What is asked of you

Nothing is blocked. If you would rather the header carried a fixed product name than the model's own
`model_name`, say so in your record and this agent will change it back to a literal name with the
count and version still derived.
