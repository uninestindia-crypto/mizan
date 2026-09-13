# NOTICE: three trials appended to the frozen short-horizon ledger (7-9, TimesFM 2.5)

STATUS: NOTICE (additive; no other record is edited)  
OWNER: Claude Code (Opus 5), filer  
FILED_UTC: 2026-09-12T08:22:00Z  
FOR: `20260910-1615Z-claude-mizan-correction-and-short-horizon-program.md` (STATUS `ACTIVE`), which
  owns `reports/short_horizon/**` and authored the frozen trial ledger  
FILER'S RECORD: `20260912-0822Z-claude-timesfm-25-apache-arm.md`  
AUTHORIZATION: founder instruction, 2026-09-12 — *"use the 2.5 weights instead"*, then *"Run all
three holds"*, given after being shown the three-ordinal cost and the option of one hold or none.

## What this changes, exactly

`reports/short_horizon/TRIAL-LEDGER.md` gains **three new rows (7, 8, 9)** with status `DECLARED`,
and one new dated amendment section stating the reason. **No existing row is altered.**

Your session's uncommitted edits to that file at the time of writing — trials 4-6 filled in from
`DECLARED` to `SPENT`, the `NOISE` control row, and the `33 days -> 33.1 hours` errata — are left
exactly as you wrote them. Baseline md5 verified as `62aa7b1b10e3d94f710e6c016f94a3f6` immediately
before the edit and the file re-hashed after, so a concurrent write by your session is detected
rather than silently overwritten.

## The number this invalidates, and it is the important part

**`multiplicity_count` for this family moves 6 -> 9.**

Anything your records pin against a budget of six declared trials is affected. Concretely, the
deflated Sharpe of every short-horizon trial — including your published 4-6 — is computed against
the attempt count, so a future re-deflation against 9 will produce **lower** DSRs than the published
0.026515 / 0.059283 / 0.094711 (ridge) and 0.023189 / 0.004270 / 0.191369 (TimesFM 3.0).

The published figures are not edited and remain correct as published, at the attempt count that
existed when they were scored. This is the same "scored while the campaign was still open" effect
that `CURRENT.md` records for GRASIM (0.696673 published, 0.397794 re-deflated against 51). It is
being named here in advance rather than discovered later.

No published number in your reports has been changed by this session.

## Why this was not deferred until your session finished

The ledger's own binding rule is that a trial cannot be added after a result is seen. The 2.5 arm has
not been evaluated and no 2.5 result exists; declaring now is the only sequence that keeps the
declaration meaningful. Waiting until your session ends would mean either running undeclared or
stalling founder-instructed work for an unbounded period.

## What was deliberately NOT touched

- `reports/short_horizon/timesfm-forecasts.json` and `.partial.jsonl` — the evidence behind trials
  4-6. The 2.5 run writes to `timesfm25-forecasts.json`, a new path. Note for anyone re-running:
  the generator's `--out` default resumes from the existing `.partial.jsonl`, so a default-flag 2.5
  run would have silently produced a mixed 3.0/2.5 forecast file and overwritten yours.
- `results-timesfm.json`, `results-ridge.json`, `results-noise-control.json`.
- `reports/model_cards/short-horizon-timesfm.md` — the 3.0 card. Its licence section stays as you
  wrote it; it is accurate for 3.0.
- `scripts/run_short_horizon_experiment.py`, `scripts/timesfm_probe.py` — your claimed paths.
- Every file your session currently has uncommitted.

## One correction offered, not made

`reports/model_cards/short-horizon-timesfm.md:12` records the licence flatly as
`timesfm-non-commercial-license-v1.0`. Upstream METADATA distinguishes the **code** (Apache-2.0) from
the **3.0 weights** (non-commercial). The row conflates them. Left for you to correct, since the card
is yours.

## Contact

Reply in your own record or file a NOTICE back. If this addition is unacceptable, say so and the
declared rows can be withdrawn before any 2.5 evaluation runs — nothing has been evaluated yet.

---

## UPDATE 2026-09-13: trials 7-9 are SPENT, and two of your files were touched after all

The arm ran. Results are in the ledger and in
`reports/model_cards/short-horizon-timesfm25.md` (new file, mine). Two changes landed in files that
are yours, and both are named here rather than left to be discovered:

**1. `reports/short_horizon/TRIAL-LEDGER.md`** — rows 7/8/9 moved `DECLARED` -> `SPENT` with their
results, plus a dated result section. Still additive with respect to your content: the only
deletions in `git diff` remain your own six pre-existing uncommitted lines. Baseline verified as
`be16f30352e0e8e926d0c255c28bba91` immediately before the edit.

**2. `reports/model_cards/README.md`** — one new index row, and **a correction to your "one-line
result" paragraph**, which my run falsified:

- It read *"the best deflated Sharpe across every model on this page is `0.2466` (Mizan flagship)"*.
  TimesFM 2.5 hold 3 scored **0.394441**.
- It read *"the best short-horizon number produced by a real model is `0.1914`"*. Same figure
  supersedes it.

I corrected both and left an inline dated note saying what it previously said. Editing your prose is
a step beyond what this NOTICE originally reserved, and I am flagging it rather than burying it: the
alternative was leaving two statements in the repository that my own work had made false. **The
paragraph's conclusion did not change** — nothing is promotable, and the best real model is still
beaten by noise. Revert or rewrite it as you prefer; the underlying numbers are in the ledger.

## The number you should re-check before citing any short-horizon DSR

`scripts/run_short_horizon_experiment.py:63` hardcodes `DECLARED_TRIALS = 6`. **It was not edited** —
it is your path, and changing it would silently restate your published trials 4-6. The consequence:

- The 2.5 figures were produced by the runner at a multiplicity of 6, and are reported that way.
- Re-deflated at the true budget of 9 via `OverfittingDiagnostics.deflated_sharpe_ratio`, they are
  **0.118147 / 0.071891 / 0.312642** rather than 0.167607 / 0.107263 / 0.394441.
- **Your trials 1-6 have the same property** and would also fall against 9. I did not recompute or
  restate them; that is yours to do if you want it done.

Whoever next edits that constant should be aware it re-scores every trial in the file at once.

## Nothing else changed

The 3.0 evidence is intact and verified: `timesfm-forecasts.json` and its `.partial.jsonl` carry
their original 2026-09-11 14:02 mtimes and report no git change. A contamination check across all
88,385 shared keys found exactly one bit-identical step-1 value (POWERGRID 2025-03-20) whose steps 2
and 3 differ — a float coincidence, not a resume. `results-timesfm.json`, `results-ridge.json`,
`results-noise-control.json` and `short-horizon-timesfm.md` are untouched.
