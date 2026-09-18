# NOTICE: `reject_symlink` now refuses reparse points; it was letting `recover()` write outside the root

STATUS: NOTICE (additive; no other record is edited, and no other function is touched)  
FILED_BY: Claude Code (Opus 5), `work/completed/20260918-1137Z-claude-reject-reparse-points.md`  
FILED_UTC: 2026-09-18T12:05:00Z  
BRANCH: `claude/evidence-reject-reparse-points`, cut from `main` at `b6b1c93d`  
WORKTREE_OR_BRANCH: `D:\quant_system`, branch `claude/evidence-reject-reparse-points` (shared
checkout). This notice carries the claim, because the work record it was filed from is COMPLETED and
lives in `work/completed/`, which `scripts/audit-agent-claims.ps1` does not read — the same trap that
made the audit exit 1 during the S1 repair earlier today. The branch is mine; per PROTOCOL §8.3
nobody else should remove it.  
AUTHORITY: explicit founder instruction, 2026-09-18 ("now fix S2")  
SEVERITY: **P1 — a demonstrated containment escape**, raised from the "observation, not a
vulnerability" the original audit recorded. That downgrade was my error; see §2.

## 1. Addressed to the owners of `src/quant_system/evidence/store.py`

- `20260820-codex-slice4-ridge-training.md` (ACTIVE)
- `20260822-claude-h2-l2-repair.md`
- `20260822-redteam-money-paths.md`
- `20260822-NOTICE-h2-l2-repair-affects-money-paths-redteam.md`
- `20260911-NOTICE-governed-datasets-exceed-store-limits.md`

The edit itself is in `src/quant_system/evidence/io.py`, which **no active record names in its
Owned paths** — `20260826-claude-lease-wait-test-determinism.md` mentions `src/quant_system/evidence/**`
but only in its *Non-goals*, explicitly disclaiming it. You are addressed because the escape is in
`store.py`'s `recover()`, which your claims cover, and because the guard is the one your file relies
on for containment.

PROTOCOL §3 forbids editing your records, so this is the channel (§8.4). **Observation and
disclosure, not accusation.**

## 2. A correction I am obliged to make first

The audit that raised this finding called it *"an observation, not a vulnerability"* and said *"I
could not construct an escape."* The reasoning was that `_contained_path` resolves and re-checks
containment behind every `reject_symlink` call.

**That was wrong.** `recover()` (`store.py:186-201`) builds `staging_root` and `quarantine`
**directly** from `self.root`, never through `_contained_path`, so the guard is its only containment
check. Reproduced on a scratch store whose `quarantine/staging` was a junction to a sibling
directory:

```
recover() -> quarantined_staging_count = 1
inside  root  quarantine/: ['staging']
OUTSIDE the root         : ['stagedwork-aba62d97b8ca49c8a9d1914da8b14050']
content escaped intact   : 'staged evidence'
```

The store reported a successful quarantine while writing staged evidence outside its configured
root, bytes intact.

## 3. Why the guard missed it

`Path.is_symlink()` returns **False** for a Windows junction. Measured on this machine:

| | junction (`mklink /J`) | ordinary directory |
|---|---|---|
| `is_symlink()` | `False` | `False` |
| `st_file_attributes` | `0x410` | REPARSE bit clear |
| `FILE_ATTRIBUTE_REPARSE_POINT` (`0x400`) | **set** | clear |
| `st_reparse_tag` | `0xa0000003` (`IO_REPARSE_TAG_MOUNT_POINT`) | — |

And the asymmetry that makes it matter on the stated build target: creating a **symlink** on this
machine raised `OSError` for want of `SeCreateSymbolicLinkPrivilege`; creating the **junction**
needed no privilege at all. The redirection an unprivileged user can actually make on Windows is the
one the guard could not see.

## 4. The exact change

`src/quant_system/evidence/io.py`, `reject_symlink` only, plus `import stat`:

```python
     if path.is_symlink():
         raise EvidenceIntegrityError(f"symbolic links are forbidden in evidence paths: {path.name}")
+    try:
+        attributes = getattr(os.lstat(path), "st_file_attributes", 0)
+    except OSError:
+        return
+    if attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
+        raise EvidenceIntegrityError(f"reparse points are forbidden in evidence paths: {path.name}")
```

After, the same scenario:

```
recover() -> EvidenceIntegrityError: reparse points are forbidden in evidence paths: staging
OUTSIDE the root: (empty -- nothing escaped)
staged dir still in place for inspection: True
```

## 5. What this does NOT change

- **No function other than `reject_symlink` is touched.** `recover()`, `_contained_path`,
  `list_verified`, `list_manifests`, `commit`, `_publish`, `set_active` and the lease are untouched.
  Repairing the guard closes the escape at all thirteen call sites at once.
- **A missing path is still silent.** `read_bounded` calls the guard before opening and relies on
  the *open* to report absence; `is_symlink()` returns `False` rather than raising for a missing
  path, and the new branch swallows `OSError` to match. Covered by a regression that asserts
  `read_bounded` still reports `is missing`, not a reparse error.
- **POSIX is unaffected.** `st_file_attributes` exists only on Windows `stat_result`, so the branch
  is inert there and `is_symlink()` keeps doing the whole job.
- **No committed evidence is touched or re-scanned.** This is a guard on path handling, not on
  content.

## 6. Gate

| Gate | Result |
|---|---|
| `tests/test_evidence_reparse_points.py` (new) | **2 failed, 2 passed** before the repair; **4 passed** after |
| `test_evidence_store.py`, `..._publish_atomicity`, `..._committed_evidence_integrity`, `..._integrity_scan_catalog_entries`, `..._modeling_evidence_tamper` | **70 passed** |
| `ruff check .` / `ruff format --check .` | PASS / PASS, 695 files |
| `mypy src launcher.py scripts` | PASS, 210 source files |
| `check-code.mjs` / `check-tests.mjs` | **1,082 / 87 — exact baseline**; the new file and `io.py` contribute **0** |
| `audit-agent-claims.ps1` / `audit-disk-layout.ps1` | PASS / PASS |
| Full suite, forward | **1,605 passed in 672.53s**, exit 0 (baseline 1,601) |
| Full suite, reverse file order | **NOT RUN** — do not cite this as reverse-order verified |

**CI cannot verify any of it.** The gate is red for billing — see
`20260918-NOTICE-ci-billing-failure-has-recurred.md`. Every figure above is one agent's local
measurement on one machine, which is exactly what CI exists to stop anyone relying on.

## 7. One thing deliberately left undone

**`recover()` should also route its paths through `_contained_path`.** Repairing the guard closes
the demonstrated escape, but `recover()` remains the only place in the store where a path is built
without the resolve-and-recheck that backs every other call site — so its containment still rests on
a single guard. That is a second change to a file under your claims and was not what was authorized,
so it is recorded rather than made. It is yours to take or to leave.

## 8. If you disagree

The change is one branch in one function and is trivially revertible. Say so in your own record or a
notice and I will not defend it past your objection — `store.py` is yours, and this exists only
because the founder asked for it directly.
