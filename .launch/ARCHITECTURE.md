# ARCHITECTURE — QuantOS Governed Research Platform

STATUS: G2 accepted 2026-08-20  
TIER: T2  
SCOPE: Local Windows research, governed model training, shadow, and paper simulation. Live-money broker execution is outside this architecture.

## Decision summary

QuantOS remains a single-user, loopback-only desktop application. FastAPI is the application boundary; one internal application layer owns all governed operations; immutable, content-addressed JSON/JSONL evidence is stored under the user's local application-data directory. The browser, API, exports, and replay all render the same domain result rather than recomputing it.

The first governed model family is the existing ridge classifier, rebuilt behind a training contract with point-in-time features, an executable next-open-to-next-open net-return target, purged walk-forward validation, an isolated final holdout, immutable trial accounting, and an evidence-driven promotion state machine.

No component may submit, modify, or cancel a broker order. Upstox adapters are read-only and expose only historical-data and quote capabilities.

## System context

```text
Local user
  |
  v
Browser on exact loopback origin
  |
  v
FastAPI /api/v1 contract + security/error middleware
  |
  v
Governed operation coordinator (one active mutation)
  |
  v
Supervised spawned worker (bounded progress/cancellation)
  |------------------|--------------------|-------------------|
  v                  v                    v                   v
Data evidence    Model governance     Financial engine   Shadow/paper replay
  |                  |                    |                   |
  |                  +----------+---------+-------------------+
  |                             v
  |                   Immutable evidence store
  v
Read-only provider adapters: Upstox historical data and quotes

Optional local AI CLI -> advisory text with explicit provenance only
```

The operating-system account is the trust boundary. QuantOS protects against hostile browser origins, malformed provider/user input, accidental concurrent mutations, path traversal, and secret disclosure. It does not claim to protect evidence from an attacker who already controls the user's Windows account.

## Component boundaries and ownership

| Component | Owns | Must not own |
|---|---|---|
| `contracts` | Stable enums, identifiers, timestamps, money, typed errors, canonical serialization | Provider calls, filesystem writes |
| `evidence` | Hashing, atomic publication, manifests, append-only events, replay verification, retention | Model or trading decisions |
| `market_data` | Provider adapters, instrument mapping, availability time, validation, quality findings, dataset manifests | Silent repair or source substitution |
| `modeling` | Feature/label construction, partitions, folds, preprocessing, deterministic fit/predict, model manifests | Promotion authority |
| `validation` | Baselines, metrics, stress tests, trial multiplicity, frozen gates, promotion evaluation | Editing prior trials or holdout evidence |
| `finance` | Effective-dated NSE rules, execution timing, risk decisions, Decimal ledger, reconciliation | Floating-point money or timeless fee constants |
| `sessions` | Recorded-data shadow and quote-driven paper state machines | Broker order routes or automatic source fallback |
| `application` | Operation lifecycle, concurrency lease, worker supervision, cancellation, orchestration | Domain calculations |
| `server` | `/api/v1`, strict validation, request IDs, idempotency, security headers, DTO translation | Alternate business rules |
| `desktop` | Same-origin rendering and operation polling | Calculation or promotion logic |

Dependencies point inward: `server`, `desktop`, and provider adapters depend on application/domain contracts; domain code never imports FastAPI, browser code, provider SDKs, or filesystem paths.

## Non-negotiable invariants

1. Every result names exactly one execution mode: `RESEARCH_BACKTEST`, `SHADOW_READ_ONLY`, or `PAPER_SIMULATION`.
2. Broker order-create, modify, and cancel traffic is structurally unavailable and is asserted as zero in release tests.
3. A value used for a decision has `available_at <= information_cutoff_at`; violation fails closed and identifies the record.
4. A dataset, configuration, rule, risk limit, trial, artifact, prediction, decision, fill, or report referenced by completed evidence is immutable.
5. Every persisted content hash covers the schema/version and every consumed value in canonical order.
6. Money and fees use `Decimal` internally and integer paise or decimal strings at boundaries; completed ledgers reconcile exactly to the paise.
7. A bar-close decision can first fill at the next eligible open. A quote decision can first fill from a later valid quote, buying at ask and selling at bid before adverse slippage.
8. Promotion is derived from frozen evidence. No API, UI, configuration, or administrator action directly sets a higher lifecycle state.
9. Trial multiplicity includes successful, failed, cancelled, abandoned, and manually reviewed attempts.
10. One governed mutating operation is active at a time. A second request cannot share its model, risk, ledger, or evidence state.
11. Provider failure never becomes synthetic or cached success without a new, affirmative request whose source label changes.
12. Publishing a new artifact or promotion never destroys its predecessor; rollback appends evidence and changes only an atomic active reference.

## Stable scalar and serialization contract

- IDs are opaque lowercase strings with prefixes: `op_`, `dset_`, `trial_`, `cand_`, `model_`, `fold_`, `session_`, `bundle_`, `risk_`, `rule_`, `promo_`, followed by UUIDv7-compatible text. Consumers never parse IDs.
- Timestamps are RFC 3339 UTC strings ending in `Z`; exchange-local dates are separate ISO `YYYY-MM-DD` fields.
- `DecimalString` is the regex `^-?(0|[1-9][0-9]*)(\.[0-9]+)?$`, contains no exponent, `NaN`, or infinity, and is normalized before hashing.
- `MoneyV1` is `{ "amount_paise": integer, "currency": "INR" }`.
- API field names are `snake_case`. Requests reject unknown fields. Readers tolerate unknown response fields and enum values by mapping the latter to an explicit `UNKNOWN` presentation.
- Canonical JSON is UTF-8, NFC-normalized, sorted by object key, compact separators, no floats, and a trailing newline. Ordered records are JSONL sorted by their declared total key. SHA-256 is written as lowercase hex.
- A hash is over `{schema_id, schema_version, canonical_payload}`; changing schema, order, source, availability, adjustment, or transformation changes the hash.

## Evidence store and filesystem contract

Production data root: `%LOCALAPPDATA%\QuantOS\evidence\v1`. Tests must inject a temporary root. An environment override is accepted only in development/test mode after resolving the path and proving containment within an explicitly allowed root.

```text
v1/
  blobs/sha256/<first-two>/<sha256>.jsonl.gz
  datasets/<dataset_id>/manifest.json
  trials/<trial_id>/manifest.json
  models/<model_id>/manifest.json
  operations/<operation_id>/{manifest.json,events.jsonl}
  sessions/<session_id>/{manifest.json,events.jsonl}
  bundles/<bundle_id>/manifest.json
  promotions/<candidate_id>/events.jsonl
  active/<purpose>.json
  locks/governed-operation.lock
  .staging/<uuid>/...
```

Publication protocol:

1. Acquire the in-process lock and the cross-process governed-operation lease.
2. Write new files only under a same-volume `.staging/<uuid>` directory.
3. Flush and `fsync` every file; recompute and compare every declared hash.
4. Write the manifest last, flush it, then publish by same-volume `os.replace` into a previously absent immutable directory.
5. Append the operation outcome and atomically replace an active reference only after its target is readable and hash-valid.
6. On startup, quarantine incomplete staging directories; never infer success from their presence. An orphaned `running` operation becomes `interrupted` through a new event.

Published evidence files are opened read-only by application code. A duplicate ID with different content is `EVIDENCE_CONFLICT`; a duplicate hash with identical content is a safe deduplication. The cross-process lease records PID, process-start identity, operation ID, and heartbeat. Stale-lease recovery requires proving that the recorded Windows process identity no longer exists; otherwise startup remains `DEGRADED` and refuses governed mutation.

Record blobs are split into deterministic gzip chunks of at most 16 MiB uncompressed canonical JSONL, written with `mtime=0`. Manifests record both the canonical uncompressed content hash and stored-file hash for every ordered chunk. No database, pickle, joblib, arbitrary YAML deserialization, or native Python object serialization is allowed in evidence. Model coefficients and preprocessing arrays are canonical JSON arrays of decimal strings with explicit shapes.

## Exact evidence schemas

All fields listed below are required unless marked optional. Each object starts with `schema_id` and integer `schema_version`; v1 readers reject an unsupported major version.

### `DatasetManifestV1`

```text
dataset_id: DatasetId
created_at: Timestamp
status: ACCEPTED | PARTIAL | STALE | REJECTED
source: {kind, provider, endpoint_id, acquired_at, request_id?}
scope: {venue: NSE, asset_class: CASH_EQUITY | NIFTY_OPTION, interval, currency: INR}
requested_range: {start_date, end_date, symbols[]}
received_range: {start_date?, end_date?, symbols[]}
instruments[]: {symbol, provider_instrument_id, isin?, mapping_history[]}
timestamp_contract: {event_field, provider_field?, ingested_field, available_field, timezone}
calendar: {calendar_id, version, content_hash}
adjustment: {status: RAW | ADJUSTED, method, version}
corporate_action_authority: AuthorityRefV1?
historical_universe_authority: AuthorityRefV1?
transformations[]: {name, version, parameters_hash, input_hash, output_hash}
record_schema: {name, version, primary_key[], total_order[]}
records: {row_count, encoding: CANONICAL_JSONL, blob_hash, canonical_hash}
quality_findings[]: QualityFindingV1
limits: {symbol_count, completed_session_count, byte_count}
```

`AuthorityRefV1` is `{authority_id, source_url, publication_date, effective_from, effective_to?, version, content_hash}`. `QualityFindingV1` is `{code, severity: INFO|WARNING|BLOCKING, count, record_keys[], disposition: NONE|REJECTED|REPAIRED, repair_rule?, repair_hash?}` with `record_keys` capped in the API and complete keys retained in evidence.

`BarRecordV1` is `{provider_instrument_id, symbol, event_at, provider_at?, ingested_at, available_at, open, high, low, close, volume, open_interest?, source_record_id?}`. Prices are `DecimalString`; volume/open interest are non-negative integers. Its total order is `(provider_instrument_id,event_at,ingested_at,source_record_id)`.

`OptionQuoteRecordV1` adds `{underlying, option_type, strike, expiry_date, multiplier, lot_size, tick_size, bid, ask, bid_quantity, ask_quantity, last?}` and uses the same four timestamps/provenance fields.

### Training rows and folds

`FeatureRowV1` is `{candidate_id,dataset_id,dataset_hash,provider_instrument_id,symbol,decision_at,information_cutoff_at,universe_authority_hash,feature_schema_id,feature_schema_version,features,preprocessing_input_hash}`. `features` is a closed map defined by the versioned feature schema and contains finite decimal strings only.

`LabelRowV1` is `{candidate_id,symbol,decision_at,order_at,entry_at,exit_at,entry_price,exit_price,gross_return,component_costs,net_return,target,cost_rule_ids,execution_contract_version}`. `target` is `UP` only when `net_return > 0`; otherwise `DOWN`. Component costs are a closed map of `MoneyV1` values.

`FoldSpecV1` is `{fold_id,ordinal,train_start,train_end,validation_start,validation_end,purge_start,purge_end,embargo_sessions,label_horizon_sessions,train_row_count,validation_row_count,train_class_balance,validation_class_balance,train_hash,validation_hash}`. The final holdout uses a separate `FinalHoldoutLockV1` containing candidate/config/dataset/trial-count/gate-policy hashes, minimum 252 completed sessions, minimum 20 percent chronology, locked_at, and a single-use evaluation state.

### Trials, runs, and artifacts

`OperationManifestV1` is `{operation_id,kind,mode,status,request_id,idempotency_key_hash,created_at,started_at?,heartbeat_at?,ended_at?,progress_basis_points?,stage?,source_revision,environment_lock_hash,architecture,config_hash,input_refs[],output_refs[],warning_codes[],error?,cancellation_requested_at?}`. Status is `pending|running|cancelling|succeeded|failed|cancelled|interrupted`.

`TrialRecordV1` is `{trial_id,candidate_id,state,created_at,ended_at?,model_family,model_contract_version,dataset_id,dataset_hash,feature_schema_id,feature_schema_version,label_contract_version,universe_policy_hash,parameters,parameter_hash,threshold_policy,seeds,fold_spec_hashes[],source_revision,environment_lock_hash,architecture,outcome_hash?,failure_codes[],multiplicity_ordinal}`. A record is persisted before fitting, so every attempt is counted.

`TrainingPolicyArtifactV1` is `{policy_id,model_family,model_contract_version,window_policy,refit_trigger,feature_schema_id,preprocessing_policy,label_contract_version,parameter_hash,seed_policy,created_at,policy_hash}`.

`ModelArtifactManifestV1` is `{model_id,candidate_id,created_at,source_revision,environment_lock_hash,architecture,dataset_id,dataset_hash,dataset_range,universe_policy_hash,feature_schema_id,feature_schema_version,preprocessing_state_hash,label_contract_version,execution_contract_version,parameters,seeds,fold_spec_hashes,trial_count,fitted_state:{encoding,shape,blob_hash},prediction_hashes,metrics,limitations[],verdict,training_policy_id?,rollback_model_id?,artifact_hash}`.

For continuous refits, `DecisionFitEvidenceV1` is required per decision: `{policy_id,decision_at,training_window,training_rows_hash,preprocessing_state_hash,fitted_state_hash,prediction_input_hash,prediction_value,prediction_kind,prediction_hash}`.

### Validation, promotion, sessions, and replay

`ValidationReportV1` is `{candidate_id,trial_count,fold_reports[],baseline_reports[],holdout_report?,predictive_metrics,trading_metrics,stress_results[],multiplicity,deflated_sharpe_ratio,cost_sensitivity,delay_sensitivity,reconciliation,report_hash}`. A fold report includes its spec, predictions, decisions, risk outcomes, fills, component costs, and all AC-41 metrics.

`PromotionRecordV1` is `{promotion_id,candidate_id,from_state,to_state,requested_at,evaluated_at,gate_policy_hash,evidence_refs[],gate_results[],verdict,failed_gate_codes[],rollback_model_id?,actor: LOCAL_USER,record_hash}`. Allowed forward edges are `REJECT -> RESEARCH_ONLY -> SHADOW -> PAPER_PILOT -> PAPER`; evaluation may remain or move backward. `REJECT -> RESEARCH_ONLY` means the blocking research defect was fixed in a new candidate, never mutation of rejected evidence. Each `gate_result` records `{gate_id,operator,threshold,observed,unit,passed,evidence_hash}`.

`DecisionRecordV1` is `{decision_id,session_id,model_id,decision_fit_evidence_hash?,dataset_or_quote_hash,decision_at,information_cutoff_at,score,score_kind,side,quantity,risk_limit_id,risk_outcome_id,status,reason_code?,record_hash}`.

`ProposalRecordV1` and `FillRecordV1` add order eligibility, first later quote hash, bid/ask quantities, remaining quantity, adverse slippage, every component cost, ledger entry IDs, and reconciliation hash. Their natural idempotency keys are `(session_id,proposal_id)` and `(session_id,proposal_id,quote_event_id,fill_sequence)`.

`EvidenceBundleManifestV1` is `{bundle_id,created_at,operation_id,mode,input_manifest_hashes[],model_manifest_hash?,config_hash,rule_version_hashes[],risk_limit_id,prediction_hashes[],decision_hashes[],risk_outcome_hashes[],fill_hashes[],ledger_hash,equity_curve_hash,metrics_hash,report_hash,reconciliation_hash,warning_codes[],capability_labels[],files[],bundle_hash}`. Each `files` entry is `{relative_path,byte_count,sha256}`; paths are generated, relative, and containment-checked.

`ReplayReportV1` records the bundle and current environment/architecture, every expected/observed stage hash, first mismatch, status, and elapsed time. Replay never replaces recorded evidence.

## Governed model and promotion flow

1. Accept a complete point-in-time dataset manifest; unresolved corporate-action or historical-universe authority restricts it to labeled research.
2. Persist a trial record before any candidate work.
3. Build the next-open-to-following-open net-cost label and time-valid features. The v1 feature family is the six existing technical features only; no new model family is added.
4. Reserve and seal the final holdout before selection. Walk-forward folds purge overlapping labels and embargo at least the maximum label horizon.
5. Fit preprocessing only on each fold's training side. Use fixed seeds and single-threaded numerical execution for governed hashing. Exact reproducibility is claimed only on the same verified architecture and dependency lock.
6. Evaluate ridge candidates and the four required baselines under the same timing, universe, cost, and risk contracts. Record every attempted trial.
7. Freeze candidate, dataset, trial count, and numeric gates. Unlock final holdout once, calculate all mandatory evidence, and append the verdict.
8. A probability label is permitted only if Brier score beats training-side climatology and ECE is at most `0.05`; otherwise the value is an `UNCALIBRATED_SCORE` everywhere.
9. Promotion evaluation advances by at most one state and is wholly derived from evidence. `PAPER_PILOT` authorizes only the bounded campaign; `PAPER` requires that campaign's own minimum sessions/records, frozen gates, reconciliation, monitoring, and rollback exercise.

## HTTP API v1

The release API is `/api/v1`. Existing unversioned `/api/*` routes remain as research-only compatibility adapters, converge immediately on the same application layer, and emit dated `Deprecation`, `Sunset`, and migration `Link` headers. They remain for at least two releases and six months after the first public deprecation unless evidence proves there are no external consumers.

| Method and path | Contract |
|---|---|
| `GET /api/v1/capabilities` | Mode/source matrix, truthful notice, limits, optional dependency status; `Cache-Control: no-store` |
| `GET /api/v1/diagnostics` | Mandatory/optional checks and `HEALTHY|DEGRADED|UNHEALTHY` |
| `GET /api/v1/operations/{id}` | Poll operation, progress, result/error; no side effect |
| `PUT /api/v1/operations/{id}/cancellation` | Idempotent cancellation request; `202` while stopping |
| `POST /api/v1/data-acquisitions` | Start bounded acquisition/validation; `202` + operation `Location` |
| `GET /api/v1/datasets/{id}` | Dataset manifest and quality summary |
| `POST /api/v1/training-runs` | Start governed trial/training; `202` |
| `POST /api/v1/validation-runs` | Start walk-forward/final evaluation; `202` |
| `GET /api/v1/models/{id}` | Immutable model card/manifest |
| `POST /api/v1/promotion-evaluations` | Evaluate one legal next state from immutable evidence; never accepts a verdict |
| `POST /api/v1/backtest-runs` | Start evidence-producing backtest; `202` |
| `POST /api/v1/option-simulations` | Start reference/evidence-producing option simulation; `202` |
| `POST /api/v1/risk-limit-versions` | Create immutable limits version; `201` + `Location` |
| `POST /api/v1/shadow-sessions` | Start eligible read-only session; `202` |
| `POST /api/v1/paper-sessions` | Start eligible bounded paper session; `202` |
| `POST /api/v1/evidence-bundles` | Export an existing completed operation; `202` |
| `POST /api/v1/replays` | Verify a bundle; `202` |

All unsafe `POST` requests require `Idempotency-Key`, `Content-Type: application/json`, and the ephemeral `X-QuantOS-Session` header. The first request reserves the key and request hash atomically with the operation manifest. Same key and body returns the original response; changed body is `422 IDEMPOTENCY_KEY_REUSED`; in-flight replay is `409 OPERATION_IN_PROGRESS`. Keys remain for at least 24 hours. Idempotent `PUT` cancellation uses the operation ID as its natural key.

CPU-bound or failure-prone governed work runs in one `multiprocessing` child created with Windows `spawn`, never in the server event loop. The coordinator sends a validated immutable operation specification, receives progress/heartbeat events at least every five seconds, and commits only verified outputs from that operation's staging directory. A missing heartbeat for 15 seconds fails the operation; cancellation is cooperative for five seconds before the child is terminated. Termination cannot expose partial evidence because only the coordinator publishes verified staging output. Provider credentials are passed only in memory to the read-only adapter and never enter the operation specification or evidence.

Every response includes `X-Request-ID`; creates include `Location`; reads include explicit `Cache-Control`; immutable resources include an `ETag`. Updating the active risk-limit reference requires `If-Match`; stale writers receive `412 PRECONDITION_FAILED`. Bodies, strings, arrays, nesting, dates, symbols, numeric ranges, five-symbol/ten-year limits, and 100 MiB bundle size are enforced before work begins.

Collection responses are `{items,next_cursor,has_more}` with default 50 and maximum 200. Cursors encode the stable `(created_at,id)` key; clients treat them as opaque.

### Error contract

```json
{
  "error": {
    "code": "DATASET_PARTIAL",
    "message": "The provider returned an incomplete requested range.",
    "request_id": "req_...",
    "operation_id": "op_...",
    "fields": {"symbols": "1 of 5 instruments is incomplete"},
    "retryable": false,
    "recovery_action": "Inspect the dataset quality report or request a research-only run."
  }
}
```

Stable code families are:

- Request: `MALFORMED_REQUEST`, `VALIDATION_FAILED`, `UNKNOWN_FIELD`, `LIMIT_EXCEEDED`, `UNSUPPORTED_VALUE`, `IDEMPOTENCY_KEY_REQUIRED`, `IDEMPOTENCY_KEY_REUSED`.
- State: `OPERATION_IN_PROGRESS`, `CONCURRENT_LIMIT`, `PRECONDITION_FAILED`, `INVALID_TRANSITION`, `HOLDOUT_LOCKED`, `HOLDOUT_ALREADY_EVALUATED`.
- Data: `DATASET_EMPTY`, `DATASET_PARTIAL`, `DATASET_STALE`, `DATA_QUALITY_BLOCKED`, `POINT_IN_TIME_VIOLATION`, `AUTHORITY_UNRESOLVED`, `SCHEMA_DRIFT`, `HASH_MISMATCH`.
- Provider: `PROVIDER_UNAUTHORIZED`, `PROVIDER_RATE_LIMITED`, `PROVIDER_TIMEOUT`, `PROVIDER_UNAVAILABLE`, `PROVIDER_MALFORMED`, `PROVIDER_RANGE_UNAVAILABLE`.
- Model: `INSUFFICIENT_EVIDENCE`, `INVALID_TARGET`, `NONFINITE_FEATURE`, `CALIBRATION_FAILED`, `REPRODUCIBILITY_FAILED`, `PROMOTION_GATES_FAILED`.
- Finance/session: `RISK_REJECTED`, `QUOTE_STALE`, `QUOTE_INVALID`, `LIQUIDITY_UNAVAILABLE`, `LOT_TICK_INVALID`, `RECONCILIATION_FAILED`, `SESSION_OFFLINE`.
- Evidence/internal: `EVIDENCE_NOT_FOUND`, `EVIDENCE_CONFLICT`, `STORAGE_UNAVAILABLE`, `CANCELLED`, `INTERRUPTED`, `INTERNAL_ERROR`.

Malformed JSON is `400`; semantic validation is `422`; missing resource `404`; conflict `409`; stale ETag `412`; provider rate limit `429` with `Retry-After`; provider transient failures map to `502/503/504`; internal errors are generic `500` with no path, token, stack, or provider body.

## Dependency failure behavior

| Dependency/failure | Detection | Behavior | Retry/fallback |
|---|---|---|---|
| Upstox credential absent/expired | Startup check or `401/403` | `UNAUTHORIZED`; halt acquisition/session; preserve last accepted evidence | No retry; no fallback |
| Upstox `429` | Status and bounded body | `RATE_LIMITED`, expose safe retry time | Bounded jittered retry for idempotent GET only; respect `Retry-After` |
| Upstox timeout/reset/5xx | Connect/read deadline | Typed timeout/unavailable; partial result rejected | At most 3 GET attempts within published total deadline |
| HTML, malformed JSON, schema drift, empty/partial set | Strict boundary parser/completeness check | Reject or mark `PARTIAL`; never substitute | New affirmative source request only |
| Quote stale/crossed/out of order/zero quantity | Quote validator | No decision/fill; append typed event | Wait for a later valid quote; never repair |
| Calendar, universe, corporate action, or NSE rule absent | Effective-date lookup | Research-only or block promotion/session as specified | Operator supplies a new authority version |
| Evidence disk full/permission/hash/atomic rename failure | Preflight, write, read-back | Fail current operation; prior evidence/active pointer unchanged | Retry only as a new operation after recovery |
| Process crash/restart | Lease plus operation/event scan | Mark orphan interrupted; verify store; never auto-resume a live session | Deterministic replay or explicit new session |
| Optional AI CLI absent/timeout/malformed | Capability check and subprocess deadline | Use no advisor, or separately requested deterministic heuristic with exact provenance | Never blocks quantitative gates |
| Cancellation | Cooperative stage boundary | Stop before next commit; publish cancelled trial/operation evidence | Repeated cancellation is idempotent |
| Clock regression | UTC wall clock vs monotonic ordering | Halt active session and record `CLOCK_INVALID` | Operator corrects clock and starts a new session |

Provider requests use fixed official hosts, percent-encoded instrument IDs, separate connect/read timeouts, TLS verification, capped response bodies, and no redirects to unapproved hosts.

## Security design

- Bind only to `127.0.0.1` or `::1`; startup rejects wildcard/non-loopback hosts. Validate `Host` against the actual loopback host and bound port.
- CORS permits only the exact current loopback origin, required methods, and required headers; no wildcard and no credentials. Unsafe API calls also require the per-process, high-entropy `X-QuantOS-Session` token delivered only in the same-origin bootstrap document and held in memory, never `localStorage` or logs.
- Set `Content-Security-Policy` with `default-src 'self'`, nonce/hash-based scripts, `object-src 'none'`, `base-uri 'self'`, and `frame-ancestors 'none'`; also `nosniff`, `Referrer-Policy: no-referrer`, `X-Frame-Options: DENY`, and a restrictive `Permissions-Policy`. HSTS is not used for plain loopback HTTP and is documented as not applicable.
- Browser rendering uses `textContent` and explicit DOM construction for variable content. No provider, file, model, or error value reaches `innerHTML`.
- Requests are strict typed objects with bounded size/depth; dynamic symbols/strategies/sorts come from allowlists. Generated opaque IDs, not user path fragments, address evidence; every resolved path is containment-checked.
- Secrets come from environment variables in local development, with `.env` ignored and a value-free `.env.example`. They never enter URLs, process arguments, evidence, logs, errors, exports, screenshots, or client code. Authorization headers are redacted at the logging boundary.
- No `shell=True`, string-built command, untrusted pickle, unsafe YAML, user-controlled URL, or disabled TLS verification. Optional CLI calls use an argument array, fixed executable allowlist, fixed working directory, input via stdin, output cap, and timeout.
- Rate limits apply to the bootstrap/session-token endpoint and expensive operations; the single-operation lease is the primary compute limiter. Security and audit logs record request/operation IDs, not full bodies.
- A non-secret `QUANTOS_GOVERNED_V1_ENABLED` feature flag can disable creation of new governed-v1 operations during rollback without changing or hiding existing evidence. Release builds default it on; disabling it is visible in capabilities and diagnostics.
- The threat model explicitly excludes a hostile administrator or process already running as the same Windows account; that actor can read local evidence and process memory. Network exposure, multi-user use, or cloud hosting requires a new architecture and authentication.

## Observability and audit

Structured JSONL logs use UTC timestamps and stable events. Every event carries `event`, `level`, `request_id?`, `operation_id?`, `session_id?`, `model_id?`, `dataset_id?`, `mode?`, `stage`, `duration_ms?`, and stable outcome/error codes. A redaction filter removes configured secret keys and authorization-shaped values before formatting.

Required event families: startup checks; request accepted/rejected; lease acquire/release/recovery; provider attempt/outcome; dataset validation; trial created/stage/outcome; holdout lock/use; gate evaluation; promotion/demotion/rollback; prediction/decision/risk/fill; reconciliation; stale/offline/unauthorized transition; evidence publish/verify; replay mismatch; cancellation; shutdown.

Local operational counters and gauges are exposed in diagnostics, not a remote telemetry service: operation duration/failures; provider latency/status; data age/quality counts; trial/fold counts; feature missingness/distribution drift; score drift; matured calibration; turnover/exposure; risk rejection rate; modeled-versus-realized costs; equity/drawdown; reconciliation failures; stale quotes; rollback/halt state. Monitoring thresholds are frozen into the promoted model card. A breach appends an alert, halts new decisions when required, updates the desktop within five seconds, and names the recovery/rollback action.

Logs rotate by size with a bounded local retention policy. Evidence is retained until the user performs a separately designed, explicit deletion; deletion is not part of this release. Logs contain IDs and outcomes, while evidence contains governed content.

## Rollback and recovery rehearsal

Rollback is a new append-only `PromotionRecordV1` from the active state/model to its declared rollback model plus an atomic replacement of `active/shadow-model.json` or `active/paper-model.json`. It never modifies model, dataset, trial, validation, or session evidence.

Rehearsal procedure:

1. From a clean temporary evidence root, publish accepted dataset `D`, candidate/model `A`, validation `VA`, and active reference `A`.
2. Publish candidate/model `B` with rollback target `A`, promote it, and confirm a new session resolves `B` while an existing completed session still references `A`.
3. Inject a mandatory monitor breach or corrupted `B` read. Confirm new decisions halt before financial mutation.
4. Append the demotion/rollback record and atomically point active state to `A`; restart the application.
5. Confirm diagnostics name `A` as active, `B` remains readable and non-active, and no in-flight proposal was duplicated.
6. Replay the known `A` evidence bundle and require every expected hash and paise reconciliation to match.
7. Capture commands, timestamps, duration, event IDs, and result. Release target: detection within 5 seconds of the evaluated event and safe rollback completed within 60 seconds in the test fixture.

If the active reference is corrupt, startup scans only hash-valid promotion history and offers the last valid rollback target; it does not silently choose it. If no valid target exists, the capability remains halted and research-only functions stay available.

## Windows packaging and architecture

- Python and all direct/transitive dependencies are locked with hashes; build from a clean source revision and exact lock.
- PyInstaller output embeds version, source revision, lock hash, build architecture, build time, and artifact SHA-256 in a machine-readable build manifest.
- Runtime evidence and secrets are outside the installation directory. Upgrade/uninstall cannot erase user evidence by default.
- x64 and ARM64 are separate build targets and support claims. Each needs its own native clean-install, startup, seven-journey, uninstall/reinstall, and rollback record.
- The application obtains an available loopback port, opens only that origin, prevents duplicate governed processes through the lease, and shuts down cleanly. Windows Defender/SmartScreen and code-signing status are reported truthfully; an unsigned build is never described as trusted/signed.

## ADR index

- `ADR-001`: immutable content-addressed filesystem evidence.
- `ADR-002`: one governed domain pipeline shared by API, desktop, export, and replay.
- `ADR-003`: asynchronous resource API with loopback session defense.
- `ADR-004`: one governed ridge family and evidence-derived promotion lifecycle.

## PRD traceability and G2 checklist

| Concern | Acceptance criteria | Architecture owner |
|---|---|---|
| Capability truth/startup/platform | AC-1–8, AC-60, AC-77–78 | contracts, server, desktop, packaging |
| Point-in-time data/provenance | AC-9–22 | market_data, evidence |
| Effective-dated finance | AC-23–28, AC-53–58 | finance, evidence |
| Governed training | AC-29–40 | modeling, evidence |
| Validation/promotion | AC-41–51 | validation |
| Shadow/paper | AC-61–72 | sessions, finance, evidence |
| Export/replay/security/limits | AC-72–78 | evidence, application, server |

G2 is ready when the ADRs and slice plan are accepted and every schema, trust boundary, failure path, observability signal, and rollback step is explicit. Current open authorities are runtime evidence inputs, not architecture ambiguities: missing effective-dated corporate-action or historical-universe authority fails closed as required by the PRD.
