# Amendment 1 to the Kronos trial declaration: compute scope, fixed by the declared rule

**Written 2026-10-06 02:15 IST, after the timing probe and before any real Kronos forecast exists.**
The only things run before this file are the environment set-up, a hash check of the code and weights, the
`forecast --dry-run` (no model loaded, no forecast made), and the probe below, which reads **no market data**.

Declaration: `reports/kronos_trial/TRIAL-LEDGER.md` ("Compute scope rule, declared before the timing probe").
That file is claimed by `agent_context/work/active/20260928-claude-kronos-trial.md` and is **not edited**; this
amendment lives in `reports/kronos_cloud_run/`, and a notice record tells the claim owner.
Probe output: `reports/kronos_cloud_run/kronos-probe.json`, SHA-256 `a0de443e7c4e9e478d8f6029bbf8bdbdf08f11e2ed6d2caae70e34e387b81446`.

## The measurement

Synthetic random-walk bars, 45 names per batch, 512-bar context, 4 forecast steps, one warm-up call then 3
timed repeats per configuration, 529 decision dates (from the dry run). Seconds are per decision date.

| Order | Model | S | Repeats (s) | Per date (s) | Projected hours | 14 h or less? |
|---:|---|---:|---|---:|---:|---|
| 1 | base | 5 | 676.9, 696.0, 710.6 | 694.51 | 102.05 | no |
| 2 | base | 1 | 118.7, 116.0, 113.5 | 116.09 | 17.06 | **no, by 3.06 h** |
| 3 | small | 5 | 195.8, 202.8, 188.2 | 195.60 | 28.74 | no |
| 4 | small | 1 | 37.5, 36.7, 36.0 | 36.74 | 5.40 | **yes** |

## The choice, by the declared rule

The rule takes the first configuration, in that order, whose projected total runtime is 14 hours or less.
Rows 1 to 3 exceed it. Row 4 fits. **The trial runs Kronos-small, S = 1.** Names, dates, context, hold,
sampling, seed rule, the 0.00224 threshold and the scoring are unchanged from the declaration.

Base S = 1 missed by about three hours, and a container has no "night" to fit into. The rule was declared
before the probe as a 14-hour budget and is applied as written. It was not relaxed after the timings were
seen, because choosing the larger model once the numbers were known would be a choice made with the result
of the measurement in hand.

## What differs from the declaration, stated before the result

1. **Platform.** The declaration names a native-ARM64 Windows interpreter. This run is Linux x86_64, 4
   vCPU, CPython 3.12.3, `torch 2.14.0+cpu`, `numpy 2.5.3`, `pandas 3.0.6`, four torch threads. The
   code commit, weights, library versions and every declared parameter are identical, and all were verified
   by hash (code: three SHA-256 values and the commit's git blob SHA-1s; weights: SHA-256 against both the
   ledger and the hash the Hub reports for that revision). A different CPU architecture and operating
   system can change floating-point results, and with them the seeded draws, so **this run is not
   guaranteed bit-identical to a laptop run of the same trial.** It is the same declared trial, not a second
   one. If the laptop also finishes it, one result is scored and published, and the existing-file
   refusal in `scripts/run_kronos_trial.py` enforces "scored once" for whichever is scored first.
2. **The weekday pause is off.** Compute scope rule 4 pauses the forecast on weekdays 08:45-16:30 IST and on
   battery "so the paper books keep their machine". No paper book runs in this container.
   `reports/kronos_cloud_run/run_generator.py` disables only that scheduling rule. It changes when the
   forecast runs, never what it computes. The per-date checkpoint and resume are untouched.
3. **Outputs are written here.** `--out` points at `reports/kronos_cloud_run/`, because
   `reports/kronos_trial/` is claimed by another record.
4. **Probe contention.** Nothing else heavy ran during the probe; the figures are the probe's own.

## What this does not change

Nothing follows this trial: no second model size after a result, no other hold, no threshold search, no
fine-tuning. A pass would read `PASS_PENDING_INDEPENDENT_CHECK` and promote nothing. No order exists on any
path here, and neither laptop paper book is touched.
