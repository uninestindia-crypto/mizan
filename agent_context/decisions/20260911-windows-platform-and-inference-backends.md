# ADR proposal: Windows desktop delivery with optional inference accelerators

STATUS: Proposed; no formal .launch release scope or gate changed  
DATE: 2026-09-11  
OWNER: Codex documentation task; implementation owners to adopt exact paths  
DECIDERS: Platform/release owner with the founder's intended Windows product scope

## Context and constraints

QuantOS is intended to run as Windows software on the user's Snapdragon ARM64 laptop with 16 GB
RAM, while the existing release target is x64. Four strategy families are intended: the two existing
longer-horizon Mizan strategies plus separate QuantOS and TimesFM 1/2/3-session research candidates.
There are active source, CI and packaging owners. This proposal does not replace their work.

Current facts at `eae79270`, plus concurrent edits:

| Area | Code or record present | What has not been established by this review |
|---|---|---|
| Desktop | `quantos_studio.py` starts FastAPI/Uvicorn, polls readiness, opens pywebview or Edge/Chrome app mode, then browser fallback; requests shutdown on close | Packaged lifecycle on a clean user machine |
| Legacy launcher | `launcher.py` opens the default browser and binds Uvicorn to loopback | Whether this should remain the installer default |
| Packaging | Studio has a windowed PyInstaller spec; standard build and Inno installer select `quantos.exe` from the legacy spec; builder defaults x86_64 | One consistent shipped entrypoint and proven native ARM64 artifact |
| Dependencies | pywebview is an optional import and not declared in pyproject.toml | Reproducible desktop host/runtime availability without developer tools |
| Workers | `server/supervisor.py` uses spawn, one active governed operation, heartbeats, cancellation, persisted recovery | Frozen executable multiprocessing and orphan-free shutdown; no freeze_support call was found in either entrypoint |
| Scheduled paper work | Supervisory scripts and Windows tasks exist separately from Studio | Packaged close/reopen, sleep/resume, reboot and missed-session policy |
| Storage/secrets | Studio data/log/temp roots sit beside its executable; .env lookup searches cwd/parents | Non-admin writable layout and predictable protected credential storage for installed use |
| Release integrity | Hash/SBOM/manifest mechanisms exist | Fresh artifacts against the current lock; real signed install/upgrade/rollback/uninstall evidence |

Code presence is not test proof. The release verifier includes simulated/in-process fallbacks;
those cannot certify a real Windows installation lifecycle. A September 10 notice records stale
artifact/SBOM lock hashes. CI's latest owner reports format/type failures, superseding CURRENT.md's
older billing explanation. Recheck current gates instead of copying either historical status.

## Proposed decision

Keep the existing Python engine and desktop web UI. Converge on one explicit desktop host and one
documented headless worker entrypoint; reuse the Studio implementation rather than starting a new
frontend framework. Bind the installer, shortcuts, diagnostics and build manifest to the selected
entrypoint. If WebView2 is the supported host, package/detect the appropriate runtime and make
fallback behavior explicit. A browser fallback is not evidence that the intended desktop host works.

| Platform component | Execution location | Operational requirement |
|---|---|---|
| Desktop controls/charts | CPU and browser/WebView rendering, with ordinary graphics acceleration where available | Responsive while jobs run; accurate progress, cancel and failure states |
| Data ingestion, features, storage | CPU, network and disk | Cache/reuse data; preserve point-in-time provenance and handle stale/offline data explicitly |
| Backtesting/classical training | Bounded CPU worker processes | Keep heavy work away from the UI; checkpoint only through valid evidence contracts |
| Small Mizan scores / XS rankings | CPU | Avoid neural conversion work with no demonstrated benefit |
| TimesFM or future neural predictions | CPU reference; optional isolated native ARM64 NPU worker | Same model/input contract, measured parity and visible actual execution backend |
| Risk, paper fills, cash/fees/ledger | CPU with existing Decimal/domain rules | No accelerator-dependent accounting or weakened risk gates |
| Paper scheduling and recovery | Explicit Windows background component | Clear UI-close versus stop-session semantics, no duplicate jobs or fabricated missed fills |
| Cloud AI assistant/provider calls | Existing network API path | NPU does not speed a remote model; timeout/cost/error handling remains separate |

A small resource manager should serialize heavy training and TimesFM inference on this 16 GB host
until a measured budget supports concurrency. Four strategy entries must not imply four always-loaded
neural runtimes. Display model version, data timestamp, mode, actual backend and job health in suitable
diagnostics. Do not turn hardware details into steps required for ordinary research workflows.

## Options considered and rejected alternatives

| Option | Benefit | Cost / decision |
|---|---|---|
| CPU reference plus optional native ARM64 inference worker | Preserves working platform, isolates dependencies and accelerator failures | Recommended first experiment; versioned IPC/output contract and extra packaging needed |
| Entire platform native ARM64 | Potential performance/efficiency improvements | Worth a parallel clean build assessment; requires every binary dependency and desktop/runtime path to pass |
| x64 emulation only | Reuses current environment and distribution | Valid baseline if tested; does not establish QNN NPU access |
| Put all models and platform operations on NPU | No established advantage for most components | Reject: wrong execution target for UI, I/O, Decimal accounting and small ranking work |
| Rewrite the application in another desktop framework | Could provide another host | Defer: existing Studio can be completed; no measured need for a rewrite |

The optional worker must return model/weights identity, preprocessing/input identity, horizon,
decision timestamp, predictions, actual backend, latency and typed failure. Preserve the CPU result
as the reference. Validate conversions with train-only calibration where applicable, supported
shapes/operators, placement profiling and ranking/trade-decision agreement. Unknown backend or
unsupported model fails visibly. CPU fallback is allowed only as an explicit, recorded operational
policy with equivalent validated behavior and acceptable freshness; never label it NPU execution.

## Windows failure behavior and release acceptance

- Window close, background operation, cancellation and full exit must be distinct and predictable.
  Closing a UI must not silently orphan a worker or claim a paper session is still active.
- A sleeping/offline machine cannot execute scheduled market work. Resume must reacquire fresh
  data, report missed sessions and avoid replaying old signals as contemporaneous fills. Do not
  globally change lid/battery policy as an implicit packaging fix.
- Keep executable/model versions separate from mutable evidence and user state. Respect the
  install-drive layout contract; do not assume write permission beside a protected installation.
  Choose a writable state location explicitly and test migration/rollback without evidence loss.
- Protect credentials with a documented Windows-appropriate mechanism, retain loopback origin/host
  and CSRF boundaries, and keep secrets out of bundles, logs, exports and context records.
- Package architecture must reflect actual binaries, including extension wheels and NPU provider
  DLLs. Verify PE architecture; never infer it solely from platform.machine() or a zip filename.
- Rebuild against the exact lock/revision, verify hashes/SBOM and chosen signing mechanism, then
  test clean install, launch, workers, cancellation, reboot, upgrade, interrupted upgrade, rollback
  and real uninstall while preserving evidence. A native ARM64 claim requires its own proof.

## Consequences and next actions

No changes were implemented here. The next owner should first reproduce the packaged Studio
launch/worker path, select the consistent shipped entrypoint, and address architecture/dependency
failures before UI polish or NPU optimization. Model research continues on its existing CPU path.
Updates must retain a compatible previous app/model version and migration/rollback evidence; no
automatic updater or guaranteed rollback was established in this read-only review.

References: [conversation and sources](../conversations/2026-09-11-mizan-four-strategies-windows-npu.md),
[handoff](../handoffs/20260911-four-strategies-and-windows-delivery.md),
[release slices](../../.launch/SLICES.md), [disk layout](../DISK-LAYOUT.md).
