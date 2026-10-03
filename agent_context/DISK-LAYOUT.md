# QuantOS disk layout contract

QuantOS lives entirely on the drive it is installed on. On the reference machine that is `D:`.
"On the drive" is not the same as "at the root of the drive". This contract says exactly where each
kind of QuantOS directory belongs, so the drive root stays readable and no agent has to guess.

## Canonical layout

```text
D:\Quant OS\
├── quant_system\                        # the platform. The only checkout that is ever developed in.
│   ├── src\  tests\  scripts\  configs\  docs\  .launch\  agent_context\
│   ├── .venv\                           # local environment, gitignored
│   ├── build\  dist\  installer\        # packaging output, gitignored
│   ├── data\  logs\                     # runtime state, gitignored
│   └── tmp\                             # run-scoped scratch and cited verifier environments
└── quant_system_workspaces\             # every derived QuantOS working directory
    ├── verification_clones\             # detached clean-state clones for verifier and Red Team runs
    ├── worktrees\                       # registered Git worktrees for concurrent agents
    ├── scratch\                         # anything else temporary that is not a Git checkout
    └── archive\                         # retained but finished environments
```

The canonical home of QuantOS is `D:\Quant OS`.
For full backwards-compatibility with ongoing scheduled tasks and external tooling, `D:\quant_system` and `D:\quant_system_workspaces` are maintained as transparent NTFS directory junctions pointing directly to `D:\Quant OS\quant_system` and `D:\Quant OS\quant_system_workspaces`.

## Rules

1. **Never develop outside the install root.** `D:\Quant OS\quant_system` is the primary checkout that receives
   ordinary edits. (Legacy references to `D:\quant_system` transparently map to this folder via junction).

2. **Never create a working directory at the drive root.** Verification clones, Red Team clones,
   mutation environments, and agent worktrees all belong under `quant_system_workspaces`.

3. **Create workspaces with the script, not by hand.**

   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts/new-workspace-clone.ps1 -Purpose verify -Label slice4
   powershell -ExecutionPolicy Bypass -File scripts/new-workspace-clone.ps1 -Kind Worktree -Purpose feature -Label data-provenance -Branch claude/my-branch
   ```

   It resolves the bucket, stamps the name with purpose, label, short revision, and UTC time, and
   prints the path to record in your work record.

4. **A registered Git worktree is never relocated with a file move.** Moving the directory breaks
   the pointer in `.git/worktrees/<name>/gitdir` and the `gitdir:` file inside the worktree. Use
   `git worktree move <old> <new>`, and only when no agent is working in it.

5. **Audit before every handoff.**

   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts/audit-disk-layout.ps1
   ```

   It exits 1 on any violation. Fix with `scripts/organize-disk-layout.ps1` — dry run by default,
   `-Apply` to execute, and it never deletes anything.

6. **Retire your own workspaces.** A clone kept as evidence goes to `archive\` with a note in the
   work record explaining what it proves. A clone kept for no reason is clutter; delete it. Deleting
   a workspace another agent created is forbidden by `AGENTS.md`; ask the owner or the founder.

## Directories that deliberately stay inside the install root

`D:\quant_system\tmp\` holds run-scoped scratch and a set of verifier environments. Four of them are
cited by absolute path as CLEAN CLONE evidence in `.launch/reports/VERIFIER-SLICE-01.md`,
`VERIFIER-SLICE-02.md`, `VERIFIER-SLICE-02-ATTEMPT-01.md`, and `VERIFIER-SLICE-03.md`. Relocating
those breaks accepted evidence, so they stay where the reports say they are.

New verifier environments should be created under `quant_system_workspaces\verification_clones`
instead, and cited from there. `tmp\` is expected to shrink over time rather than grow; it is
gitignored and safe to prune with founder approval once the slice it belongs to is certified.

`pyproject.toml` pins pytest to `--basetemp=tmp/pytest`, which keeps test scratch inside the install
root and off the system drive. Do not change that without a decision record.

## Enforcement

| Script | Purpose | Destructive |
|---|---|---|
| `scripts/audit-disk-layout.ps1` | Reports every QuantOS path and exits 1 on violations | No, read-only |
| `scripts/organize-disk-layout.ps1` | Moves strays into the correct bucket | No, moves only, never deletes |
| `scripts/new-workspace-clone.ps1` | Creates a clone or worktree in the right place | No |
| `scripts/quantos-layout.psm1` | Shared layout definition used by all three | No |

The layout is derived from the install root at runtime, so the contract holds on any drive and any
machine without editing the scripts.
