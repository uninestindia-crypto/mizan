# Active work: UNKNOWN_OWNER - data-provenance worktree at the drive root

STATUS: RESOLVED_AND_RETIRED  
RESOLVED_UTC: 2026-08-21T00:01:00Z  
OWNER: identified (Claude Code session 21d82993, merged into main)  
RECORDED_BY: Claude Code root agent (disk layout task)  
TOOL: unknown  
STARTING_REVISION: `6a17d5e60f9fd93538cb403a09b7b87732996d5a`  
WORKTREE_OR_BRANCH: `D:\quant_system_wt\data-provenance` on `claude/truthful-data-source`

## Why this record exists

`PROTOCOL.md` section 7 requires an `UNKNOWN_OWNER` record when changes appear with no identified
owner. This worktree was registered at 2026-08-21 05:02:31 local while the disk layout audit was
running. No active work record claims it and no `agent_context` file mentions the branch.

It is also the one remaining violation of `agent_context/DISK-LAYOUT.md`: it sits at the drive root
instead of `D:\quant_system_workspaces\worktrees\`.

## Owned paths

- `D:\quant_system_wt\**` (do not edit)
- `refs/heads/claude/truthful-data-source` (do not edit)
- `agent_context/work/active/20260821-unknown-owner-data-provenance-worktree.md`

## Observed state

| Check | Result |
|---|---|
| `git worktree list --porcelain` | Registered as a worktree of `D:\quant_system` |
| `git status --short --branch` inside it | Clean; branch `claude/truthful-data-source`, no changes |
| `git rev-parse HEAD` | `6a17d5e`, equal to `main` |
| `.git` pointer file | `gitdir: D:/quant_system/.git/worktrees/data-provenance` |
| Content | Checkout of `6a17d5e` only; no work committed or staged yet |

## Do not do

- Do not delete the directory, remove the worktree, or delete the branch.
- Do not relocate it with `Move-Item`, `mv`, or any file move. That breaks both
  `.git/worktrees/data-provenance/gitdir` and the `gitdir:` pointer inside the worktree.
- Do not edit any file inside it.

## Pending relocation

Once the owner confirms it is idle, relocate it with the registration-preserving command, run from
`D:\quant_system`:

```powershell
git worktree move "D:\quant_system_wt\data-provenance" "D:\quant_system_workspaces\worktrees\data-provenance"
Remove-Item -LiteralPath "D:\quant_system_wt" -Force   # only if the parent is then empty
```

`scripts/organize-disk-layout.ps1 -Apply -MoveWorktrees` performs the same move and refuses when the
worktree is dirty. It currently skips this path because the stray is the parent directory rather
than the worktree itself.

## Next safe action

Identify the owner. If the branch is abandoned and unmerged work is absent, relocate as above and
close this record. If the owner is active, ask them to relocate it themselves.

## Addendum 2026-08-20T23:52Z - owner identified, worktree is LIVE

The owner is no longer unknown. The worktree holds its own active work record at
`agent_context/work/active/20260821-claude-truthful-data-source.md`, which is untracked and
therefore invisible from the primary checkout. That is why the first audit found no claim.

Live state at 2026-08-21 05:20 local:

- last write 24 seconds earlier; the agent is actively editing
- 7 modified tracked files: `configs/upstox_config.yaml`, `launcher.py`,
  `scripts/daily_pipeline.py`, `src/quant_system/server/app.py`,
  `src/quant_system/server/schemas.py`, `tests/test_daily_pipeline.py`,
  `tests/test_server_api.py`
- 4 untracked files including `src/quant_system/data/provenance.py` and
  `tests/test_data_provenance.py`
- 0 commits ahead of `main`, so all of that work exists only in the working tree

STATUS CHANGE: `UNKNOWN_OWNER` to `DO_NOT_TOUCH_WHILE_ACTIVE`.

Relocating this worktree now would move the working directory out from under a running agent and
risk uncommitted work. Do not run `git worktree move` until that agent commits and stops.

## Process gap this exposes

A worktree agent's active record lives inside its own worktree, so no other agent can see the claim
from the primary checkout. `PROTOCOL.md` assumes all active records are visible in one place. Until
that is fixed, `git worktree list` is the only reliable way to discover concurrent agents, which is
why `scripts/audit-disk-layout.ps1` reports registered worktrees explicitly.
