# Active work: real governed journey API wiring

STATUS: ACTIVE
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
model-training agent. The concurrent feature-window owner has repair `8f29564` on `main`. Its final
independent Dalton recheck halted on a new finding: exported `compute_feature_values` accepts
reverse-chronology bars and produces six different values instead of failing closed. This branch
remains based on `ac47d7c`; it has not merged, rebased onto, edited, or staged any modeling/execution
path or concurrent record.

## Owned paths

- `src/quant_system/server/app.py`
- `src/quant_system/server/data_sync.py` (new)
- `src/quant_system/server/dataset_schemas.py` (new)
- `src/quant_system/server/governed_journeys.py` (new)
- `src/quant_system/server/schemas.py` only if required; unchanged at handoff
- `src/quant_system/server/static/app.js`
- `src/quant_system/server/static/styles.css`
- `src/quant_system/server/supervisor.py`
- `src/quant_system/server/ui/constants.py`
- `src/quant_system/server/ui/journeys.py`
- `docs/ui-profile.md` (new)
- `tests/test_server_governed_journeys.py` (new)
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
6. IN PROGRESS — push the exact owned commits and hand off independent recheck.

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
- `tests/test_ui_journeys.py`
- this record

## Blockers and conflicts

- Training cannot start from this branch. Feature schema v2 at `8f29564` changes arithmetic
  compatibility, invalidates the old 51-trial campaign, and failed its final independent recheck
  because the public feature kernel accepts reverse-chronology bars.
- The modeling owner must repair chronological-order validation and a fresh independent clone must
  complete the reverse-order probes plus the 28 Red Team items skipped after halt-on-first-finding.
- This branch must be integrated only after that record's binding next action is satisfied.
- Independent recheck cannot be performed by this implementation agent.

## Stop point

Implementation, verification, repository audits, and the implementation commit are complete. Push
and the independent-recheck handoff remain.

## Next safe action

Commit this record and the handoff, push only owned paths, then hand the branch to an independent
reviewer. Separately, repair and independently certify the reverse-order model blocker. Only after
that certification may this disjoint server branch be integrated and the full suite rerun before a
new schema-v2 model training campaign.
