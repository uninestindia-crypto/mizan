# Active work: real governed journey API wiring

STATUS: ACTIVE_FINAL_RECHECK_PENDING
OWNER: Codex — server/API implementation owner by founder direction
TOOL: Codex
STARTED_UTC: 2026-08-24T10:30:00Z
STARTING_REVISION: `ac47d7cc03e4aa485e2c92d7022d33de3809a1f2`
WORKTREE_OR_BRANCH: `D:\quant_system_workspaces\worktrees\feature-real-journey-api-ac47d7c-20260824-102717` on branch `codex/real-journey-api`

## Objective

Replace journey endpoints and dashboard states that fabricated manifests, training metrics, holdout
passes, shadow activity, and paper fills with real governed evidence/operation adapters or typed,
truthful unavailability. Preserve PointInTimeBar acquisition, immutable evidence, supervised
operations, idempotency, Decimal money, zero broker writes, and fail-closed behavior.

## Founder direction and concurrency boundary

The founder directed this agent to complete all non-training parts without crossing the separate
model-training agent. The concurrent feature-window owner repaired the evaluator at `8f29564`, then
repaired the independent reverse-chronology finding at `88a7ac9`. A fresh final-2 Dalton recheck of
that exact revision is active. This branch remains based on `ac47d7c`; it has not merged, rebased
onto, edited, or staged any modeling/execution path or concurrent record.

## Owned paths

- `src/quant_system/server/app.py`
- `src/quant_system/server/data_sync.py` (new)
- `src/quant_system/server/dataset_schemas.py` (new)
- `src/quant_system/server/governed_journeys.py` (new)
- `src/quant_system/server/operation_journal.py` (new; durable idempotency/recovery receipts)
- `src/quant_system/server/schemas.py` only if required; unchanged at handoff
- `src/quant_system/server/security.py` (bounded trusted request correlation IDs)
- `src/quant_system/server/static/app.js`
- `src/quant_system/server/static/index.html` (remove CSP-blocked external chart dependency)
- `src/quant_system/server/static/styles.css`
- `src/quant_system/server/supervisor.py`
- `src/quant_system/server/ui/constants.py`
- `src/quant_system/server/ui/journeys.py`
- `src/quant_system/server/ui/templates.py` (self-hosted/CSP-safe dashboard shell)
- `docs/ui-profile.md` (new)
- `tests/test_server_governed_journeys.py` (new)
- `tests/test_server_governed_completion.py` (new completion-audit regressions)
- `tests/test_server_api.py` only if required; unchanged at handoff
- `tests/test_server_supervisor.py` only if required; unchanged at handoff
- `tests/test_ui_journeys.py`
- `agent_context/decisions/20260824-real-journey-api-contract.md` (new)
- `agent_context/handoffs/20260824-real-journey-api-recheck.md` (new)
- this active/completed record

## Non-goals

- Train, select, promote, or certify a model; change features, labels, folds, costs, thresholds,
  holdouts, or promotion policy.
- Edit `src/quant_system/modeling/**`, `src/quant_system/execution/**`, training scripts, campaign
  evidence, or another agent's records/artifacts.
- Add live-money routing. Dataset acquisition is Upstox read-only; shadow/paper broker writes remain
  zero.
- Self-certify. Independent recheck and post-B2 integration are separate gates.

## Plan

1. DONE — isolate this worktree and freeze the additive versioned resource/error contract.
2. DONE — replace fabricated API successes with a PointInTimeBar evidence adapter or stable refusal.
3. DONE — bind idempotency keys to canonical operation intent and supervise real data acquisition.
4. DONE — replace prefilled dashboard financial/model/runtime claims with truthful states.
5. DONE — harden identity, cancellation, validation serialization, responsive UI, and output escaping.
6. DONE — push the exact owned commits and hand off independent recheck.
7. DONE — close completion-audit gaps in the same owned server/API paths and commit the repairs.
8. DONE — obtain and reconcile independent verdicts on `e329e84` and `222b693`.
9. IN PROGRESS — push the combined verifier-blocker repair and obtain one final exact-revision
   clean-state verdict.

## Decision rationale

Returning a typed refusal is more correct than claiming an operation happened when it did not.
Datasets are the one journey with a complete adapter in this branch: POST dispatches a real
Upstox HistoricalDailyRequest, the worker receives PointInTimeBar records, verifies provider/request
identity, and publishes immutable EvidenceStore evidence. Feature, training, holdout, shadow, and
paper endpoints do not have persisted server adapters here, so they fail closed and their controls
are disabled. This preserves the seam with the concurrent feature/model owner.

## Commands and outcomes

- Required startup/claim/worktree discovery: PASS; disjoint branch and paths established first.
- Failing-first public regressions: 9 expected failures before implementation.
- Dataset API: real verified list, deterministic cursor pages, strict query/body schemas, operator
  evidence root only, bounded idempotency keys, symbol/instrument binding, 202 operation resource.
- Worker adapter: provider identity binding, cancellation precondition before publication, typed
  provider/evidence failures, no path/token/provider body disclosure.
- Mutation check: inverted idempotency fingerprint comparison; two focused tests failed for the
  intended reason, then passed after restoration.
- Focused server/UI suite: 107 passed.
- Full suite normal order: 883 passed; one third-party Starlette/httpx deprecation warning.
- Full suite reverse file order: 883 passed; same warning.
- Ruff repository: PASS.
- Mypy `src`: PASS, 124 source files.
- Node syntax: PASS.
- Secure-by-default scanner on changed executable paths: clean.
- Detect-secrets on changed executable paths: no findings.
- Code-craft on the three new server modules: clean. Existing app/supervisor/app.js monolith findings
  remain inherited; new dashboard loaders and schemas were split to avoid adding those violations.
- API-craft: new `/api/v1/datasets` routes are versioned; scanner reports inherited unversioned UI/
  legacy routes plus three source-parser false positives. Legacy ingest is now 410 with successor
  headers; broader route migration is reserved in the decision record.
- Apple-grade executable UI scan: app.js clean. The inherited styles token vocabulary is not
  checker-compatible and contrast is explicitly not certified. Real browser inspection passed at
  1280x720 and 390x844 in light/dark: no page overflow, no console errors, readable contained mobile
  tabs, and 44px actions.
- OpenAPI generation: GET/POST `/api/v1/datasets` present; POST request references
  `DatasetCreateRequest`; global documented error responses included.
- Repository agent-claim audit: PASS.
- Repository disk-layout audit: PASS.
- Implementation commit: `4905b5b7168677eb8115e267b8b8d225a2cc7e6c`.
- Handoff commit: `3a5938161f05d543cf44a7546887c6ff5d3d1628`.
- Remote branch `origin/codex/real-journey-api`: pushed and verified.
- Final post-push agent-claim and disk-layout audits: PASS.
- Completion-audit failing-first evidence: seven focused regressions failed for the intended
  boundary defects before repair, then passed after repair.
- Completion revision focused server/UI suite: 115 passed; one third-party Starlette/httpx
  deprecation warning.
- Completion revision full suite normal order: 891 passed in 53.27s; same warning.
- Completion revision full suite reverse test-file order: 891 passed in 55.57s; same warning.
- Completion revision Ruff, mypy over 124 source files, changed-file format check, Node syntax,
  OpenAPI generation (43 paths), Git whitespace, changed-path security scan, and changed-path
  secret scan: PASS.
- Completion revision browser inspection at 1280x720 and 390x844 in light/dark: no page overflow,
  no console errors, and feature/training/holdout/shadow/paper actions remained disabled with
  truthful unavailable-state explanations.
- Completion revision repository agent-claim and disk-layout audits: PASS.
- Completion implementation commit: `1e953f53d7d5e2ce920452845c6ea69c47decd75`.
- Completion handoff head: `222b69322ff8ec782d055ebcd951bde42621ed03`; pushed and
  independently confirmed at `origin/codex/real-journey-api`.
- Clean-state verifier Godel (`01a033b1-515b-7aa3-92fe-c1c7044d7e7f`) completed exact remote
  revision `222b693`; it owned only its unique record/report/verification clone and made no product
  edit.
- Planck's independent `e329e84` verdict was BLOCKED: restart replay created a second dataset
  operation, oversized/unsafe `X-Request-ID` values were reflected, a forged cursor was accepted,
  the external chart script violated CSP, two controls were below 44px, and four files failed the
  formatter. The cursor/domain/formatter findings were already closed by `1e953f5` plus the current
  formatting repair.
- Godel's independent `222b693` public-boundary matrix passed 12/12, with 115 focused and 891 normal/
  reverse tests, browser, OpenAPI, lint, typing, security, secret, Git, claim, and layout evidence
  green. Its sole BLOCKED item was `tests/test_ui_journeys.py` formatting; that exact file is now
  formatted.
- Additional failing-first regressions reproduced durable restart replay, unsafe request-ID
  reflection, external chart loading/undersized targets, and cancellation losing a worker success;
  all five are now green.
- Durable dataset idempotency receipts are atomically claimed below the operator evidence root,
  contain no raw idempotency key, bind the canonical request fingerprint, persist terminal state,
  reject tampering with typed `503 OPERATION_JOURNAL_UNAVAILABLE`, and prevent duplicate workers
  across supervisor restart.
- Completion-blocker focused server/UI suite: 127 passed; one third-party Starlette/httpx warning.
- Completion-blocker full suite normal order: 903 passed in 54.83s; same warning.
- Completion-blocker full suite reverse test-file order: 903 passed in 52.93s; same warning.
- Full Ruff lint and `ruff format --check .`: PASS, 355 files formatted. Mypy `src`: PASS, 125
  source files. Node syntax, OpenAPI (43 paths), changed-path security/secrets, and Git whitespace:
  PASS.
- Final browser repair inspection: only self-hosted `app.js` loads; native canvas equity rendering
  works after a real backtest; 1280x720 and 390x844 light/dark have no page overflow or console
  errors; measured theme, refresh, ingestion, backtest, and export targets are at least 44px.
- Completion-blocker implementation commit: `261473eeb679ee93b36750d9dc83b9deecd4971c`.

## Files changed

- `agent_context/decisions/20260824-real-journey-api-contract.md`
- `docs/ui-profile.md`
- `src/quant_system/server/app.py`
- `src/quant_system/server/data_sync.py`
- `src/quant_system/server/dataset_schemas.py`
- `src/quant_system/server/governed_journeys.py`
- `src/quant_system/server/static/app.js`
- `src/quant_system/server/static/styles.css`
- `src/quant_system/server/supervisor.py`
- `src/quant_system/server/ui/constants.py`
- `src/quant_system/server/ui/journeys.py`
- `tests/test_server_governed_journeys.py`
- `tests/test_server_governed_completion.py`
- `tests/test_ui_journeys.py`
- this record

## Blockers and conflicts

- Training cannot start from this branch. Feature schema v2 changes arithmetic compatibility and
  invalidates the old 51-trial campaign. The reverse-chronology blocker found at `8f29564` was
  repaired at `88a7ac9`, but the fresh final-2 independent recheck is still active.
- The final-2 clone must close both prior reproductions and complete the 28 Red Team items skipped
  after halt-on-first-finding before integration or training.
- This branch must be integrated only after that record's binding next action is satisfied.
- Independent recheck cannot be performed by this implementation agent.
- A distinct clean-state verifier is active against exact server revision `e329e84`; it owns only a
  unique record/report/clone and may not edit product code.
- The completion audit's server-only gaps are repaired in `1e953f5`: placeholder training is
  refused, dataset cursors bind a verified total sort key, HTTP validation enforces the provider
  range, provider failures are sanitized, evidence staging observes cancellation, operator-only
  runtime configuration is excluded from idempotency intent, and catalog reads validate domain
  identity and `PointInTimeBar` record bindings.
- Both independent BLOCKED reports are fully reconciled in `261473e`; the remaining server gate is
  a new clean-state verifier at the new exact pushed revision, not another implementation change.

## Stop point

The final known independent blockers are repaired and committed at `261473e`; local normal/reverse,
static, security, OpenAPI, repository, and real-browser evidence is green.

## Next safe action

Commit the updated handoff, push the new exact head, and dispatch a fresh clean-state verifier that
must rerun both prior reproductions plus Godel's matrix and all gates. If it passes, record the
immutable verdict and hand off integration. Separately, do not touch the model/training agent's
paths, campaign, or runtime artifacts.
