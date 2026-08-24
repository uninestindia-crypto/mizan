# Handoff: governed journey API independent recheck

STATUS: READY_FOR_FRESH_COMPLETION_RECHECK
OWNER: Codex server/API implementation owner
BRANCH: `codex/real-journey-api`
IMPLEMENTATION_COMMIT: `1e953f53d7d5e2ce920452845c6ea69c47decd75`
BASE_REVISION: `ac47d7cc03e4aa485e2c92d7022d33de3809a1f2`

## Scope

Independently review the truthful governed-journey server implementation. Dataset creation/listing
is implemented with real read-only Upstox acquisition, `PointInTimeBar`, supervised operations, and
immutable EvidenceStore publication. Feature, training, holdout, shadow, and paper journeys have no
persisted runtime adapter in this branch and therefore return typed unavailability or show disabled
controls instead of fabricated results. Live-money and broker writes remain excluded.

## Required adversarial targets

1. Exercise `POST /api/v1/datasets` through completion and verify request/provider/evidence identity.
2. Reuse one idempotency key with identical and conflicting payloads; verify deterministic replay
   and fail-closed conflict respectively.
3. Attempt mismatched symbol/instrument values, unknown/repeated query parameters, unsafe keys, and
   client-selected evidence roots.
4. Tamper with catalog evidence and verify listing fails closed without leaking paths or payloads.
5. Race cancellation immediately before publication and verify no immutable acquisition is written.
6. Confirm legacy and unsupported model/shadow/paper routes never emit fake successes, metrics,
   fills, quotes, P&L, or campaign state.
7. Confirm there are zero broker-write paths and that responsive light/dark states remain truthful.
8. Reject well-formed cursors that do not identify an exact verified dataset and verify the cursor
   binds the total `(created_at, dataset_id)` sort key.
9. Verify hash-valid but domain-invalid metadata, content hashes, record identity, and date ranges
   fail closed at catalog read.
10. Force cancellation during evidence staging, not only before commit, and verify no dataset is
    published unless publication has already won.
11. Confirm `/api/v1/operations/train` cannot create a placeholder operation or return invented
    metrics before the independently certified feature-schema-v2 adapter is integrated.

## Existing evidence

- Focused server/UI contract suite: 115 passed.
- Full suite normal test-file order: 891 passed in 53.27s; one third-party Starlette/httpx warning.
- Full suite reverse test-file order: 891 passed in 55.57s; same warning.
- Ruff, mypy over 124 source files, Node syntax, changed-path security scan, changed-path secret scan,
  OpenAPI generation, Git whitespace check, claim audit, and disk-layout audit: PASS.
- Mutation probe inverted the idempotency fingerprint comparison; the two intended tests failed,
  then passed after restoration.
- Real browser inspection at 1280x720 and 390x844, light/dark: no page overflow or console errors;
  mobile tabs remained readable, and governed feature/training/holdout/shadow/paper actions were
  disabled with truthful explanations.
- Seven completion-audit regressions were observed failing for the intended defects before repair,
  then passed. They cover domain-invalid evidence, invented cursors, provider date limits,
  exception sanitization, staging cancellation, operator-only idempotency inputs, and refusal of
  placeholder training.

## Known inherited caveats

- The API scanner still reports inherited unversioned legacy/UI routes and three parser false
  positives; the new dataset contract is under `/api/v1/datasets` and legacy ingest returns 410.
- The inherited style-token vocabulary is not understood by the static contrast checker. Contrast
  is explicitly not certified in `docs/ui-profile.md`.

## Binding integration and training boundary

Do not integrate this branch or begin training yet. Independent Dalton recheck of modeling revision
`8f29564` halted because exported `compute_feature_values` accepted reverse-chronology bars. The
modeling owner repaired that boundary at `88a7ac9`; a fresh final-2 Dalton recheck of that exact
revision is active and must close both prior reproductions plus all 28 skipped Red Team items. The
old 51-trial campaign is invalid for feature schema v2.

After both independent certifications, integrate the disjoint branches, rerun the full suite in
normal and reverse test-file order, and only then launch a fresh schema-v2 model campaign.
