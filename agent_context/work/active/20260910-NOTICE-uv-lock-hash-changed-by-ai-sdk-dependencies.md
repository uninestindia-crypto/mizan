# NOTICE: `uv.lock` hash changed — release manifest and SBOM evidence invalidated

STATUS_AT_CREATION: NOTICE (additive; no other record is edited; no owned path is touched)
FROM: Claude Code (Opus 5), author of `20260910-claude-bedrock-dual-model-audit.md`
AUTHORITY: Explicit founder instruction — "add anthropic and openai to pyproject.toml"
CREATED_UTC: 2026-09-10T00:00:00Z
REVISION: `c6532fbd`

Filed under PROTOCOL §8.4, which requires a uniquely named notice when a change invalidates a
number another record pins as evidence. It names what changed and what that breaks. It does not
edit anyone's record and does not repair anyone's artifact.

## What changed

`anthropic>=1.4.0` and `openai>=3.11.0` were added to `[project.optional-dependencies] dev` in
`pyproject.toml`, and `uv lock` was run so the lockfile stays consistent with it.

Re-locking was not optional. Every verification and Red Team clone in this project runs
`uv sync --frozen --extra dev`, and `--frozen` fails outright when the lock does not match
`pyproject.toml`. Leaving the lock stale would have broken every adjudication clone rather than
just the hashes below.

| | Before | After |
|---|---|---|
| Packages in `uv.lock` | 48 | **57** |
| `uv.lock` SHA-256 (raw and newline-normalized are identical) | `9c40ebf470a8c7021b849f72acdb23347e49a63053ecbd59e3832337d3a27498` | **`37f56de0fbf55208c8c0b340cb749e55b7f5a0e5ae278598e5f311b258b749b2`** |

Nine packages entered the lock: `anthropic`, `openai`, and their transitive dependencies
`docstring-parser`, `httpcore2`, `httpx2`, `httpx2-jsfetch`, `jiter`, `sniffio`, `truststore`.

They are in the **dev extra**, not `[project.dependencies]`. The shipped trading platform does not
carry them, and no trading, training, or execution path imports either SDK. They exist for
`scripts/run_mizan_dual_opinion_bedrock.py`.

## What this invalidates

### 1. `20260824-1110Z-codex-release-manifest-integrity.md` — ACTIVE, in a worktree

That record pins, as its own completion evidence:

> Normalized `uv.lock`: `9c40ebf470a8c7021b849f72acdb23347e49a63053ecbd59e3832337d3a27498`.

**That hash no longer describes the install root.** The new value is
`37f56de0fbf55208c8c0b340cb749e55b7f5a0e5ae278598e5f311b258b749b2`.

The record's own conclusion is unaffected: it established that the manifest must bind to normalized
lock *bytes* rather than to arbitrary input, and that mechanism is untouched and still correct. Only
the specific value it captured has moved. Its worktree
(`D:\quant_system_workspaces\worktrees\feature-release-manifest-integrity-b084d72-20260824-111030`,
branch `codex/release-manifest-integrity`) is untouched — nothing here entered it, and nothing was
removed, pruned, or merged.

### 2. Built release artifacts now fail their own verification

Measured, not inferred, by calling `quant_system.release.sbom.verify_sbom` against the current lock:

```
dist/quantos/sbom.json:   ok=False :: Lock hash mismatch:
    recorded 9c40ebf4...a27498 != actual 37f56de0...b749b2
dist/quantos-sbom.json:   ok=False :: Lock hash mismatch:
    recorded 9c40ebf4...a27498 != actual 37f56de0...b749b2
```

`dist/quantos/release-manifest.json` and `dist/quantos/release.json` carry the same superseded hash.

`CURRENT.md` records program-level Major #3 as **CLOSED** on the strength of that artifact
("Artifact rebuilt at `dab7f7b3`; SBOM matches `uv.lock`"). On this evidence the SBOM no longer
matches `uv.lock`. **Major #3 should be read as reopened until the artifact is rebuilt.** Rebuilding
it is the whole repair; the provenance mechanism itself is sound and is not in question.

### 3. Documents quoting the superseded hash

- `.launch/SLICE-12-EVIDENCE.md` — formal release evidence
- `agent_context/handoffs/20260822-claude-real-data-training-runner-handoff.md`

Both are historical records of what was true at their revision. They are not wrong about their own
moment and were not edited. A reader comparing either against the tree today will find a mismatch,
and this notice is the explanation.

## What is *not* affected

- **Tests.** `pytest tests/ -q` → **1339 passed** at the post-change revision. No test regressed.
- **Static gates.** `ruff check src/ scripts/` clean. `mypy` unchanged: the same 15 pre-existing
  errors in `research_xs_monthly/`, none introduced here.
- **Lock consistency.** `uv lock --check` → resolved 57 packages, no drift.
- **Runtime behaviour.** Neither SDK is imported by `src/quant_system/alpha/__init__.py` or by any
  trading, training, or execution module. `alpha/__init__.py` was deliberately left alone so the
  package still imports for anyone without the SDKs installed.

## Suggested repair, for whoever owns the release path

1. Rebuild the provenance artifact so `sbom.json`, `release-manifest.json`, and `release.json` bind
   to `37f56de0fbf55208c8c0b340cb749e55b7f5a0e5ae278598e5f311b258b749b2` and 57 packages.
2. Re-verify with `verify_sbom`, and record the new hash wherever the old one was cited as evidence.
3. Decide whether `CURRENT.md` Major #3 is restated as closed at the new artifact.

None of that is done here. This author does not own `.launch/`, `dist/`, or `CURRENT.md`, and an
artifact rebuild is a release action, not a dependency change.

## Note on version pinning

Both SDKs are declared with bare `>=`, matching every other dependency in the file. Worth knowing:
`anthropic` 1.x is itself the far side of a major-version break (it moved to `httpx2`), so an
unbounded `>=1.4.0` will accept a future 2.x that may break again. No cap was added, because
capping only these two would depart from the file's established style — `pydantic`, which has its
own famous major break, is likewise uncapped. Recorded so the choice is visible rather than
accidental.
