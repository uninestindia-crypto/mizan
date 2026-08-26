# NOTICE: additive edits to `execution/governed_strategy.py`, a Red Team adjudication target

FILED_UTC: 2026-08-26T00:00:00Z
FILED_BY: Claude Code — `20260826-claude-cross-sectional-execution-path.md`
SUBJECT_RECORD: `agent_context/work/active/20260823-redteam-governed-execution-path.md`
  (STATUS: IN_PROGRESS)
STATUS: NOTICE (additive; the subject record is **not** edited)

## Why this exists

The subject record lists `src/quant_system/execution/governed_strategy.py` in its adjudication
target table. It owns only its own record and `.launch/reports/RED-TEAM-GOVERNED-EXECUTION.md`, and
states its adjudication is read-only against the tree — so it holds no write claim and this is not a
claim conflict. PROTOCOL 8.4 still requires that an agent whose evidence a change could move be able
to see the change. This file is that notice.

## What changed

Three module-private helpers were promoted to public names so a new cross-sectional module can reuse
them instead of copying the risky parts:

| Was | Now | Behaviour |
|---|---|---|
| `_require_bar_history` | `require_bar_history` | unchanged |
| `_require_bar_sequence` | `require_bar_sequence` | unchanged |
| `_available_window` | `available_window` | unchanged |

The private names are retained as aliases, so any existing reference still resolves.

**No invariant is relaxed.** Specifically, the per-bar symbol verification that a recheck added after
finding RELIANCE bars passing under an INFY key (`governed_strategy.py:420-423`) is neither moved nor
weakened; the new module reuses that exact function rather than reimplementing it, which is the
reason for the promotion.

## What is NOT changed

- `PromotedModelBundleV1`, `ModelEvidenceIdentityV1`, `GovernedModelStrategy` — no field, check, or
  arithmetic altered. The single-instrument path behaves bit-for-bit as before.
- The verdict gate. `RESEARCH_ONLY` and `REJECT` remain executable on no surface.
- The feature-schema pin on the single-instrument bundle.

## Numbers this could invalidate

The subject record pins `STARTING_REVISION: 1e5beb5`. HEAD is `466d562b`. `governed_strategy.py` has
already changed at `97fcc4b`, `deccec1`, `85ff535`, `8f29564` and `88a7ac9` since that revision, so
the pinned baseline was stale before this edit. No test count, coverage figure, or manifest hash
named in the subject record is moved by a rename-with-alias.

## If the owner objects

Revert is mechanical: restore the three leading underscores and delete the aliases. Nothing outside
`execution/cross_sectional_strategy.py` depends on the public names.
