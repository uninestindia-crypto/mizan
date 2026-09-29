# NOTICE: short-horizon trial 10 (Kronos) declared, on founder override

STATUS: NOTICE (additive; no other record or file is edited)  
FILED_UTC: 2026-09-29T04:50:00Z  
FILED_BY: Claude Code session, recording founder instructions of 2026-09-28  
FOR: `20260910-1615Z-claude-mizan-correction-and-short-horizon-program.md` (STATUS `ACTIVE`). It
owns `reports/short_horizon/**`, `src/quant_system/research_short_horizon/**` and
`scripts/run_short_horizon_experiment.py`.  
FILED UNDER: PROTOCOL §8.4. It names the numbers this work changes, rather than editing them.  
DECLARATION: `reports/kronos_trial/TRIAL-LEDGER.md`  
WORK RECORD: `agent_context/work/active/20260928-claude-kronos-trial.md`

## What happened

The founder instructed **one** Kronos zero-shot trial on the short-horizon family's data, subset,
labels and costs. The founder did so knowing that `reports/short_horizon/TRIAL-LEDGER.md` says "Do
not run a tenth trial".

- It is ordinal **10** of this family, at hold 3 only, deflated against 10.
- It is declared in its own ledger, `reports/kronos_trial/TRIAL-LEDGER.md`, because your ledger is
  your path.
- Your code is **imported, never edited**: `build_decisions`, `_noise_predictions`,
  `turnover_ranked`, `universe_bound`, `score_decisions`, `hold_specs`.

## What it changes in your evidence

1. **Multiplicity.** Your nine trials are published and re-scored at `num_trials = 9`. With trial
   10 counted, each would read lower against 10.
   - Nothing of yours is edited.
   - The published figures stay correct at the count that existed when they were scored, exactly
     as your ledger says of the move from 6 to 9.
   - If you re-score, 10 is the count in force from 2026-09-29.
2. **Your reserved holdout is no longer unseen.** The Kronos window is every decision from
   2024-07-01 to the store's end. That includes the final 252 sessions your program set aside as
   its untouched holdout. Kronos is scored on them once, by a fixed rule. Anyone who reads that
   result has seen those sessions.

## What it does not change

- No file under your claimed paths is modified, and your `DECLARED_TRIALS = 9` constant stays.
  `require_declared_trials` still passes against your own ledger.
- No gate threshold is adjusted. No short-horizon verdict changes: none of trials 1-9 passes at 9,
  so none passes at 10.
