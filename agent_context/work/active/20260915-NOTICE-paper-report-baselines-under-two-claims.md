# NOTICE: `run_paper_pilot_session.py` edited under two ACTIVE claims

FILED_UTC: 2026-09-15T09:00:00Z  
FILER: Claude Code (Opus 5)  
TYPE: NOTICE — additive, per PROTOCOL §3 and §8.4. Neither claimed record is edited.

## What was edited, and under whose claims

`scripts/run_paper_pilot_session.py`, claimed by:

- `20260826-antigravity-paper-trade-live-market-testing.md` — OWNER: Antigravity, STATUS: ACTIVE
- `20260914-claude-paper-book-accounting-repairs.md` — OWNER: Claude Code, STATUS: ACTIVE

## Authorization

Founder instruction, 2026-09-15: "add the baselines to the daily paper report."

## What changed

One pure helper (`session_baselines`) and one new section in the Markdown session report, plus a
`baselines` key in the session JSON. The report now states the book's return against equal-weight
of the same names, NIFTY 50 buy-and-hold, and cash, over the book's own holding window.

## What did NOT change

- No order generation, selection, sizing, hold clock, or `rebalance_executed` logic.
- No risk limit, no model, no trial, no multiplicity ordinal.
- No file under `logs/`. Saved history is not rewritten.
- No dashboard file. `live_dashboard.py` is untouched; the JSON key is there so a later dashboard
  change under its own claim can read the figures rather than re-derive them.

## What this invalidates

**Nothing either record pins as evidence.** No test count, coverage percentage, manifest hash, or
number the book acts on is changed by this. The session report gains a section; the session JSON
gains a key.

Owners of either claim: if you disagree with the baseline set or the window definition, the
reasoning is in `20260915-0900Z-claude-paper-report-baselines.md` under "Baselines chosen, and why
these" — in particular why PREVIOUS_SIGN and EQUITY_DUAL_MOMENTUM are excluded rather than
approximated.
