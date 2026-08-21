# Decision: concurrent workspace ownership and merge preconditions

STATUS: Accepted  
DATE: 2026-08-21  
OWNER: User and Claude Code

## Context

`20260820-cross-agent-coordination.md` established that "one uniquely named active work record per
task" is the visible path claim. That holds in a shared checkout. It silently fails in a worktree,
because the record is created inside the worktree and is untracked there, so no other agent reading
`agent_context/work/active/` in the primary checkout can see it.

On 2026-08-21 this produced a real incident. An agent working in a registered worktree on branch
`claude/truthful-data-source` held a complete active record inside that worktree. A concurrent disk
layout audit read the primary checkout, found no claim for the worktree, and correctly followed
PROTOCOL section 7 by opening an `UNKNOWN_OWNER` record against a workspace that was in active use.
The audit later self-corrected to `DO_NOT_TOUCH_WHILE_ACTIVE` and wrote, in its own record, that the
protocol assumes all active records are visible in one place and that `git worktree list` is the
only reliable way to discover concurrent agents.

Three further gaps surfaced in the same incident:

- No rule governs `git worktree remove`, `git worktree prune`, or `git branch -D` against another
  agent's workspace. `AGENTS.md` forbade only relocation by file move, which is less destructive.
- No rule governs merging another agent's branch. The branch carried a record whose `Next safe
  action` stated the merge must wait for Slice 4 certification, because the branch adds 16 tests and
  moves repository-wide gate counts. It was merged before that condition was met.
- The consequence is concrete: Slice 4's pinned evidence of 254 repository tests and 5,806
  statements at 88.62% no longer reproduces at `main`, and an independent verifier re-running from a
  clean state will read that mismatch as a gate failure rather than as expected drift.

No data was lost and every action taken was defensible under the rules as written. That is precisely
why the rules must change: correct behaviour under the current rules still produced a false
abandonment finding and an evidence mismatch.

## Decision

Four rules, added to `PROTOCOL.md` section 8 and mirrored in `AGENTS.md`:

1. **A claim is only real where every agent can see it.** The active work record for worktree work
   is created in the primary checkout, before the worktree exists, and names the worktree path and
   branch. A copy may live in the worktree so it travels with the branch, but the primary checkout's
   copy is authoritative for ownership.

2. **Discovery includes workspaces, not only records.** The startup sequence runs `git worktree
   list` and `git branch --list` alongside reading active records. A registered worktree or a
   non-default branch with no matching claim is treated as a live agent until proven otherwise, not
   as an abandoned artifact.

3. **A live workspace is not yours to destroy.** Never run `git worktree remove`, `git worktree
   prune`, `git branch -d/-D`, or delete a workspace directory belonging to another agent. This
   holds even when the workspace looks idle, is clean, or has no visible claim, and it holds during
   reconciliation. Removal happens only after the owning agent records `COMPLETED` or the founder
   directs it.

4. **Merging honours the record's stated preconditions.** Before merging another agent's branch, read
   its record's `Next safe action` and `Blockers and conflicts`. If it names a precondition, that
   precondition is binding. If a merge would change any number another record pins as evidence, the
   merging agent either waits, or notifies the owner in their record that a re-baseline is required.

Enforcement is `scripts/audit-agent-claims.ps1`, which cross-references registered worktrees and
local branches against active records and exits 1 on an unclaimed workspace or a claim naming a
workspace that no longer exists. It runs before any handoff or completion, alongside
`scripts/audit-disk-layout.ps1`.

## Evidence

- `git log --oneline main`: `1148b99` authored in the worktree, merged by `ebded8c`, records moved
  by `45bedda`.
- The `UNKNOWN_OWNER` record and its own addendum, which names the visibility gap and the
  `git worktree list` workaround, now in `agent_context/work/completed/`.
- `agent_context/work/completed/20260821-claude-truthful-data-source.md`, whose `Next safe action`
  states the unmet merge precondition.
- `agent_context/work/active/20260820-codex-slice4-ridge-training.md`, which still pins 254 tests
  and 5,806 statements at 88.62%.
- `AGENTS.md` startup step 4 and PROTOCOL section 2 step 1, both of which read only the primary
  checkout's `work/active/`.

## Rejected alternatives

- **A pointer stub in the primary checkout beside a worktree-local record**: rejected because two
  files describing one claim drift, and the incident was caused by a claim being in the wrong place,
  not by a missing pointer. One authoritative location is the fix.
- **Requiring the record be committed on the branch**: rejected because a claim must be visible
  before the first commit. The gap is widest exactly when work is uncommitted, which is when the
  worktree looks most abandoned.
- **Forbidding worktrees and mandating a shared checkout**: rejected because worktree isolation is
  what protects pinned gate evidence, which is the same evidence rule 4 protects. Removing it would
  trade a visibility problem for a correctness problem.
- **Relying on tool messaging between agents**: rejected because the agents here run in different
  tools and sessions with no shared channel, which is the stated premise of the original decision.
- **A lock file**: rejected as a heavier mechanism that still fails when an agent exits uncleanly,
  and PROTOCOL already states that records are declarations and worktrees are the lock.

## Consequences

Creating a worktree costs one extra step: write the record in the primary checkout first. In return,
`git worktree list` and the active records can no longer disagree, and an audit cannot mistake a
working agent for an abandoned artifact.

Reconciliation becomes slower and more explicit. A coordinator may no longer merge a branch on the
strength of its diff alone; it must read the record and honour stated preconditions, or say in
writing why it did not.

Migration: none required. There is one active record and no registered worktrees at `45bedda`.

Rollback: revert this decision and the two rule-file amendments. The audit script is additive and
can be left in place.

Follow-up: the Slice 4 owner must re-baseline the pinned gate numbers against the post-merge
revision before requesting independent verification. That is theirs to do; this decision does not
touch `.launch/`.
