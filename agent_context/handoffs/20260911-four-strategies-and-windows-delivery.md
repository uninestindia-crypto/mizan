# Handoff: preserve four strategies and finish Windows delivery

STATUS: READY_FOR_ADOPTION  
FROM: Codex documentation/review task  
TO: Existing model-program owner and a coordinated Windows release owner  
DATE_UTC: 2026-09-11  
WORK_RECORD: `agent_context/work/completed/20260911-0612Z-codex-model-windows-context.md`

## Read first

1. [Sanitized discussion and dated facts](../conversations/2026-09-11-mizan-four-strategies-windows-npu.md).
2. [Proposed Windows/backend design](../decisions/20260911-windows-platform-and-inference-backends.md).
3. [Existing model-program owner](../work/active/20260910-1615Z-claude-mizan-correction-and-short-horizon-program.md)
   and the current [trial ledger](../../reports/short_horizon/TRIAL-LEDGER.md).
4. Repository startup/ownership protocol and current .launch state. Read all active records; this
   handoff does not transfer any other agent's path claims or authorize a concurrent state write.

## Confirmed objective

Retain existing Flagship and XS-Monthly, and build TWO distinct additional research strategies:
a newly trained QuantOS model and a separate TimesFM candidate, both evaluated for 1/2/3 held trading
sessions. Deliver the rest of QuantOS as reliable Windows software. NPU is optional inference
optimization, not a requirement for every strategy or platform component and not proof of edge.

## Already done and current stop point

This task saved context and reviewed existing code only. It installed nothing and ran no training,
holdout, benchmark, paper session, packaging build or product test. Other-agent work now includes
an adjusted governed retrain, an isolated successful TimesFM CPU probe, a failing current-environment
NPU feasibility result, and three spent short-horizon ridge trials. None establishes profitability
or independent certification. TimesFM trials remain declared at the last ledger read.

The actual Python binary is x64 on ARM64 Windows (PE 0x8664), independently rechecked here.
Studio is implemented; the normal packaging path still selects the other launcher. Do not rebuild
a desktop host from scratch or call the repository browser-only.

## Next safe work, in order

1. **Reconcile the current experiment state.** Read timestamps, manifests and the ledger before
   restarting jobs. Older program prose says six trials are unrun, while the ledger marks three
   ridge holds SPENT. Later checkpoints use 45 names, older text says 50. Preserve failed attempts,
   declared budgets, same-universe comparisons and holdout isolation. Check exact output/maturity
   alignment between close-time forecasts and next-open executable targets.
2. **Correct a planning arithmetic error in owned reports.** `423*2427*0.116 seconds` is 33.08001
   hours, not 33 days. This is only an extrapolation; rerun no experiment on that basis and do not
   silently amend a frozen budget after results. The report owner should append the correction.
3. **Finish the data/model evidence obligations.** Preserve the priced HEG parent and record the
   distinct unpriced resulting-company entitlement safely through the paper owner's lifecycle.
   Align costs, authority, labels, artifacts and portfolio rules; complete comparable evaluations,
   independent adversarial checks and clean-state verification. Do not promote a failing candidate.
4. **Align Windows packaging.** Select the shipped Studio entrypoint; align build specs, installer,
   shortcuts, diagnostics and manifest. Verify GUI dependencies and actual PE architecture. Test
   frozen multiprocessing bootstrap rather than assuming development-script behavior transfers.
5. **Integrate application lifecycle.** Define whether closing the window stops work or leaves an
   explicit background session. Test duplicate launch, cancellation, crash, sleep/resume, reboot,
   expired data/auth and missed sessions. Preserve evidence, no duplicate jobs or fabricated fills.
6. **Prove delivery and resource budgets.** Rebuild stale artifacts against the current revision/
   lock, resolve current CI failures with its owner, then test actual install/update/rollback/
   uninstall and state preservation. Bound concurrent RAM/CPU use on 16 GB. Native ARM64 and x64
   emulation are separate test targets. Optional native ARM64 NPU worker comes after CPU parity.

## Boundaries and acceptance

- Core money/risk/data safeguards stay on the validated CPU path. No live-money/T4 work is authorized.
- Personal TimesFM intent does not waive its license; preserve isolated research use and recheck
  distribution/production rights before bundling or exposing it as a shipped feature.
- Hardware/environment changes should use an isolated runtime and coordinated paths; do not replace
  the working .venv merely to probe NPU. Installing a QNN package is not proof of accelerator use.
- A CPU fallback must be explicit, validated and visible. Measure actual backend placement,
  end-to-end latency, working set and forecast/ranking/trade parity before recommending NPU.
- Label everything as code-present, author-tested, independently verified, or not tested. Required
  result: versioned evidence and an honest pass/fail report, even when no candidate is profitable.

## Files and verification

The new conversation, proposed decision, this handoff and this task's work record are the only
paths authored here. Existing source/runtime/report changes belong to other agents. Nothing was
staged or committed by this task. Final document/link checks and repository audit outcomes are
recorded in the completed work record. No current release gate is asserted by these documents.
