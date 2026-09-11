# TimesFM 3.0 on this machine: it runs, and the throughput constrains the study

**It works.** `google/timesfm-3.0-pytorch` loads and forecasts correctly on this Windows-on-ARM
machine. That was not a given — the environment is emulated x86-64 (see `NPU-FEASIBILITY.md`) and
`torch` had to have a wheel for it.

**And it is slow enough to change the experiment design.** At ~116 ms per series per decision, the
full 423-name universe over 2,427 decision dates is about **33 days of compute**. That is not a
number to work around quietly; it is a constraint that has to be declared before the trials, because
the alternative is silently shrinking the study until it finishes and then reporting it as if it had
always been that size.

Reproduce:

```bash
D:/quant_system_workspaces/scratch/timesfm-probe-20260910/Scripts/python.exe scripts/timesfm_probe.py
```

Machine-readable: `reports/short_horizon/timesfm-probe.json`.

## Pinned versions

| Item | Value |
|---|---|
| Checkpoint | `google/timesfm-3.0-pytorch` |
| **Resolved revision** | **`43046b85ec22d584a13f8098c2ed39c889e129c2`** |
| `timesfm` | 3.0.2 |
| `torch` | 2.14.0+cpu, wheel tag `cp313-cp313-win_amd64` |
| `numpy` | 2.5.3 |
| Environment | `D:/quant_system_workspaces/scratch/timesfm-probe-20260910` — isolated; the QuantOS `.venv`, `pyproject.toml` and `uv.lock` are untouched |
| Fine-tuning | **None.** Zero-shot, as declared in the trial ledger |

## Measured cost

| Measure | Value |
|---|---:|
| Checkpoint load | 5.2 s |
| **Peak working set** | **2,568.8 MiB** |
| Single-series forecast, horizon 1 / 2 / 3 | 283 / 264 / 291 ms |
| Batched, 8 series | 116 ms/series |
| Batched, 32 series | 149 ms/series |
| Batched, 128 series | 116 ms/series |

Batching amortises per-call overhead roughly 2.4x and then plateaus around **116 ms/series**. The
32-batch figure being worse than 8 and 128 is measurement noise on a machine that was not otherwise
idle; the plateau is the number to plan against, not the best single reading.

**2.57 GB is the other operational constraint.** On a 16 GB machine running a training job at the
same time, that is enough to matter — this session lost a governed retrain to memory exhaustion while
the probe held its weights. TimesFM work and training work should not be scheduled concurrently here.

## What the throughput means for the study

```text
423 names × 2,427 decision dates × 0.116 s ≈ 33 days
```

Infeasible. Some scope has to give, and the choice must be declared in advance:

| Option | Cost | What it gives up |
|---|---:|---|
| Full universe, full history | ~33 days | — |
| Full universe, most recent ~500 sessions | ~6.8 hours | Regime coverage; ~2 years is one regime |
| 50-name subset, full history | ~3.9 hours | Cross-sectional breadth; reintroduces selection risk |
| 100-name subset, ~1,200 sessions | ~3.9 hours | Some of both |

**None of these is chosen here.** Choosing after seeing which one produced a better number is exactly
the failure the trial ledger exists to prevent, so the choice belongs in the ledger as a declaration
before the TimesFM trials run — and the subset, however chosen, is a disclosed limitation of every
TimesFM number that follows.

The simple-model arm has no such constraint: it is a ridge fit, and it runs on the full universe and
full history in minutes. So the two arms **cannot** be compared on identical data unless the simple
model is also restricted to the TimesFM subset. It must be. Comparing a full-universe simple model
against a subset TimesFM would confound model quality with sample size, and the difference would be
uninterpretable.

## Two defects found in the probe itself, worth recording

Both produced plausible-looking output while being wrong, which is the failure mode that matters.

**1. The 2.5 loader silently looked like a 3.0 failure.** The first probe called
`timesfm.TimesFM_2p5_200M_torch.from_pretrained` against the 3.0 checkpoint and got
`RuntimeError: Missing key(s) in state_dict: "tokenizer.hidden_layer.weight" ...`. Read quickly, that
looks like "the 3.0 checkpoint is broken on this platform". It is not: 3.0 has its own class,
`TimesFM3Forecaster`, and loads in 5 seconds. The probe now reports the available module attributes
on a load failure so the next person sees the real API surface instead of guessing.

**2. Peak memory reported `None` next to real timings.** `GetProcessMemoryInfo` was called without
explicit `argtypes`, so ctypes marshalled the process HANDLE as a 32-bit int and the call failed
silently on 64-bit Windows. The probe printed `peak memory: None MiB` beside genuine latency figures
— which reads as "it used no memory" rather than "the measurement failed". Fixed with explicit
`argtypes`/`restype`; the real answer is 2.57 GB, which is not a rounding difference from nothing.

## Licence, restated because it constrains use rather than just attribution

TimesFM 3.0's default licence is **non-commercial and non-production**. This work is the founder's
personal, non-production research within that licence. No live-money routing, no commercial
decision-making, and no training of another model on its outputs.

Version 2.5 is Apache-2.0. If this line of work ever needs a commercial path, 2.5 is the checkpoint to
evaluate — and it is a *different model*, so its results would not transfer.

## Pretraining overlap, declared before any result

The TimesFM model card does not establish one exhaustive pretraining cutoff, and NSE daily equity
history is public. A retrospective test on 2016–2026 NSE bars **cannot be assumed uncontaminated**.

The consequence is asymmetric, and it is declared here so it cannot be dropped later:

- A **negative** result stays informative. A model that may have seen this data and still cannot beat
  0.224% round-trip costs is strong evidence against the strategy.
- A **positive** result is not evidence of forecasting skill on unseen data, and would need a genuine
  out-of-sample confirmation — a forward period after the model's publication, or a market its
  pretraining plausibly excludes — before supporting anything.

## Future covariates

`predict` and `predict_batch` accept `past_only_covariates` and `past_future_covariates`. The second
is a leakage surface by construction: anything placed there is presented to the model as *known* over
the forecast window. Only values genuinely published before the decision timestamp may go there. No
covariates are used in the declared zero-shot trials.
