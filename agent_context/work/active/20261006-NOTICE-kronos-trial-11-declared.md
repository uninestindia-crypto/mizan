# NOTICE: short-horizon trial 11 (Kronos-base, five paths) declared, on founder instruction

STATUS: NOTICE (additive; no other record or file is edited)  
FILED_UTC: 2026-10-06  
FILED_BY: Claude Code session, recording the founder's instruction of 2026-10-06 ("you should have run Kronos's
biggest and best model ... download it, we will run it locally, and run it on a third party like Kaggle if possible")  
FOR: `20260928-claude-kronos-trial.md` (STATUS `ACTIVE`), which owns `reports/kronos_trial/**`,
`scripts/generate_kronos_forecasts.py`, `scripts/run_kronos_trial.py` and `tests/test_kronos_trial.py`; and
`20260910-1615Z-claude-mizan-correction-and-short-horizon-program.md` (STATUS `ACTIVE`), which owns the short-horizon
ledger and `DECLARED_TRIALS`  
FILED UNDER: PROTOCOL section 8.4  
DECLARATION: `reports/kronos_trial11/TRIAL-LEDGER.md` (frozen 2026-10-06 10:40 IST, before any trial-11 forecast)  
WORK RECORD: `agent_context/work/active/20261005-claude-cloud-paper-and-kronos-run.md`

## What happened

The founder knowingly overrode the "nothing follows trial 10" rule that he set on 2026-09-28. Your trial-10 ledger already
said "any further attempt is ordinal 11, with its own dated declaration", and this is that: **Kronos-base, five sampled
paths**, everything else identical to trial 10, any machine (a GPU is expected), scored once against **eleven** attempts.

## What it changes in your evidence

1. **Multiplicity is 11 from 2026-10-06.** Trials 1-10 stay correct at the count in force when each was scored. None passes at 11
   either. The short-horizon family's `DECLARED_TRIALS = 9` constant is not touched.
2. **A rule you wrote is overridden knowingly.** "No second model size after a result." The ledger is not edited.
3. **Trial 10's ledger row still reads `DECLARED / not yet run`** (also noted in `20261005-NOTICE-kronos-trial-run-from-cloud.md`).
4. **The "scored once" guard in your scorer is path-based.** This trial is scored through `scripts/score_kronos_trial11.py`,
   which refuses if a sentinel or any trial-11 results file exists anywhere under `reports/`. It found, and a test pins, the
   loophole that a results file written under another name would not have been refused.

## What it does not change

- No file under your claimed paths is edited. `scripts/generate_kronos_forecasts.py` and `scripts/run_kronos_trial.py` are
  **run unmodified**: the runner refuses the generator unless its SHA-256 is the declared one, and the scoring wrapper sets
  the scorer's `DECLARED_TRIALS` to 11 at call time, then corrects three label fields it writes as trial-10 literals.
  No number is touched.
- Nothing is promoted. No order exists on any path. Neither laptop paper book is touched.

## What I could not do

No GPU exists in the building container, there is no Kaggle credential, and `LIGHTNING_API_KEY` is set but empty. So the
forecast has **not been run**. The package to run it on a GPU is at `reports/kronos_trial11/kronos-trial11-package.zip`.
