# Completed work: Canonical D: disk layout for QuantOS

STATUS: COMPLETED  
OWNER: Claude Code root agent  
TOOL: Claude Code  
STARTED_UTC: 2026-08-20T23:36:47Z  
COMPLETED_UTC: 2026-08-20T23:48:00Z  
STARTING_REVISION: `6a17d5e60f9fd93538cb403a09b7b87732996d5a`  
WORKTREE_OR_BRANCH: `D:\quant_system` on `main`

## Objective

Stop QuantOS working directories from spreading across the root of `D:`. Sweep the stray root-level
verification clones into the established workspace bucket, then make the layout a written, tooled,
startup-visible law so the next agent cannot recreate the mess.

## Owned paths

- `agent_context/work/completed/20260821-claude-organize-disk-layout.md`
- `agent_context/work/active/20260821-unknown-owner-data-provenance-worktree.md`
- `agent_context/DISK-LAYOUT.md`
- `scripts/quantos-layout.psm1`
- `scripts/audit-disk-layout.ps1`
- `scripts/organize-disk-layout.ps1`
- `scripts/new-workspace-clone.ps1`
- `AGENTS.md` (appended one "Disk layout law" section and one startup-step reference)
- `D:\quant_system_workspaces\`
- `D:\quant_system_redteam_s4_final_1787268332685` (move source only)
- `D:\quant_system_slice4_verify_6a17d5e_20260821` (move source only)

## Non-goals

- Moving, renaming, or restructuring the primary checkout. It is the canonical install path cited
  by clone origins, verifier evidence, and every work record.
- Deleting any verification clone, Red Team clone, or evidence environment.
- Touching the repository `tmp` folder. Four of those environments are cited by name as CLEAN CLONE
  paths in the Slice 1 to 3 verifier reports; relocating them would break recorded evidence.
- Editing any path claimed by `20260820-codex-slice4-ridge-training.md`, including
  `agent_context/CURRENT.md`, the `.launch` state files, and all Slice 4 source, test, and report
  paths.
- Changing any product code, test, or gate behavior.

## Plan

1. COMPLETE - audit every QuantOS path on the drive, size it, and classify strays vs. canonical
   roots.
2. COMPLETE - prove the two stray root clones are clean, detached, unreferenced, and idle.
3. COMPLETE - move the two strays into the verification clones bucket.
4. COMPLETE - write the layout contract, the workspace README, and the enforcement scripts.
5. COMPLETE - append the startup-visible layout law to `AGENTS.md` and verify with the audit script.
6. COMPLETE - record the one violation that is not mine to fix as an `UNKNOWN_OWNER` claim.

## Current step

Done. The drive root holds exactly the two canonical QuantOS entries plus one stray worktree that
belongs to another agent and is recorded rather than touched.

## Decision rationale

Evidence: the drive root carried four QuantOS top-level entries. `git worktree list --porcelain`
showed the primary checkout as the only registered worktree at audit time. Both stray folders were
clean detached clones at `6a17d5e` with the primary checkout as origin, about 299 MB each, last
written 2026-08-21 04:58 local, with no process holding them. Both a `Get-Process` path filter and a
`Win32_Process` query returned empty.

Decision: move rather than delete. They are reproducible clean-state environments and deleting
another agent's evidence is forbidden by `AGENTS.md`. Moving is reversible and matches the
convention the previous Codex record already established for two earlier clones.

Decision: make the convention executable. Two prior sweeps did not stop recurrence because the
convention lived only in a completed work record that new agents never read. The law now sits in
`AGENTS.md` startup reading, has a contract document, and has an audit that exits non-zero.

Rejected alternative 1: consolidate everything under a single new QuantOS root. That requires moving
the primary checkout itself, invalidating the origin of all four clones, the CLEAN CLONE paths in
the verifier reports, the branch field of every work record, and the running session working
directory. High cost, cosmetic benefit.

Rejected alternative 2: relocate the 4.7 GB of verifier environments out of the repository `tmp`
folder. Four accepted verifier reports cite those directories by absolute path as evidence. Moving
them would either break the citations or force an edit to accepted evidence documents. Reported to
the founder as a reclaim decision instead.

Rejected alternative 3: rename the existing verification clones bucket into finer buckets. That
would re-move another agent's completed work for naming taste alone. Kept the established name;
Red Team clones are verification clones.

Assumption: the Codex Slice 4 agent had finished writing to both stray clones. Basis is the idle
timestamps and the absent processes above. The move preserved content byte for byte, so a resumed
run only needs the new path.

## Commands and outcomes

| Command | Result | Evidence/notes |
|---|---|---|
| Required startup reads plus `git status --short --branch` | PASS | One active Codex record; its claimed paths are disjoint from mine. |
| `git rev-parse HEAD` | PASS | `6a17d5e`, matches both stray clones. |
| `git worktree list --porcelain` | PASS | Primary checkout was the only registered worktree at audit time. |
| Clone status, HEAD, and remote audit | PASS | Both strays clean, detached at `6a17d5e`, origin is the primary checkout. |
| `Get-Process` path filter and `Win32_Process` query | PASS | No process held either stray directory. |
| Size inventory of the repository `tmp` folder | PASS | 18 entries, 4.7 GB, 16 of them full verifier environments. |
| Grep for verifier paths across the `.launch` reports | PASS | Four accepted reports cite `tmp` verifier paths; do not move. |
| `Move-Item` of both strays into the clones bucket | PASS | Both moved; each still reports a clean tree at `6a17d5e`. |
| `git rev-parse HEAD` in all four bucket clones | PASS | Two at `8d09ec4`, two at `6a17d5e`, all clean. |
| `new-workspace-clone.ps1 -Purpose audit -Label layout-selftest` | PASS | Created the stamped name in the clones bucket; removed after the self-test. |
| `organize-disk-layout.ps1` dry run | PASS | Correctly skipped the stray parent because it contains a registered worktree. |
| `audit-disk-layout.ps1` | FAIL, exit 1, expected | Both canonical roots OK; the single violation is the other agent's worktree. |
| `audit-disk-layout.ps1` against empty buckets | FIXED then PASS | Strict-mode null dereference in `Get-QuantOsDirectorySize` for empty directories; guarded and re-verified. |

## Files changed

- `agent_context/DISK-LAYOUT.md`: new layout contract, rules, and enforcement table.
- `AGENTS.md`: added a "Disk layout law" section and added the contract to startup step 1.
- `scripts/quantos-layout.psm1`: new shared module that derives the layout from the install root,
  sizes directories, and classifies strays including registered worktrees.
- `scripts/audit-disk-layout.ps1`: new read-only audit; exits 1 on any violation.
- `scripts/organize-disk-layout.ps1`: new organizer; dry run by default, `-Apply` executes, never
  deletes, refuses to file-move a registered worktree.
- `scripts/new-workspace-clone.ps1`: new creator for clones and worktrees in the correct bucket,
  with purpose, label, short revision, and UTC stamp in the name.
- `agent_context/work/active/20260821-unknown-owner-data-provenance-worktree.md`: new
  `UNKNOWN_OWNER` claim protecting the stray worktree.
- Workspaces `README.md` plus new `worktrees`, `scratch`, and `archive` buckets.
- Both stray clones moved unchanged into the verification clones bucket.
- No product code, test, or gate behavior changed.

## Blockers and conflicts

One violation is deliberately left in place. The `data-provenance` directory below the stray
`quant_system_wt` parent is a Git worktree on branch `claude/truthful-data-source`, registered at
2026-08-21 05:02:31 local while this audit was running, claimed by no work record. `AGENTS.md`
forbids cleaning up another agent's work, and a file move would break its Git registration. It is
recorded in `agent_context/work/active/20260821-unknown-owner-data-provenance-worktree.md` with the
exact `git worktree move` command, pending founder or owner authorization.

Reported for a founder decision, not acted on: the repository `tmp` folder holds 4.7 GB across
sixteen full verifier environments for slices 1 to 4. Four are cited as evidence and must stay. The
rest are regenerable and would reclaim roughly 3.6 GB.

## Stop point

Sweep, contract, tooling, and the `AGENTS.md` law are complete and self-tested. The audit script
reports both canonical roots as OK and exits 1 solely on the other agent's worktree.

## Next safe action

Confirm the owner of `claude/truthful-data-source` is idle, then relocate the inner worktree with the
`git worktree move` command recorded in the `UNKNOWN_OWNER` file and remove the empty parent
directory. Re-run the audit; it should then exit 0.
