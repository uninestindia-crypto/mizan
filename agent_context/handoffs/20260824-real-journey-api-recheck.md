# Handoff: governed journey API independent recheck

STATUS: INDEPENDENTLY_CERTIFIED_PENDING_INTEGRATION
OWNER: Codex server/API implementation owner
BRANCH: `codex/real-journey-api`
IMPLEMENTATION_COMMIT: `261473eeb679ee93b36750d9dc83b9deecd4971c`
CERTIFIED_HEAD: `474795f3ad6287bdec3b7deaa677a54b537f28c7`
CERTIFIED_TREE: `1f6ca227bfdcd9dded692d7334f817da965d5f9e`
VERDICT_REPORT: `agent_context/reports/20260824-final-adjudication-real-journey-api-474795f.md`
REPORT_SHA256: `c0b71220145ff36e911f3e47c0afc069024fb988d034126c231718206eb9b85f`
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
12. Complete a dataset operation, restart/clear the supervisor's process-local state, and replay the
    same idempotency key. It must return the original terminal operation ID without another worker;
    a conflicting payload must still fail, and a tampered receipt must return typed `503`.
13. Send oversized and markup-shaped `X-Request-ID` headers. They must be replaced by a bounded
    generated correlation ID and never reflected; a valid bounded ID must still round-trip.
14. Verify only self-hosted scripts load, the native canvas chart renders after a real backtest,
    desktop/mobile remain overflow-free after chart rendering, interactive targets are at least
    44px, and the console remains clean.

## Existing evidence

- Focused server/UI contract suite: 127 passed.
- Full suite normal test-file order: 903 passed in 54.83s; one third-party Starlette/httpx warning.
- Full suite reverse test-file order: 903 passed in 52.93s; same warning.
- Ruff, mypy over 125 source files, Node syntax, changed-path security scan, changed-path secret scan,
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
- Five independent-verifier blocker regressions were also observed failing before repair: durable
  restart replay, unsafe request-ID reflection, external chart/CSP loading, undersized controls,
  and cancellation overwriting a worker success. They now pass.
- Full `ruff format --check .` is green across 355 files. Ruff lint, mypy over 125 source files,
  Node syntax, OpenAPI generation, changed-path security/secrets, Git whitespace, claim audit, and
  disk-layout audit pass.
- Real-browser post-repair evidence proves self-hosted native chart rendering, measured 44px
  controls, light/dark at 1280x720 and 390x844, no page overflow after chart rendering, and no
  console errors.

## Independent final certification

- Fresh verifier Dewey executed exact detached revision `474795f3ad6287bdec3b7deaa677a54b537f28c7`
  from a canonical clean clone and preserved 20 raw evidence artifacts.
- Final adjudicator Ptolemy independently hashed and reviewed every requested artifact. All 16
  claims were `PROVEN`; strict verdict: `PASS`.
- Exact clean-state results: 127 focused tests; 903 normal and 903 reverse tests; 355-file format
  gate; Mypy over 125 source files; 43-path OpenAPI contract; all lint, security, secret, Git,
  claim, layout, historical-regression, governed-boundary, and zero-broker-write checks passed.
- Real-browser evidence ran one local backtest with six trades and six fill rows. Desktop/mobile
  light+dark rendered the self-hosted native canvas with no horizontal overflow, external assets,
  undersized controls, or console/security errors.

## Prior independent reports to reproduce

- `e329e84` report: `.launch/reports/VERIFIER-REAL-JOURNEY-API-E329E84.md` — BLOCKED on restart
  idempotency, request-ID reflection, forged cursor, CSP/target sizes, and formatting.
- `222b693` report: `agent_context/reports/20260824-godel2-verifier-real-journey-api-222b693.md` —
  12/12 public probes and all substantive gates passed; BLOCKED only on UI-test formatting.
- The final verifier must rerun both reports' concrete reproductions on the new exact head and may
  not reuse their outcomes as current evidence.

## Known inherited caveats

- The API scanner still reports inherited unversioned legacy/UI routes and three parser false
  positives; the new dataset contract is under `/api/v1/datasets` and legacy ingest returns 410.
- The inherited style-token vocabulary is not understood by the static contrast checker. Contrast
  is explicitly not certified in `docs/ui-profile.md`.

## Binding integration and training boundary

This server/API/UI branch is certified and may now be integrated by a separate integrator. Preserve
all disjoint modeling/training commits and runtime evidence, then rerun the combined full suite in
normal and reverse file order plus static, OpenAPI, security, claim/layout, and real-browser gates.

The separate ten-year NIFTY 50 schema-v2 campaign has already completed 50/50 trials at source
revision `5a7185a`, but every result is capped at `RESEARCH_ONLY`. Best final-count DSR probability
was `0.217695263874` against the `0.95` promotion gate. The static current-member universe is
survivorship-biased and pre-2020 costs use explicit research proxies. Therefore no model promotion,
final-holdout opening, shadow/paper/live session, or broker write is authorized. A new governed
research hypothesis and fresh evidence are required before another promotion attempt.
