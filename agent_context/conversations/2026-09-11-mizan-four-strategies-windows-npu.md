# Sanitized conversation: four strategies, TimesFM, NPU and Windows delivery

DATE: 2026-09-11  
STATUS: Captured; implementation and evidence remain separately governed  
SOURCE: User discussion of September 10-11, local read-only inspection, linked project records  
PRIVACY: No credentials, raw chats, account identifiers, or private device identifiers retained

## User intent and confirmed scope

The user wants QuantOS to become useful Windows software and wants future agents to remember this
discussion. They asked why both Mizan paper books lose money, what retraining needs, whether Google
TimesFM is useful, and whether the laptop NPU can run the models. They intend TimesFM for personal
research. They explicitly clarified that there must be TWO additional short-horizon candidates,
not just one model or a TimesFM feature silently added to an existing strategy.

| Strategy track | Intended role | Scope clarification |
|---|---|---|
| Existing Mizan Flagship | Longer holding period; currently about 10 held trading sessions | Preserve running artifact/history; evaluate retrained candidates separately |
| Existing XS-Monthly | Approximately 21-session holding rule | A momentum ranking rule, not necessarily a trainable model; evaluate rule changes as new versions |
| New QuantOS short-horizon | Newly trained, simple baseline model first | Evaluate exactly 1, 2 and 3 sessions held after entry |
| New TimesFM short-horizon | Separate frozen Google TimesFM forecast candidate | Evaluate the same 1/2/3 holds, universe, execution and cost assumptions |

These are four strategy families, not an instruction to hold four large neural networks in RAM.
The short horizons are trading sessions, not calendar days or intraday round trips. In the current
label builder, decision close k -> entry open k+1 -> exit open k+horizon; horizons 2/3/4 map to
holds 1/2/3. Future changes must prove the entry/exit timestamp mapping again.

The goal is evidence of positive net expectancy with acceptable risk, not a promise of profitability.
Virtual-money operation does not automatically update weights, validate a model, or authorize live
capital. No live-money order routing was authorized in this discussion.

## Original loss diagnosis and required scientific work

Read [the dated loss diagnosis](../../reports/mizan_loss_diagnosis_20260910.md) for calculations,
source links, timestamps and hashes; its figures are snapshots, not current balances.

- Flagship's September 10 snapshot lost INR 12,769.60, comprising INR 11,696.95 marked price loss
  and INR 1,072.65 historical fees. The frozen historical model had weak research evidence.
- The purported top-quintile validation screen and the live loader were different models: an
  eight-feature research fit versus the older fifteen-feature weights. Evaluation must bind the
  exact artifact, feature transforms, portfolio rule and execution convention that actually runs.
- XS-Monthly's gross loss of INR 1,928.33 included INR 6,084 apparent HEG price loss across a
  demerger. The 13-share resulting-company entitlement was missing from the paper book. Keep the
  priced parent holding and separately disclose the resulting asset as unpriced when necessary;
  do not invent its value, delete the parent, or reverse the full price gap as profit.
- Report gross price P&L, paid costs, prospective costs, priced equity and unpriced assets clearly.
  Benchmark both strategies on matched dates, exposure, universe and execution assumptions.
- Corporate-action corrections require external authority and consistent features/labels/return
  accounting, with fees on executable raw prices. A gap alone is not an adjustment factor.
- Use chronological walk-forward tests, train-only transforms/calibration, purge/embargo for
  overlapping labels, realistic fees/spread/slippage/liquidity, adverse-cost/delay stresses,
  multiplicity accounting, preserved final holdout and subsequent forward paper evidence.
- TimesFM starts zero-shot. Assess net trading performance and incremental benefit over cash,
  simple return/momentum models and an aligned benchmark, not forecast error alone. Pretraining
  overlap is uncertain; retrospective success alone cannot establish unseen-data performance.

## Progress that supersedes the earlier discussion

Inspection on September 11 at `eae79270894cbe4fc8403142ee90168201a8f555`, with concurrent
uncommitted work. The following are another implementation agent's reported results; this task did
not independently certify or rerun them.

- [Current program owner](../work/active/20260910-1615Z-claude-mizan-correction-and-short-horizon-program.md)
  already owns the corrections, retrain, short-horizon harness and NPU probe. Continue that work;
  do not start a duplicate experiment or consume additional trial ordinals casually.
- Governed retrain `trial_mizan_h11_003` has been published; reported DSR approximately 0.2466
  against the unchanged 0.95 gate, `RESEARCH_ONLY`. Retraining did not establish profitability.
- [Trial ledger](../../reports/short_horizon/TRIAL-LEDGER.md) lists all three short-horizon ridge
  holds as SPENT and failing the gate. The three TimesFM holds remain DECLARED at this read.
  Both arms now use a disclosed 45-name governed subset. The program summary and the active
  record's older stop/next-action sections still say no trials ran or name 50 symbols; those are
  stale relative to the ledger and later checkpoints. Reconcile before executing anything.
- [TimesFM CPU probe](../../reports/short_horizon/timesfm-probe.json) records successful load and
  finite outputs, context 512, checkpoint revision `43046b85ec22d584a13f8098c2ed39c889e129c2`,
  load 5.248 seconds, roughly 116 milliseconds per series in measured batches, peak 2568.8 MiB.
  It ran in the owner's isolated environment, not an NPU backend. These are probe measurements,
  not guaranteed production latency or total platform memory. Concurrent memory pressure was
  reported; schedule heavy training and TimesFM work separately until resource use is measured.
- [HEG notice](../work/active/20260910-NOTICE-xs-monthly-heg-entitlement-unpriced.md) reports
  disclosure in a separate analysis artifact; the running book correction remains outstanding.
- Independent adjudication remains outstanding; author tests and reports do not replace it.

### Correction to preserve: throughput estimate

The TimesFM feasibility/program prose says `423 x 2427 x 0.116 seconds` is about 33 days.
Direct Decimal arithmetic gives **119,088.036 seconds = 33.08001 hours = 1.37833375 days**.
This is an extrapolation of one measured configuration, before I/O and other overhead; it is not a
measured full study. The 50-name estimate of about 3.9 hours is arithmetically consistent.
Do not propagate the 33-days claim or change the frozen experiment after seeing results. Inform
the owner and keep the scientific scope/multiplicity history intact. Other agents' reports were
not edited by this documentation task.

## Hardware, execution backends and their limits

Hardware inspection established Snapdragon X X1-26-100, Hexagon NPU present/OK, Adreno integrated
GPU, 16 GB nominal RAM, Windows 11 ARM64, and no NVIDIA CUDA GPU.

**Binary architecture correction:** `platform.machine()` returned ARM64, but the actual QuantOS
Python 3.13.15 executable PE header is **0x8664 / AMD64** and `sysconfig.get_platform()` is
`win-amd64`. Rechecked September 11. This agrees with the older August hardware record and the
new NPU probe. Any interim inference of a native ARM64 Python environment is superseded. Distinguish
hardware/OS architecture, process architecture, extension wheels and accelerator runtime DLLs.

The [NPU probe](../../reports/short_horizon/NPU-FEASIBILITY.md) reports `NPU_UNREACHABLE` in its
tested environment. That establishes neither unusable hardware nor a successful TimesFM conversion.
The current general Qualcomm QNN route supports native Windows ARM64 on-device inference; the
existing x64 process cannot directly load ordinary ARM64 provider DLLs. A separate native ARM64
inference worker is an option; a wholesale immediate migration of the platform is not required.

Recommended baseline: CPU for small ridge models, XS ranking, features, backtests, accounting and
risk; optional NPU for a compatible neural forward pass. Train classical models on CPU. There is
no verified TimesFM 3 training/fine-tuning workflow on this Hexagon NPU and no established official
ready-made TimesFM 3 ONNX/QNN deployment found in the reviewed sources.

Potential NPU advantages are lower inference power/heat and freed CPU capacity. Costs include model
export/operator compatibility, fixed-shape handling, compilation, memory and driver/runtime support,
and reduced-precision changes to small return forecasts/rankings/trades. Benefits must be measured
end to end. A daily prediction may not justify conversion effort. NPU support changes speed/power,
not trading edge. Do not describe every supported NPU as integer-only; precision support depends on
the device and runtime version. Do not equate successful package installation with actual NPU use.

## TimesFM licensing context

The user described personal use; that intent is retained, but personal ownership is not proof that
profit-seeking or production use is permitted. TimesFM 3's default terms restrict commercial and
production uses. Keep the current candidate isolated as non-production research and reassess the
actual license before wider distribution or use. TimesFM 2.5 has a different Apache-2.0 licensing
route and is a different candidate whose performance cannot be inherited from 3.0. No licensing
exception or production permission was established in this conversation.

## Windows platform continuation

Read [the proposed Windows architecture decision](../decisions/20260911-windows-platform-and-inference-backends.md)
and [the implementation handoff](../handoffs/20260911-four-strategies-and-windows-delivery.md).
There is already a Studio desktop host. The remaining work is aligning packaging/launchers,
proving x64 versus ARM64 behavior, reliable background scheduling/recovery, bounded resources,
protected local state and credentials, and actual install/update/rollback/uninstall evidence.
This is a separate delivery track from model research; neither completion proves the other.

## External references checked September 10-11

- [Google TimesFM source](https://github.com/google-research/timesfm)
- [TimesFM 3 model license](https://huggingface.co/google/timesfm-3.0-pytorch/blob/main/LICENSE)
- [Qualcomm QNN integration](https://github.com/onnxruntime/onnxruntime-qnn)
- [QNN execution provider constraints](https://github.com/onnxruntime/onnxruntime-qnn/blob/main/docs/execution_providers/QNN-ExecutionProvider.md)
- [Microsoft Windows ARM emulation](https://learn.microsoft.com/en-us/windows/arm/apps-on-arm-x86-emulation)
- [Microsoft NPU overview](https://learn.microsoft.com/en-us/windows/ai/npu-devices/)
- [WebView2 runtime distribution](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/distribution)

Recheck fast-changing package/runtime/license facts when implementation resumes.
