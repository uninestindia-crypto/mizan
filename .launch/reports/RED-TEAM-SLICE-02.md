# Red Team report — Slice 2 immutable evidence and recovery

DATE: 2026-08-20  
REVIEWER: independent Founder Mode Red Team agent  
FINAL VERDICT: PASS

## Reproduced finding

### Major — Windows crash recovery misclassified an exited worker as live

- **Family:** failure injection / operability.
- **Reproduction:** start an evidence commit in a Windows `spawn` process; stop it at any `CommitPhase`; join it; immediately call `EvidenceStore.recover()`.
- **Observed before repair:** all six phase cases raised `EvidenceBusy`. `GetProcessTimes` continued returning the creation identity for an exited process that remained queryable through an open parent handle.
- **Expected:** an exited writer is stale and recovery proceeds without a false live-owner refusal.
- **Blast radius:** a Windows restart after an interrupted evidence commit could remain unable to recover while another process retained the exited worker handle.
- **Disposition:** fixed. `_windows_process_identity` now requires `GetExitCodeProcess == STILL_ACTIVE` before returning creation identity. The spawned-process matrix kills the writer at all six phases and all six pass.

No other Blocker, Major, or Minor defect was reproduced.

## Independent evidence

```text
Focused Slice 2 suite: 58 passed
Reviewer demo subset: 10 passed
```

The reviewer independently confirmed:

- deterministic near-limit commit and verified reload;
- safe identical deduplication and conflicting-ID refusal;
- cooperative cancellation without visible partial evidence;
- real process termination at every commit phase;
- blob, manifest, marker, and active-pointer corruption rejection;
- deterministic valid/invalid index rebuild;
- simultaneous-process exclusion and live-recovery refusal;
- governed Slice 1 acquisition-to-evidence binding;
- atomic active-reference A → B → A rollback.

## Not probed

- Physical power loss or storage-controller write-cache failure.
- Real disk exhaustion at every individual publication phase.
- Sustained multi-process contention at production volume.
- A literal 100 MiB fixture; boundary behavior uses scaled configuration fixtures.
- OS-process termination during active-reference replacement; the pointer boundary uses exception injection.

## Final adjudication

The documented Slice 2 boundary has no unresolved release-blocking finding. PASS.
