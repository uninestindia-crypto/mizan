# Mutation proof — Slice 2 immutable evidence

DATE: 2026-08-20  
STATUS: PASS

## Mutations

Two independent integrity guards in `EvidenceStore` were deliberately disabled together:

1. the `COMMITTED` marker-to-manifest-hash comparison;
2. the active-reference target-hash-to-opened-manifest comparison.

The temporary mutation was never committed and both guards were restored with `apply_patch` immediately after the red run.

## Red run

```text
uv run pytest -q tests/test_evidence_store.py -k "commit_marker_hash_tamper or active_reference_cannot_redirect"

collected 37 items / 35 deselected / 2 selected
tests\test_evidence_store.py FF

FAILED tests/test_evidence_store.py::test_commit_marker_hash_tamper_blocks_open
E   Failed: DID NOT RAISE EvidenceIntegrityError

FAILED tests/test_evidence_store.py::test_active_reference_cannot_redirect_to_wrong_manifest_hash
E   Failed: DID NOT RAISE EvidenceIntegrityError

2 failed, 35 deselected
EXIT=1
```

Both targeted tests failed for the intended reason: each weakened guard allowed an invalid object to open.

## Restored run

```text
uv run pytest -q tests/test_evidence_store.py -k "commit_marker_hash_tamper or active_reference_cannot_redirect"

collected 37 items / 35 deselected / 2 selected
tests\test_evidence_store.py ..
2 passed, 35 deselected
EXIT=0
```

## Adjudication

The tests are causally sensitive to both publication-completeness and active-pointer identity. Mutation status: killed.
