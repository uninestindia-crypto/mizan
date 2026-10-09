# Kronos-base zero-shot trial: frozen declaration (short-horizon trial 11)

**Frozen 2026-10-06 10:40 IST, before any forecast of this trial exists.** Before this file: the trial-10 result, a
hash check of the pinned code and weights, and an inputs file built from the repository and proven identical to the
data trial 10 used (all 23,805 `last_close` values match exactly). No trial-11 forecast has been generated on any
machine.

The rule this file inherits from the short-horizon and trial-10 ledgers: **a trial not listed here cannot be added
after a result is seen.**

## Why this trial exists, and what it overrides

- **Founder instruction, 2026-10-06:** "you should have run Kronos's biggest and best model; your first priority is
  to test and finalise ... a model which has the highest probability and maximum chance of profitability", and to
  make it downloadable to run locally, and to run it on a third party like Kaggle if possible.
- **It overrides a rule the founder himself set.** `reports/kronos_trial/TRIAL-LEDGER.md` says nothing follows trial 10:
  "no second model size after a result". The same file says "any further attempt is ordinal 11, with its own dated
  declaration". This is that. The founder chose it knowingly.
- **Why trial 10 did not use the biggest model.** Its declared compute rule was a 14-hour budget written for a laptop
  night. Base with one path projected 17.1 hours and was excluded by three hours; base with five paths projected
  102 hours. That rule chose Kronos-small with one path. The choice was applied as written and not raised with the
  founder at the time. It should have been.
- **The prior, stated before the result: expect it to fail.**
  - Trial 10 (Kronos-small, one path): Sharpe -0.444, net -6.65%, deflated Sharpe 0.013 against 0.95, rank IC
    t = 1.32, top-quintile edge t = 0.45. It lost to holding cash.
  - A larger model that averages five paths should forecast with less noise. Whether that clears a 0.224% round
    trip over a three-session hold is exactly what is untested, and nothing in 111 earlier attempts says it will.
  - The founder's wish for the model with the highest chance of profit is not something a trial can deliver. A trial
    can only report whether this one configuration cleared the bar.
- **This is not a search.** One configuration, one run, scored once, judged against eleven attempts. **Nothing follows
  it, whatever the result:** no other size, no other path count, no other hold, no threshold search, no
  fine-tuning. Any further attempt is ordinal 12 with its own declaration. Choosing the larger model because the
  smaller one failed is a decision made with a result in hand; the deflation against 11 prices that in.

## What changes from trial 10, and nothing else

| | Trial 10 | Trial 11 |
|---|---|---|
| Model | `NeoQuasar/Kronos-small` (24.7M) | **`NeoQuasar/Kronos-base` (102.3M)**, with `Kronos-Tokenizer-base` |
| Paths averaged per forecast, S | 1 | **5** |
| Machine | Linux x86_64 CPU, 4 cores | **any**: a GPU (Kaggle or similar) is expected; a local or cloud CPU is allowed |
| Compute budget rule | 14 hours | **none**. There is no fallback: if base with five paths cannot be run, the trial waits. It is never run with fewer paths or a smaller model |
| Deflation | 10 trials | **11 trials** |

Identical to trial 10, and verified by hash rather than by assertion: the 45-name subset and its adjusted total-return
OHLCV (the inputs file below), the 512-bar context, four forecast steps, `T = 1.0`, `top_p = 0.9`, `top_k = 0`, the seed
rule `20260929 + decision_date.toordinal()` with one batch per date, the window (decisions from 2024-07-01), the hold
(3 sessions), the rule (**long if and only if `predicted_return > 0.00224`**, else cash), the labels and costs, the
scoring harness, the controls (`NOISE-K`, 30 seeds; `ALWAYS_TRADE`; `PREVIOUS_SIGN`; `CASH`), the diagnostics, and the
gate (`GatePolicyV1` defaults: DSR 0.95 or more, max drawdown 0.15 or less, 5 or more trades).

`predicted_return = predicted_open[k+4] / predicted_open[k+1] - 1`, both opens model outputs, exactly as in trial 10.

## Why five paths

The founder asked for the biggest and best model and did not name a path count. Five is the lowest-noise setting the
original trial-10 ledger listed first, `(base, S = 5)`, before the compute rule demoted it. It is the faithful reading
of "best". **If the founder prefers one path, say so before any forecast exists. After that this is locked.**

## Machines, and which result counts

A GPU changes floating-point results, and with them the seeded draws, so a GPU run, a laptop CPU run and a cloud CPU
run of this trial are not bit-identical. The runner records the device, the torch version and the GPU name in the
output. The rule, declared now so nobody chooses between outputs afterwards:

- **The first forecast file to complete** (all 23,805 forecasts) **and pass the integrity checks in
  `scripts/score_kronos_trial11.py` is the one scored.**
- **Any other run of this trial, on any machine, is discarded unscored.** It is not compared, not averaged and not
  consulted. `scripts/score_kronos_trial11.py` refuses to score if a trial-11 result exists anywhere under `reports/`.
- Nobody may re-run on a different machine because a result looks disappointing.

## Pinned artifacts

| Artifact | Value |
|---|---|
| Generator, `scripts/generate_kronos_forecasts.py`, run unmodified (SHA-256, checked by the runner) | `ef17b128de13f93b50a6874c5e637c8c8d2840b55966a07c6e470aef94d49e8a` |
| Scorer, `scripts/run_kronos_trial.py`, run unmodified (SHA-256) | `8bc4186d568db2aad07ea34907979725388acce623ba137e6800a655d8f14099` |
| Inputs, `reports/kronos_trial11/kronos-inputs.json.gz` (SHA-256) | `fdbbdd152c582355aabd9ee827d02eac61ca4642133fd10da21f43af2c2cd9c4` |
| Kronos code, `shiyu-coder/Kronos` commit | `67b630e67f6a18c9e9be918d9b4337c960db1e9a` |
| `model/__init__.py` | `f8f856ca3fedadcaac97e196be23d1aeda1c3c9ffe8903d66d43ea3bcac6240c` |
| `model/kronos.py` | `0a5f90282e2039c2de0771473419715c845def154896dbd0f5747837e6241032` |
| `model/module.py` | `a07edbadc0e96804c8158c021bbc6063bb7cc43b34d7fc470d5c8ff2005a409f` |
| `NeoQuasar/Kronos-base` revision | `2b554741eca47781b64468546e77fef3e85130e6` |
| `NeoQuasar/Kronos-base` `model.safetensors` (SHA-256) | `abff193acab6db1a0368e9773e75799d11403b6d054ee6d5f0a11aeabc5f4b83` |
| `NeoQuasar/Kronos-Tokenizer-base` revision | `0e0117387f39004a9016484a186a908917e22426` |
| `NeoQuasar/Kronos-Tokenizer-base` `model.safetensors` (SHA-256) | `59d85f6af76a2c3b8240ea06cb21db4213b4eeca053f246b23e29cf832fc6bee` |

All of these were verified current on the Hub and upstream on 2026-10-06: no newer Kronos release exists, and the
Hub lists only `Kronos-mini`, `Kronos-small` and `Kronos-base`. The runner verifies every hash on every machine and
refuses to run on a mismatch. Library versions (torch, numpy, pandas) are recorded, not pinned, because a GPU host
supplies its own.

## Verdict

**PASS only if all three hold:** (1) the gate passes; (2) the candidate's Sharpe beats the best of the 30 `NOISE-K`
seeds; (3) the candidate's Sharpe beats `ALWAYS_TRADE`. Otherwise `RESEARCH_ONLY`. A pass reads
`PASS_PENDING_INDEPENDENT_CHECK` and promotes nothing: an agent that did not write this code must re-run it, and a
forward paper period must follow. Trial 10 passed two of the three checks while losing to cash, so those two alone are
not evidence of an edge. No live-money path exists (T4 is excluded).

## Contamination and disclosed biases

- **A second look at the same 529 dates.** The window, the names and the labels are exactly trial 10's, and trial 10's
  result is already known. This is not an independent sample; it is the same data seen through a different model.
- **Contamination bound is the authors' statement.** Every scored target is dated after Kronos's stated pre-training
  cutoff (June 2024). If the real cutoff were later, contamination could only flatter a result.
- **Survivorship and liquidity selection** in the 45-name subset favour the candidate. A negative under a favourable
  bias is a stronger negative.
- **The reserved holdout is already seen**, by trial 10.
- **Demergers.** Decisions near an unsized corporate action have no label and are not scored.

## Ledger

| # | Family | Hold | Status | Result | Recorded |
|---|---|---:|---|---|---|
| 11 | Kronos-base zero-shot, 5 paths (MIT) | 3 | **DECLARED** | not yet run | 2026-10-06 |
