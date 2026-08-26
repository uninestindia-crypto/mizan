# Active work: remove wall-clock dependence from the permanently-held-lease test

STATUS: ACTIVE  
OWNER: Claude Code — test craft  
TOOL: Claude Code  
STARTED_UTC: 2026-08-26T00:00:00Z  
STARTING_REVISION: `466d562b2bc2414c6cfc8bf3140eb8cb4e47f1fb`  
WORKTREE_OR_BRANCH: `D:\quant_system` on `main`

## Objective

`tests/test_evidence_publish_atomicity.py::test_a_permanently_held_lease_still_fails_closed` is
flaky under machine load. Make it deterministic without lengthening any timeout and without
weakening the guarantee it proves: a lease that is never released must still fail closed, and must
not leave `trials/trial_blocked` on disk.

## Owned paths

- `tests/test_evidence_publish_atomicity.py`
- `agent_context/work/active/20260826-claude-lease-wait-test-determinism.md` (this file)

## Non-goals

- `src/quant_system/evidence/**`. No production change is needed; the injection seam already exists.
- `test_commit_waits_briefly_for_a_contended_lease`, the sibling in the same file. It is timing-
  coupled too but was not reported flaky and proves the opposite guarantee. Assessed, left alone,
  reported to the founder.
- The remaining 10 `loop-in-test` / 2 `huge-test-file` craft findings elsewhere in the repo.

## Prior claim on this path, and why it is free

`20260825-claude-loop-in-test-repair.md` lists `tests/test_evidence_publish_atomicity.py` in its
owned paths, but records `STATUS: COMPLETE — every finding in an unclaimed file resolved`. PROTOCOL
§5 says a completed record is moved to `work/completed/`; this one was not. I treat a record that
declares itself COMPLETE as a released claim, and I have not edited it. Flagged to the founder as a
protocol-hygiene item rather than fixed unilaterally.

No other active record and neither live worktree (`codex/real-journey-api`,
`codex/release-manifest-integrity`) claims this path.

## Plan

1. Measure the baseline. DONE — 4 passed in 1.01s; 0 craft findings in this file.
2. Locate the real coupling. DONE — see rationale.
3. Rewrite the test against the existing injection seam. IN PROGRESS
4. Verify: file, full suite, ruff, ruff format, mypy, craft checker, both audits.

## Current step

Step 3.

## Decision rationale

**The coupling is not the 0.2s budget itself, it is that the budget is racing a 5s escape hatch.**
The holder thread runs `release.wait(timeout=5)` and then exits the `with` block, unlinking the
lease. `release` is only set in the test's `finally`, so during the assertion the sole way the lease
can disappear is that 5-second timeout. `LeaseManager.acquire`
(`src/quant_system/evidence/lease.py:108`) only returns a handle when `_write_new_lease` succeeds,
i.e. when the lease file is gone. So `EvidenceBusy` fails to raise exactly when the main thread is
starved long enough that the holder's 5s timeout fires first — which is what a loaded 8-core box
does. Lengthening `lease_wait_seconds` would make this *worse*, not better: it widens the window in
which the holder can time out first.

**The seam already exists and was never wired.** `LeaseManager.__init__` takes `monotonic` and
`sleep` (`lease.py:86-87`). `grep -rn "monotonic=\|sleep=" src/ tests/` returns nothing — they are
dead parameters, added for testability and never used. Using them is what they are for.

Decisions, with rejected alternatives:

- **Rejected: plumb `monotonic`/`sleep` through `EvidenceStoreConfig`.** Cleaner-looking, but
  `models.py` and `store.py` are shared contracts and PROTOCOL §4 puts evidence-schema and public-API
  changes under single-owner coordination. Adding production surface to fix a test is the wrong
  trade when the seam is already reachable.
- **Rejected: lengthen the timeout.** Explicitly excluded by the brief, and per the mechanism above
  it points the wrong way.
- **Chosen: swap `store._lease` for a `LeaseManager` on the same path with the same `wait_seconds`,
  driven by a fake monotonic clock that only advances when the retry loop sleeps.** The test already
  reaches `holder._lease` at two sites, so this is not new access. Ruff `select` does not include
  `SLF`, so no lint waiver is needed.
- **Chosen: delete the holder thread.** The docstring says "a lease that is never released". A
  handle acquired on the main thread and never exited models that exactly, with no timeout that can
  hand the lease back mid-assertion. This removes `held.wait(timeout=5)`, `release.wait(timeout=5)`
  and `worker.join(timeout=5)` — three more wall-clock budgets — rather than only the 0.2s one.

**What stays real:** the lease file, `os.open(O_CREAT|O_EXCL)`, the genuine `FileExistsError`, the
retry loop, the typed `EvidenceBusy`, and the on-disk assertion. Only the clock is fake.

Termination is provable rather than hoped for: every non-returning iteration calls `sleep`, which
advances the fake clock by a strictly positive `_LEASE_POLL_SECONDS`, so the deadline is reached in
a finite number of iterations. The retry count is not asserted — `0.025` is not exact in binary and
the loop may take 8 or 9 iterations to cross `0.2`. The test asserts that it retried at all, which
is the property that distinguishes a bounded wait from no wait.

## Commands and outcomes

| Command | Result | Evidence/notes |
|---|---|---|
| `.venv/Scripts/python.exe -m pytest tests/test_evidence_publish_atomicity.py -q` | PASS | Baseline, 4 passed in 1.01s |
| `node scripts/check-tests.mjs` | Baseline | 12 findings / 6 files repo-wide; 0 in this file |

## Files changed

- `tests/test_evidence_publish_atomicity.py`: pending.

## Blockers and conflicts

None.

## Stop point

Baseline measured, root cause identified, no edit made yet.

## Next safe action

Rewrite `test_a_permanently_held_lease_still_fails_closed` against the injected clock.
