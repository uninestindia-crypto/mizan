# NOTICE: flagship fee display and model identity changed under Antigravity's claim

STATUS: NOTICE (additive; no other record is edited)
OWNER: Claude Code (Opus 5), filer
FILED_UTC: 2026-09-14
FOR: `20260826-antigravity-paper-trade-live-market-testing.md` (STATUS `ACTIVE`), which owns
  `scripts/run_paper_pilot_session.py`, `scripts/view_live_pnl.py` and
  `src/quant_system/server/ui/live_dashboard.py`
AUTHORIZATION: founder instruction, 2026-09-14, in answer to an explicit question naming this repair
  and naming this claim as the one it crosses. Item 2 of the repair order in
  `reports/loss_diagnosis_20260913/DIAGNOSIS.md`.

## The defect, measured before it was changed

`logs/paper_runs/live_paper_status.json` as of the 2026-09-11 session:

```text
net_pnl          : -13729.82     <- lifetime (equity minus the book's starting capital)
total_fees_paid  :      0.00     <- this session's fills only; 09-11 was a hold day
```

Reconstructed independently from the same file and `portfolio_state.json`:

```text
entry consideration 853,407.04 + fees 1,072.65 + cash 145,520.31 = 1,000,000.00
```

So **1,072.65 of statutory fees had in fact been paid, and were already inside that -13,729.82**,
while the field beside it read zero. `scripts/view_live_pnl.py:54` rendered it as "Statutory NSE Fees
Paid" and the dashboard as "Statutory NSE Fees Paid", neither qualified by period. A reader
subtracting the displayed fees from the displayed P&L gets the wrong answer; a reader concluding the
book has traded for free gets a worse one.

This is the same class of defect as the HEG entitlement: a number that reads as economic truth and
is not. It is smaller, and it is not a mismeasurement — the value was correct for what it measured.
It was labelled as something else.

## What changed

| File | Change |
|---|---|
| `run_paper_pilot_session.py` | rolling status now publishes `session_fees_paid`, `lifetime_fees_paid` (carried + today) and a `fees_basis` string. `total_fees_paid` is **kept unchanged** so no existing consumer breaks |
| `view_live_pnl.py` | prints "NSE Fees, this session" and "NSE Fees, lifetime (already inside TOTAL NET P&L)"; falls back with a stated caveat when a payload predates the new fields |
| `live_dashboard.py` | the KPI tile is relabelled "Statutory NSE Fees, Lifetime" and prefers `lifetime_fees_paid`, with the session figure in its subtitle. On an old payload it shows the session figure and says so |

## Model identity

The diagnosis also asked that reports name the exact artifact under observation. `model_name` and
`version` are shared by every retrain of this product — every flagship is "Mizan Flagship Alpha
(NSE 50) v1.0.0" — so they identified nothing, and a *newer* flagship model card describing
`trial_mizan_h11_003` made that actively misleading.

- `src/quant_system/modeling/mizan_model.py` gains `DEFAULT_MODEL_PROVENANCE`: the trial id
  (`trial_mizan_h11_002`), the evidence model id, the verdict, DSR `0.175990` against the `0.95`
  gate, and RIDGE Sharpe `-0.410755`. This was stated only in a docstring, so nothing that ran could
  repeat it. **That file is claimed by
  `20260910-1615Z-claude-mizan-correction-and-short-horizon-program.md`**, the same claim the founder
  authorised crossing for item 3; a separate notice covers that record.
- `run_paper_pilot_session.model_provenance()` publishes it plus the model card hash into both the
  rolling status and the session JSON.
- The dashboard header now reads `... | Trial: trial_mizan_h11_002 · RESEARCH_ONLY | Marked: <ts>`.

No weights, thresholds, features, risk limits or decisions changed. The model card schema and its
hash payload are untouched — the provenance is a module constant, not a new card field.

## Verification

- Full suite **1,519 passed**, forwards. Ruff check and `ruff format --check` clean across 671
  files. `mypy src launcher.py scripts` clean across 208 files.
- No file under `logs/` was written. `git status --short logs/` is empty.
- The next scheduled session is the first to emit the new fields; both renderers were written to
  degrade honestly on the current payload rather than to assume them.

## Residual, stated rather than hidden

`lifetime_fees_paid` is `portfolio.total_fees + total_fees` — the resumed carried total plus this
session's fills — because `portfolio` is not rebuilt from the ledger until after the live loop. If a
future change moves `state_from_ledger` inside that loop, this double counts. There is no test
pinning that ordering, and adding one would mean writing a test for a path under this claim that I
have not otherwise touched.
