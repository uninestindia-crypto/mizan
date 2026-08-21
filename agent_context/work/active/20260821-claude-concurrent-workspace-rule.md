# Active work: concurrent workspace ownership rule

STATUS: HANDOFF_REQUIRED  
OWNER: Claude Code (Opus 5) session 21d82993  
TOOL: Claude Code  
STARTED_UTC: 2026-08-21T05:40:00Z  
STARTING_REVISION: `45bedda`  
WORKTREE_OR_BRANCH: `D:\quant_system` on `main`

## Objective

Close the coordination gaps that let a live agent's workspace be treated as abandoned, and that let
a branch be merged past a precondition its own record had stated. Founder instruction: make it a
rule so it does not happen again by any agent.

## Owned paths

- `AGENTS.md`
- `agent_context/PROTOCOL.md`
- `agent_context/decisions/20260821-concurrent-workspace-ownership.md`
- `scripts/audit-agent-claims.ps1`
- `agent_context/work/active/20260821-claude-concurrent-workspace-rule.md`
- `agent_context/work/completed/20260821-claude-concurrent-workspace-rule.md`

## Non-goals

- Editing anything claimed by `20260820-codex-slice4-ridge-training.md`.
- Rewriting `DISK-LAYOUT.md` or the disk-layout tooling. Those rules are correct; they simply do not
  cover claim visibility, workspace destruction, or merge preconditions.
- Re-litigating the merge that already happened. The fix is forward-looking.
- Changing `.launch/` state. Slice 4 owns it and its evidence re-baseline is that agent's call.

## Plan

1. COMPLETE - reconstruct the incident from Git history and the surviving records.
2. COMPLETE - write the decision record, amend the two rule files, add the audit script.
3. COMPLETE - prove the audit script detects each failure mode it claims to detect.
4. PENDING - founder review, then commit.

## Current step

All rule text and enforcement written and self-tested. Nothing committed.

## Decision rationale

Working in the shared checkout is permitted here under PROTOCOL section 1: owned paths are exact and
disjoint from the only other active record, no repository-wide command is involved, and the changes
are governance documents plus one PowerShell script. None of it perturbs the Python gate counts,
which is what forced worktree isolation for the previous task.

`AGENTS.md` is a shared root guidance file, normally requiring single-owner coordination under
PROTOCOL section 4. The founder's explicit instruction is that authority.

### Incident reconstruction

Four distinct gaps, each independently sufficient to cause the failure:

1. A worktree agent's active record lived inside its own worktree, untracked, so it was invisible
   from the primary checkout. `AGENTS.md` startup step 4 reads `agent_context/work/active/` in the
   primary checkout only, so the audit correctly concluded the worktree was unclaimed and opened an
   `UNKNOWN_OWNER` record against an agent that was actively editing.
2. Neither rule file names `git worktree list` as a discovery step, so there is no way to find a
   concurrent agent whose claim is invisible.
3. `AGENTS.md` forbids relocating a registered worktree while an agent works in it, but says nothing
   about `git worktree remove`, `git worktree prune`, or `git branch -D`. Removal is more
   destructive than relocation and was ungoverned.
4. Nothing governs merging another agent's branch. The merged record stated, under `Next safe
   action`, that the merge should wait for Slice 4 certification precisely because the added tests
   move repository-wide gate counts. It was merged anyway, so Slice 4's pinned evidence of 254 tests
   and 5,806 statements no longer reproduces at `main`.

The common root cause is that a claim is only as good as its visibility, and a stated precondition
is only as good as the rule that makes reading it mandatory.

## Commands and outcomes

| Command | Result | Evidence/notes |
|---|---|---|
| `git status --short --branch`, `git rev-parse HEAD` | PASS | Clean tree at `45bedda`, `main` ahead 3. |
| `git worktree list` | PASS | Only the install root remains registered. |
| `git log --oneline -8 main` | PASS | Confirms merge `ebded8c` and record move `45bedda`. |
| `audit-agent-claims.ps1` on clean state | PASS | Exit 0; two records, no workspaces. |
| `audit-agent-claims.ps1` with unclaimed worktree | PASS | Exit 1; reported UNCLAIMED worktree and UNCLAIMED branch. Reproduces the incident. |
| `audit-agent-claims.ps1` after adding the claim | PASS | Exit 0; both resolved to OK. |
| `audit-agent-claims.ps1` after removing the workspace | PASS | Exit 1; reported STALE claim. |
| `audit-disk-layout.ps1 -Fast` | PASS | No stray directories; selftest workspace fully retired. |

Self-test workspace `claude/audit-selftest` was created and removed by this agent only. Removing a
workspace you created yourself is permitted under the new section 8.3.

## Files changed

- `agent_context/decisions/20260821-concurrent-workspace-ownership.md`: NEW. Accepted decision with
  the incident reconstruction, four rules, five rejected alternatives, and consequences.
- `agent_context/PROTOCOL.md`: section 2 startup adds `git worktree list` and `git branch --list`
  and treats unclaimed workspaces as live; section 4 adds worktree removal, branch deletion, and
  cross-agent merges to the coordinated-operation list; section 7 forbids acting destructively on an
  `UNKNOWN_OWNER` finding; new section 8 carries the four binding rules and the enforcement command.
- `AGENTS.md`: startup sequence gains the workspace-discovery step and the claim-first requirement
  for worktrees; new "Workspace ownership law" section mirrors section 8 in the auto-loaded file.
- `scripts/audit-agent-claims.ps1`: NEW. Read-only cross-reference of registered worktrees and local
  branches against active records. Exits 1 on UNCLAIMED or STALE.

## Blockers and conflicts

None. Owned paths are disjoint from the Slice 4 record.

Rule 8.4 obliged someone to tell the Slice 4 owner that `main` no longer reproduces their pinned
254 tests / 5,806 statements / 88.62%. That is now resolved without action from me:
`20260821-0530Z-claude-slice4-certification.md` (started 05:30Z) adopts the Slice 4 task, states the
re-baseline to 272 tests / 5,830 statements at `45bedda`, and proves the modeling and evidence
packages are byte-identical to `6a17d5e`. Owned paths are disjoint from mine; no coordination is
outstanding.

## Stop point

All four files written. Both audits pass. Working tree contains exactly the five owned paths, two
modified and three new. Nothing staged, nothing committed.

## Next safe action

Founder review, then commit the five paths. No merge or branch work is involved.
