# Decision: real governed journey API contract

STATUS: ACCEPTED FOR IMPLEMENTATION
DATE_UTC: 2026-08-24
OWNER: Codex — server/API implementation

## Context

The seven desktop journeys are presented as product capabilities, but five handlers currently
return literal sample data: invented dataset hashes, positive ridge metrics, a passing holdout,
running shadow activity, and filled paper orders. The responses are labelled `SYNTHETIC`, which is
necessary but insufficient: the handler still claims an operation occurred when none did.

The domain stack now has real immutable evidence and governed operation entry points. A concurrent
agent owns the feature-window/model-training change, so this server change must consume committed
evidence without editing model or execution code.

## Decision

### 1. Authoritative versioned resources

The target migration surface uses resource nouns under `/api/v1`. This change implements the
dataset collection and operation polling end to end:

- `GET /api/v1/datasets` — cursor-paginated verified point-in-time acquisition manifests.
- `POST /api/v1/datasets` — accept one real Upstox V3 acquisition as a supervised operation;
  return `202` and `Location: /api/v1/operations/{id}`.

The following resource names are reserved for later adapters and are not exposed by this change:

- `GET /api/v1/model-trials` and `GET /api/v1/models` — verified persisted evidence only.
- `POST /api/v1/model-trials` — supervised governed training after the canonical feature contract
  lands; no synthetic fallback.
- `POST /api/v1/holdout-evaluations` — supervised single-use promotion pipeline against persisted
  model/data evidence.
- `GET /api/v1/shadow-sessions/current` — actual configured runtime/audit state, or `404` when none.
- `POST /api/v1/shadow-sessions` — supervised start; promotion evidence is mandatory.
- `GET /api/v1/paper-campaigns/current` — actual in-memory/persisted campaign state, or `404`.
- `POST /api/v1/paper-orders` — simulated order intent against a real active campaign and quote;
  never a broker write.

Collections use an envelope with `items`, `next_cursor`, and `has_more`; default limit 25, maximum
100. Cursors encode the total sort key and are opaque to clients.

### 2. Writes are operations and are idempotent

Every unsafe write requires `Idempotency-Key`. First use creates one operation. Reuse with the same
operation type and canonical request returns the same operation. Reuse with a different operation
type or body returns `422 IDEMPOTENCY_KEY_REUSED`. The key is bound before spawning the worker.

Long work returns `202`, a real operation resource, and a `Location` header. Provider and governed
failures become terminal operation errors with stable codes; no provider body, credential, path,
or stack trace reaches the response.

### 3. Runtime configuration is operator-owned

`QUANTOS_EVIDENCE_ROOT` selects the runtime evidence store. It is never accepted from an HTTP
request. When absent, evidence-backed endpoints return `503 EVIDENCE_ROOT_NOT_CONFIGURED` with
`Retry-After`; they do not create a default directory or silently use fixtures.

Provider credentials remain environment/.env configuration loaded at process startup. Tokens are
never accepted in request bodies, command-line arguments, operation records, logs, or errors.

### 4. Legacy journey routes are compatibility adapters

Existing unversioned `/api/...` routes remain during migration so the bundled UI does not break in
one change. They delegate to the authoritative service and carry `Deprecation`, `Sunset`, and `Link`
headers once the UI has moved. They may preserve their old successful response shape, but they may
not preserve fabricated behavior. Missing configuration/evidence/state is therefore an error,
never a sample success.

### 5. Money and model claims stay exact

Internal amounts remain `Decimal`; new API money fields are decimal strings plus currency. Existing
float fields are legacy-only and are not copied into the versioned contract. Model verdicts,
metrics, attempt counts, hashes, and feature contracts are read from verified evidence and never
recomputed or defaulted by the server.

### 6. Training-agent seam

This branch does not edit model features, fitting, campaign selection, promotion policy, or training
scripts. Model operation dispatch is enabled only after the feature-window change is committed and
its schema/version identity is available. Until then, the endpoint returns the exact typed
compatibility refusal rather than launching against old semantics.

## Error contract

All immediate failures retain the existing `ErrorEnvelope` and add stable codes for this surface:

- `EVIDENCE_ROOT_NOT_CONFIGURED` (`503`, retryable after operator configuration)
- `EVIDENCE_ROOT_INVALID` (`503`, retryable after operator correction)
- `EVIDENCE_STORE_UNAVAILABLE` (`503`, retryable)
- `EVIDENCE_NOT_FOUND` (`404`)
- `EVIDENCE_INTEGRITY_INVALID` (`409`)
- `IDEMPOTENCY_KEY_REQUIRED` (`422`)
- `IDEMPOTENCY_KEY_INVALID` (`422`)
- `IDEMPOTENCY_KEY_REUSED` (`422`)
- `PROVIDER_UNAVAILABLE` (`503`, with `Retry-After` when known)
- `PROVIDER_UNAUTHORIZED` (`503`, non-retryable until configuration changes)
- `PROVIDER_IDENTITY_MISMATCH` (terminal operation failure; non-retryable)
- `MODEL_CONTRACT_INCOMPATIBLE` (`409`)
- `PROMOTION_EVIDENCE_REQUIRED` (`409`)
- `SHADOW_SESSION_NOT_CONFIGURED` (`404`)
- `PAPER_CAMPAIGN_NOT_CONFIGURED` (`404`)

## Rejected alternatives

1. **Keep literals but label them synthetic.** Rejected: provenance disclosure does not make an
   operation that never happened a truthful operation result.
2. **Import private CLI `_run` functions into FastAPI.** Rejected: delivery would depend on
   argparse/script internals, and model-training ownership would collide across agents.
3. **Accept an evidence path or provider token in the request.** Rejected: path traversal and
   credential disclosure risks, plus clients could select evidence outside the governed runtime.
4. **Return empty successful objects for missing state.** Rejected: missing configuration is not an
   empty dataset/model/session and must remain distinguishable.
5. **Promote a research model to exercise shadow/paper.** Rejected: the server cannot alter model
   governance verdicts.

## Consequences

- The old UI tests that asserted literal positive results must be replaced with behavior tests over
  seeded verified evidence and typed unavailable states.
- Real model training remains parallel work, but its outputs become directly consumable once
  committed.
- Release certification must recheck the OpenAPI schema, idempotency conflict behavior, provider
  failure mapping, evidence tamper refusal, zero broker writes, and legacy deprecation behavior.
