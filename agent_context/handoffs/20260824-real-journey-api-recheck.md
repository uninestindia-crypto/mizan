# Handoff: governed journey API independent recheck

STATUS: READY_FOR_INDEPENDENT_RECHECK
OWNER: Codex server/API implementation owner
BRANCH: `codex/real-journey-api`
IMPLEMENTATION_COMMIT: `4905b5b7168677eb8115e267b8b8d225a2cc7e6c`
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

## Existing evidence

- Focused server/UI contract suite: 107 passed.
- Full suite normal test-file order: 883 passed; one third-party Starlette/httpx warning.
- Full suite reverse test-file order: 883 passed; same warning.
- Ruff, mypy over 124 source files, Node syntax, changed-path security scan, changed-path secret scan,
  OpenAPI generation, Git whitespace check, claim audit, and disk-layout audit: PASS.
- Mutation probe inverted the idempotency fingerprint comparison; the two intended tests failed,
  then passed after restoration.
- Real browser inspection at 1280x720 and 390x844, light/dark: no page overflow or console errors;
  mobile tabs remained readable and actions were 44px.

## Known inherited caveats

- The API scanner still reports inherited unversioned legacy/UI routes and three parser false
  positives; the new dataset contract is under `/api/v1/datasets` and legacy ingest returns 410.
- The inherited style-token vocabulary is not understood by the static contrast checker. Contrast
  is explicitly not certified in `docs/ui-profile.md`.

## Binding integration and training boundary

Do not integrate this branch into the modeling repair or begin training yet. Independent Dalton
recheck of modeling revision `8f29564` halted because exported `compute_feature_values` accepts the
same 21 bars in reverse chronology and silently changes all six feature values. That owner must add
fail-closed chronological validation, rerun the focused probes, and complete the 28 skipped Red Team
items in a fresh independent clone. The old 51-trial campaign is invalid for feature schema v2.

After both independent certifications, integrate the disjoint branches, rerun the full suite in
normal and reverse test-file order, and only then launch a fresh schema-v2 model campaign.
