# Integrate codex/real-journey-api into main

TASK_ID: 20260824-claude-integrate-real-journey-api
AGENT: Claude Code (Opus 5) — acting as the separate integrator the branch record asks for
STATUS: IN_PROGRESS
STARTED_UTC: 2026-08-24
STARTING_REVISION: main at `6455970`; branch at `b124da3`; merge base `ac47d7c`
WORKTREE_OR_BRANCH: D:\quant_system on main

## Objective

Founder-directed: merge `codex/real-journey-api` into `main`.

## Binding preconditions, read before acting (PROTOCOL 8.4)

From `agent_context/work/active/20260824-codex-real-journey-api-wiring.md` on the branch, whose
`Next safe action` and `Blockers and conflicts` are binding on an integrator:

| # | Precondition | How it is satisfied |
|---|---|---|
| 1 | "A separate integrator may integrate ... with current `main`" | I did not author any code on that branch. I am that separate integrator. |
| 2 | "preserve the training agent's disjoint commits and evidence" | Verified: the branch changes **no** path under `modeling/`, `analytics/multiplicity.py`, `advisory/`, or `scripts/run_governed_*`. Disjoint by construction, not by care. |
| 3 | "must not be used to overwrite, stage, or rewrite the training agent's paths or artifacts" | Same evidence as 2. A merge commit is used; no rebase, no force, no history rewrite. |
| 4 | "rerun the combined normal/reverse, static, OpenAPI, security, claim/layout, and real-browser gates" | To be run after the merge and recorded below, including any gate I cannot run. |
| 5 | "The research-only model result must not be promoted" | Nothing here promotes a model. Recorded so the constraint travels with the merge. |

## Conflict surface, measured before merging

- Merge base: `ac47d7c`. Branch ahead 9, main ahead 22.
- Files changed on **both** sides: exactly one —
  `agent_context/work/active/20260824-codex-real-journey-api-wiring.md`.
- That file is absent at the merge base and was added independently on both sides, so it is an
  add/add conflict. **The two versions are byte-identical** (223 lines each, `diff` empty), so the
  resolution is trivial and loses nothing from either side.
- No source file conflicts.

## Why this branch matters

It carries an independent adjudication at `474795f` with verdict PASS over 16 claims, and the
repaired governed journey APIs — `feat(server): wire truthful governed journey APIs` plus two
rounds of blocker fixes. Those repairs are the mocked-endpoint layer that has been the largest open
gap on `main`: at `main` today `sharpe_ratio=1.84` and `status="FILLED"` are still hardcoded
literals, and `tests/test_server_governed_journeys.py` does not exist.

**The adjudication certifies `474795f`, not the merge result.** A merge of 9 commits into a `main`
that has moved 22 commits produces a tree no adjudicator has seen. That is precisely why
precondition 4 exists, and why the PASS must not be cited for the merged tree.

## Plan

1. Record this. (done)
2. Merge with `--no-ff`, resolving the single trivial add/add conflict.
3. Rerun the gates precondition 4 names; record every result, including gates I cannot run.
4. Do not push if any gate fails; report instead.

## Outcome

Merged with `--no-ff`. **Zero conflicts** — git resolved the single add/add automatically because
the two versions were byte-identical.

One untracked file blocked the merge: `agent_context/handoffs/20260824-real-journey-api-recheck.md`.
AGENTS.md treats untracked files as owned work, not disposable, so it was **not deleted**: it was
hashed, copied to the session scratchpad, moved aside, and the post-merge file verified against the
backup. `sha256 751ebce7…faefbe5` before and after — nothing lost.

### What the merge closes

`sharpe_ratio=1.84` and `status="FILLED"` are now **0** occurrences in `server/app.py`, and
`tests/test_server_governed_journeys.py` exists. That is the mocked-endpoint layer — the largest
open gap on `main` and the first defect identified in this session — actually closed.

### Gates required by precondition 4

| Gate | Result |
|---|---|
| Full suite, normal order | **929 passed** |
| Full suite, reverse file order (75 files) | **929 passed** |
| `ruff check .` | All checks passed! |
| `scripts/audit-agent-claims.ps1` | PASS |
| `scripts/audit-disk-layout.ps1` | PASS |
| `ruff format --check .` | **RED — 10 files** |
| `mypy src launcher.py scripts` | **RED — 3 errors in 2 files** |
| OpenAPI contract gate | **NOT RUN** — no such script exists in `scripts/`; the adjudicator ran it from its own harness |
| Real-browser gate | **NOT RUN** — requires a live server and browser harness not available to this session |

### The two red gates are not caused by this merge

Attributed file by file rather than assumed:

- Both mypy errors are in `scripts/cached_nifty50_io.py` and
  `scripts/run_cached_nifty50_ridge_campaign.py`, which are **untracked** — another agent's
  in-flight work, absent from this merge.
- All 10 format failures return `in-merge:0`. They are `modeling/**`, `strategies/**`, governed
  strategy/shadow tests and `run_governed_shadow_session.py` — other agents' concurrent edits.

Neither file appears in the 20 staged paths. The merge is clean on everything attributable to it.

**But the merged tree does not currently pass a full repository gate**, and that must not be
softened: `ruff format --check` and `mypy` are red on `main` right now for unrelated reasons. Anyone
citing this merge as gate-green would be wrong.

### What this merge is NOT

The `474795f` PASS certifies that revision. This merge produces a tree **no adjudicator has seen** —
9 branch commits into a `main` 22 commits ahead. The verdict does not transfer, and the two
un-runnable gates above mean the combined rerun precondition 4 asks for is **partially unmet**.
A fresh adjudication of the merged revision is still required before release use.

## Next safe action

A separate adjudicator should verify the merged revision, including the OpenAPI and real-browser
gates this session could not run. The two red repository gates need their owners, not an
integrator.
