# Slice 02 Evidence — Immutable Evidence and Recovery

STATUS: CANDIDATE — Red Team PASS; verifier attempt 1 blocked and remediated; recheck pending
DATE: 2026-08-20

## Outcome

Slice 2 adds a local, content-addressed evidence store for datasets and the later governed resource
types. Publication uses canonical UTF-8 JSON/JSONL, SHA-256 identities, deterministic gzip chunks,
same-volume staging, an atomic immutable-directory rename, a bound commit marker, and mandatory
published-byte readback before success is returned.

The Slice 1 governed Upstox acquisition now has one adapter that revalidates its row count, content
hash, manifest hash, content-derived dataset ID, received range, and instrument identity before
preparing the exact records for immutable publication.

## Demonstrated behavior

- deterministic near-limit commit/reload and cross-root byte identity;
- identical safe deduplication and conflicting-ID refusal;
- canonical rejection of floats, over-depth input, oversized integer encoding, duplicate order keys,
  secret-bearing fields, traversal IDs, unsupported schemas, and configured size limits;
- blob, manifest, marker, active-reference, row-count, byte-count, and total-order verification;
- cooperative cancellation and injected failures at every pre-publication phase;
- real Windows spawned-process termination at all six publication phases;
- live-process refusal, stale-lease quarantine, process-start identity, and phase heartbeats;
- disk preflight and write-failure invisibility;
- deterministic source-of-truth index rebuild with invalid-resource reporting;
- active-reference A → B → A rollback and failed-replacement preservation;
- symlink and resolved-path containment checks;
- no pickle, joblib, database, or executable object deserialization.

## Verification before clean-clone handoff

| Gate | Result | Evidence |
|---|---|---|
| Focused Slice 2 suite | PASS | 58 tests across three evidence test files |
| Repository suite | PASS | 164 tests |
| Repository coverage | PASS | 88.69%, required minimum 80% |
| Ruff lint and format | PASS | 127 files formatted |
| Strict Mypy | PASS | 66 source files |
| Code Craft | PASS | 9 Slice 2 source files, zero findings |
| Test Craft | PASS | 3 Slice 2 test files, zero findings |
| Vulture | PASS | zero findings at 80% confidence |
| Detect-secrets | PASS | zero application candidates after repairing the Windows path-separator exclusion |
| Mutation proof | PASS | both marker binding and active-target binding mutations killed |
| Red Team | PASS | one Major found, repaired, and independently rechecked |

## Red Team finding and repair

A real six-phase Windows process-kill matrix showed that an exited-but-still-queryable process was
misclassified as live. All six recovery cases initially raised `EvidenceBusy`. Windows liveness now
requires `GetExitCodeProcess == STILL_ACTIVE` before the process-creation identity can match. All six
cases pass after repair. The raw report is `.launch/reports/RED-TEAM-SLICE-02.md`.

## Explicitly not proven in this slice

- physical power loss or controller write-cache loss;
- literal 100 MiB fixtures and sustained production-volume process contention;
- real disk exhaustion at every individual publication instruction;
- process termination during active-reference replacement;
- CI, dependency vulnerability audit, SBOM, packaging, and installer recovery;
- model features, labels, training, promotion, and financial-model evidence, which begin in later slices.

## Independent verifier

Attempt 1 at `c2596ea` proved every test/static/recovery claim but correctly returned `BLOCKED`
because the committed secret-scan exclusion matched `/` only and scanned the generated Windows
environment. The cross-platform separator regex is repaired and its exact gate passes locally.
A fresh verification of the remediation revision is pending. Raw attempt evidence is stored in
`.launch/reports/VERIFIER-SLICE-02-ATTEMPT-01.md`.
