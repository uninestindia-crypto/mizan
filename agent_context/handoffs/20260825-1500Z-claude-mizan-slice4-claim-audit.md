# Handoff audit: editing paths claimed by `20260820-codex-slice4-ridge-training`

FILED_UTC: 2026-08-25T15:00:00Z  
FILED_BY: Claude Code — Mīzān model build  
SUBJECT_RECORD: `agent_context/work/active/20260820-codex-slice4-ridge-training.md` (STATUS: ACTIVE)  
AUTHORIZATION: founder instruction, 2026-08-25

This is an audit, not a takeover. The subject record is **not edited**. It keeps its STATUS and its
owned-path list. This file exists so its owner can see exactly what changed and object.

## Why this was necessary

The founder directed that the system have one model, named Mīzān, trained on the multi-dimensional
feature family. That family has 15 predictive features. Two constraints in claimed files make any
feature count other than six structurally impossible:

- `src/quant_system/modeling/rows.py:159` — `if tuple(self.features) != FEATURE_NAMES_V1: raise`
- `src/quant_system/modeling/ridge.py:77,98` — the L2 regularizer is sized `len(FEATURE_NAMES_V1)+1`,
  so a 24-column design matrix meets a 7×7 identity and raises a shape error

## Contact attempted

`ListAgents` returned one peer session started 11 minutes before this filing — not the owner of a
record dated 2026-08-20. No messaging channel reaches that owner. PROTOCOL §7 permits a handoff
audit where contact fails; abandonment was **not** inferred from the clean tree or the idle
timestamp, per §8.2.

## Exactly what changed in claimed paths

Every change is **additive**. No existing behaviour is removed or renamed.

| File | Change | Existing behaviour |
|---|---|---|
| `rows.py` | Added `FEATURE_SCHEMA_ID_V3`, `FEATURE_NAMES_V3` (15 names), `FEATURE_NAMES_BY_SCHEMA`, `feature_names_for()`; registered v3 in `SUPPORTED_FEATURE_SCHEMAS`; the row-level feature-name check is now schema-dependent instead of always comparing to `FEATURE_NAMES_V1` | v1 and v2 rows validate exactly as before, against the same six names |
| `ridge.py` | `RidgeFittedStateV1` carries `feature_names`, **defaulting to `FEATURE_NAMES_V1`**; the regularizer, the minimum-rows check and `_matrix` are sized from the fitted family | Six-feature arithmetic is identical, and the canonical dict is byte-identical — proven below |
| `preprocessing.py` | Standardization fits and transforms against the family the rows declare, rather than the hard-coded six | Identical for v1/v2 |
| `validation.py` | The `EQUITY_DUAL_MOMENTUM` baseline read `features["return_10"]`, which only the six-feature family has. It now selects the medium-horizon return per schema (`return_21` for v3, `return_10` otherwise) | Identical for v1/v2 |

**Two files named in the original filing were NOT changed.** `labels.py` and `features.py` were
expected to need a multi-instrument binding. They did not: pooling binds rows to a *pooled source
identity* hashed from the constituent acquisitions, which satisfies the existing invariant rather
than relaxing it. The single-instrument acquisition binding in `labels.py:133` is untouched and
still enforced on every constituent.

## Evidence that existing work is unharmed

- **941 tests pass** (full suite), Ruff clean, `ruff format --check` clean, strict Mypy clean across
  21 modeling source files.
- **All 50 published schema-v2 models rehash byte-identically** under the modified `ridge.py`:
  reconstructing `RidgeFittedStateV1` from each stored manifest reproduces its recorded
  `fitted_state_hash` and `coefficient_names` in 50 of 50 cases, 0 mismatches.

## What this does NOT invalidate

- The **50 published schema-v2 models** remain valid and auditable. Their manifests bake in
  `('quantos.ridge_technical_six', 2)`, which still resolves and still validates.
- No test count, coverage figure, or manifest hash pinned by any other active record is changed by
  these edits. PROTOCOL §8.4 was checked: no record pins a number that an additive schema
  registration moves.
- `RidgeFittedStateV1`, `ModelCardV1`, and the v1/v2 schema identifiers are **not** renamed.

## If the owner objects

Revert order is `features.py`, `labels.py`, `preprocessing.py`, `ridge.py`, `rows.py`. Each change
is independent of the others except that `ridge.py` and `preprocessing.py` assume `rows.py` exposes
the v3 names. Nothing in `modeling/` depends on the Mīzān work; deleting
`src/quant_system/modeling/pooled.py`, the two `scripts/*mizan*` files, and
`data/evidence/models/mizan-*` removes it entirely.

Filed against: `agent_context/work/active/20260825-1500Z-claude-mizan-pooled-model.md`

## Second change set: the label horizon (2026-08-26)

Same founder authorization. Measurement in
`agent_context/decisions/20260826-label-horizon-is-a-declared-parameter.md`.

| File | Change | Existing behaviour |
|---|---|---|
| `rows.py` | `label_contract_version_for(horizon)`; `LabelDatasetV1.label_horizon_sessions` field defaulting to 2 | `label_contract_version_for(2)` returns `next-open-net-return-v1` **verbatim**, so every existing label dataset hashes exactly as before |
| `labels.py` (unclaimed) | `build_label_dataset(..., horizon_sessions=...)`; exit is `ordinal + horizon_sessions` | Default 2 reproduces the original entry/exit pair exactly |
| `partitions.py` | `build_purged_fold(..., label_horizon_sessions=...)`; the "next two eligible opens" check generalises to the declared horizon | Identical at the default |
| `validation.py` | Fold horizon is checked against the label dataset's declared horizon instead of the constant | Identical at the default |
| `errors.py` | Added `LABEL_HORIZON_INVALID` | Additive enum member |

Also changed, both unclaimed: `scripts/cached_nifty50_costs.py` (`round_trip_cost_quotes` prices the
declared horizon) and `scripts/run_governed_ridge_training.py` (`_fold_from_tail` forwards it).

**The default is deliberately unchanged.** Every prior governed result was measured at horizon 2;
moving the default would make 101 published trials incomparable to anything produced afterwards.

Verification after this change set: **953 tests pass**, Ruff clean, `ruff format --check` clean,
strict Mypy clean across 21 modeling source files, `audit-agent-claims` PASS, `audit-disk-layout`
PASS.

One flaky failure was observed and is not a regression:
`tests/test_evidence_publish_atomicity.py::test_a_permanently_held_lease_still_fails_closed` budgets
0.2 seconds of wall clock for a threaded lease wait and slips under machine load. It passed 4/4 in
isolation and 953/953 on an immediate re-run.
