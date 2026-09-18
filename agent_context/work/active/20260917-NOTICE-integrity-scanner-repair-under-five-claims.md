# NOTICE: `_scan_resource_type` repaired in `evidence/store.py`, which carries five active claims

STATUS: NOTICE (additive; no other record is edited, and no other function in the file is touched)  
FILED_BY: Claude Code (Opus 5), `work/completed/20260917-1257Z-claude-integrity-scanner-non-directory-entry.md`  
FILED_UTC: 2026-09-17T13:30:00Z  
REVISION_EDITED: committed as `16d9e3cc` on branch `claude/evidence-scanner-catalog-entry`, cut from `main` at `9b12dd8c`. Not pushed, not merged.  
AUTHORITY: explicit founder instruction, 2026-09-17 ("fix S1"), after a line-by-line audit of
`src/quant_system/evidence/store.py` in that session.

## Addressed to the owners of `src/quant_system/evidence/store.py`

- `20260820-codex-slice4-ridge-training.md` (ACTIVE)
- `20260822-claude-h2-l2-repair.md`
- `20260822-redteam-money-paths.md`
- `20260822-NOTICE-h2-l2-repair-affects-money-paths-redteam.md`
- `20260911-NOTICE-governed-datasets-exceed-store-limits.md`

PROTOCOL §3 forbids editing your records, so this is the channel (§8.4). **This is an observation and
a disclosure, not an accusation** — nothing any of you wrote was wrong, and none of the behaviour any
of you relies on has changed.

## The exact change

One branch in `EvidenceStore._scan_resource_type`, plus an explanatory comment. Nothing else in the
file is touched.

```python
 for resource_directory in sorted(resource_root.iterdir(), key=lambda path: path.name):
     if not resource_directory.is_dir():
-        continue
+        invalid.append(resource_directory.name)
+        continue
```

## Why

`list_manifests` (`store.py:160-163`) and `list_verified` (`:179-182`) both treat a non-directory
entry in a catalog directory as a fatal `EvidenceIntegrityError`. `_scan_resource_type` skipped it.
So `scan_integrity()` — the function run to *confirm* a store is healthy — was more permissive than
the read path it certifies, and reported a clean store that `list_verified()` could not read.

Demonstrated before the repair, on a fresh store with one stray file in `models/`:

```
scan_integrity() : 0 valid, 0 invalid, 0 orphans   => "clean"
list_verified()  : EvidenceIntegrityError: evidence catalog contains a non-directory entry: stray.txt
```

After: `0 valid, 1 invalid ('stray.txt')`, and `list_verified` is unchanged.

## What this does NOT change — read this if you own a pinned number

- **`list_verified`, `list_manifests`, `open_verified`, `commit`, `_publish`, `set_active`,
  `resolve_active`, `recover` and the lease are all untouched.** The reader was already correct; only
  the scanner moved, and only toward it.
- **No committed store's scan result changes.** Measured across `data/evidence/` **before** editing:
  **103 catalog directories, 0 stray non-directory entries.** There is nothing in the repository for
  the new branch to find.
- **Re-measured after the repair**, because the figure is pinned as evidence in
  `.launch/reports/ADJUDICATION-TRAINING-PATH-20260911.md` ("9 valid, 0 invalid, 0 orphan blobs" for
  `mizan-v1`):

  ```
  mizan-v1 scan_integrity() -> valid=9  invalid=0  orphan=0
  ```

  **Unchanged. No pinned number is invalidated**, so §8.4 raises no precondition against merging.

- `20260911-NOTICE-governed-datasets-exceed-store-limits.md` concerns store *limits* on DATASET
  publication. This change touches neither limits nor publication.

## Gate at the working tree

| Gate | Result |
|---|---|
| New regression `tests/test_evidence_integrity_scan_catalog_entries.py` | **13 failed, 1 passed** before the repair; **14 passed** after |
| `test_evidence_store.py`, `test_evidence_publish_atomicity.py`, `test_committed_evidence_integrity.py`, `test_modeling_evidence_tamper.py` | **56 passed** |
| `ruff check .` | PASS |
| `ruff format --check .` | PASS, 691 files |
| `mypy src launcher.py scripts` | PASS, 210 source files |
| `check-code.mjs` / `check-tests.mjs` | totals unchanged at 1,082 / 87; the changed and added files contribute **0** |
| `audit-agent-claims.ps1` / `audit-disk-layout.ps1` | PASS / PASS |
| Full suite, forward order | **1,601 passed in 824.59s**, exit 0 (baseline 1,587 at `6ca45e10`; +14 is exactly the new regression file) |
| Full suite, reverse file order | **NOT RUN.** CI runs it as a separate job; do not cite this work as reverse-order verified |

## If you disagree

The repair is one branch and is trivially revertible. Say so in your own record or in a notice and I
will not defend it past your objection — `store.py` is yours, and this edit exists only because the
founder asked for it directly.
