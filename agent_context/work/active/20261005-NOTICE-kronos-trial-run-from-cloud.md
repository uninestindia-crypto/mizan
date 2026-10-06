# NOTICE: short-horizon trial 10 (Kronos) was run to completion and scored, in the cloud

STATUS: NOTICE (additive; no other record or file is edited)  
FILED_UTC: 2026-10-06  
FILED_BY: Claude Code session, on founder instruction of 2026-10-05 ("run Kronos zero-shot short-horizon trial 10 in
the cloud exactly as declared ... and report the result whatever it is")  
FOR: `20260928-claude-kronos-trial.md` (STATUS `ACTIVE`). It owns `reports/kronos_trial/**`,
`scripts/generate_kronos_forecasts.py`, `scripts/run_kronos_trial.py` and `tests/test_kronos_trial.py`.  
FILED UNDER: PROTOCOL section 8.4. It names what this changes in your evidence rather than editing it.  
WORK RECORD: `agent_context/work/active/20261005-claude-cloud-paper-and-kronos-run.md`  
OUTPUTS: `reports/kronos_cloud_run/` (`AMENDMENT-1.md`, `kronos-probe.json`, `kronos-forecasts.json`,
`results-kronos.json`, `RESULT.md`, `run_generator.py`)

## What happened

Trial 10 was run exactly as `reports/kronos_trial/TRIAL-LEDGER.md` declares, by your scripts, unmodified, with
every output written under `reports/kronos_cloud_run/` because your folder is yours.

- Compute scope by the declared rule: base S=5 102.1 h, base S=1 17.1 h, small S=5 28.7 h, small S=1 5.4 h
  against the 14 h limit. **Kronos-small, one sample path.** Recorded in `AMENDMENT-1.md` and committed
  (`1c3b5d06`) before any forecast existed.
- 23,805 forecasts, 529 dates, 45 names; 23,637 scored decisions; 0 missing forecasts.
- **Verdict `RESEARCH_ONLY`.** Candidate Sharpe -0.444, net -6.65%, DSR 0.0134 against 0.95 (10 trials). It is
  less negative than the best of 30 NOISE-K seeds (-0.606) and than ALWAYS_TRADE (-0.956), and loses to CASH
  (0.000). Rank IC t = 1.32 and top-quintile edge t = 0.45, neither significant.
  Full table and reading: `reports/kronos_cloud_run/RESULT.md`.

## What it changes in your evidence

1. **Your ledger is stale.** Its trial table still reads `10 | Kronos zero-shot (MIT) | 3 | DECLARED | not yet run`.
   Your ledger also promised that the probe numbers and chosen configuration would be "appended below as Amendment
   1". That amendment exists, but at `reports/kronos_cloud_run/AMENDMENT-1.md`, not appended to your file. Neither
   edit was made, because the ledger is your path. Updating row 10 and pointing to the amendment is yours to do.
2. **The environment is not the declared one.** The ledger names a native-ARM64 Windows interpreter. This run is
   Linux x86_64, 4 vCPU, CPython 3.12.3, the same pinned code, weights and library versions, all hash-verified
   (weights against both the ledger and the hash the Hub reports for that revision). Floating-point results, and
   so the seeded draws, can differ across CPUs. **This run is not guaranteed bit-identical to a laptop run.**
3. **The weekday pause was disabled** by `reports/kronos_cloud_run/run_generator.py`, which overrides only
   `in_market_hours` and `on_ac_power` at runtime. No container has a paper book to protect. It changes when the
   forecast runs, never what it computes. Your file is imported, not edited.
4. **Multiplicity.** Ordinal 10 of the short-horizon family is now spent. Your published trials 1-9 stay
   correct at the count that existed when they were scored, and none passes at 10 either.
5. **Your reserved holdout was seen**, as your own notice of 2026-09-29 said it would be.

## An action for you, and why it matters

**The trial is spent. Do not score it a second time.** `scripts/run_kronos_trial.py` enforces "scored once" by
refusing an existing results file **at the path it is given**. A laptop run that scores into
`reports/kronos_trial/results-kronos.json` would not be refused by that guard, because that file does not exist,
and would create a second scored result of the same trial on possibly different forecasts. If the laptop's
forecast run has finished or does finish, it may be compared with `kronos-forecasts.json` to see how much the
platform moved the draws. It must not be scored. A stronger guard (for example, refusing when any
`results-kronos.json` exists anywhere under `reports/`) would close the gap; that file is yours, so I did not
touch it.

I do not know whether the laptop run produced forecasts. The repository showed none.

## What it does not change

- No file under your claimed paths was edited. `git status` shows `scripts/generate_kronos_forecasts.py`,
  `scripts/run_kronos_trial.py`, `tests/test_kronos_trial.py` and `reports/kronos_trial/**` unchanged.
- `tests/test_kronos_trial.py` still passes against the unchanged scripts (run with the neighbouring suites:
  92 passed forwards and in reverse file order).
- No short-horizon verdict changes. Nothing is promoted. No order exists on any path. Neither laptop paper book
  was touched.
